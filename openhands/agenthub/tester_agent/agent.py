import logging

from openhands.agenthub.tester_agent.action_parser import TesterAgentResponseParser
from openhands.agenthub.tester_agent.prompt import get_prompt
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.config.llm_config import LLMConfig
from openhands.core.message import Message, TextContent
from openhands.events.action import Action, AgentFinishAction
from openhands.events.action.commands import CmdRunAction, IPythonRunCellAction
from openhands.events.action.message import MessageAction
from openhands.events.observation.commands import (
    CmdOutputObservation,
    IPythonRunCellObservation,
)
from openhands.events.observation.error import ErrorObservation
from openhands.events.observation.observation import Observation
from openhands.events.observation.reject import UserRejectObservation
from openhands.llm.llm import LLM


class TesterAgent(Agent):
    VERSION = '1.0'
    """
    The Tester Agent is an agent that tries to replicate the issue.
    """

    action_parser = TesterAgentResponseParser()

    def __init__(self, llm: LLM, config: AgentConfig):
        """Initialize the Tester Agent with an LLM

        Parameters:
        - llm (LLM): The llm to be used by this agent
        - config (AgentConfig): The configuration for this agent
        """
        # TODO: Remove this once we have a real LLM config
        llm_config = LLMConfig(
            model='deepseek/deepseek-chat', api_key='REDACTED', temperature=0.0
        )
        llm = LLM(llm_config)
        # TODO: Remove this once we have a real AgentConfig
        config = AgentConfig(llm_config='deepseek')
        super().__init__(llm, config)
        # Set up logger
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.DEBUG)  # Set the logging level

    def get_action_message(self, action: Action) -> Message | None:
        """Convert an Action to a Message for the LLM conversation.

        Parameters:
        - action (Action): The action to convert

        Returns:
        - Message | None: The converted message, or None if action type is not supported
        """
        if isinstance(action, CmdRunAction):
            return Message(
                role='assistant',
                content=[
                    TextContent(
                        text=f'{action.thought}\n<execute_bash>\n{action.command}\n</execute_bash>'
                    )
                ],
            )
        elif isinstance(action, IPythonRunCellAction):
            return Message(
                role='assistant',
                content=[
                    TextContent(
                        text=f'{action.thought}\n<execute_ipython>\n{action.code}\n</execute_ipython>'
                    )
                ],
            )
        elif isinstance(action, MessageAction):
            return Message(
                role='user' if action.source == 'user' else 'assistant',
                content=[TextContent(text=action.content)],
            )
        elif isinstance(action, AgentFinishAction) and action.source == 'agent':
            return Message(role='assistant', content=[TextContent(text=action.thought)])
        return None

    def get_observation_message(self, obs: Observation) -> Message | None:
        """Convert an Observation to a Message for the LLM conversation.

        Parameters:
        - obs (Observation): The observation to convert

        Returns:
        - Message | None: The converted message, or None if observation type is not supported
        """
        obs_prefix = 'OBSERVATION:\n'
        if isinstance(obs, CmdOutputObservation):
            text = obs_prefix + obs.content
            text += (
                f'\n[Command {obs.command_id} finished with exit code {obs.exit_code}]'
            )
            return Message(role='user', content=[TextContent(text=text)])
        elif isinstance(obs, IPythonRunCellObservation):
            text = obs_prefix + obs.content
            return Message(role='user', content=[TextContent(text=text)])
        elif isinstance(obs, ErrorObservation):
            text = obs_prefix + obs.content
            text += '\n[Error occurred in processing last action]'
            return Message(role='user', content=[TextContent(text=text)])
        elif isinstance(obs, UserRejectObservation):
            text = obs_prefix + obs.content
            text += '\n[Last action has been rejected by the user]'
            return Message(role='user', content=[TextContent(text=text)])
        else:
            raise ValueError(f'Unknown observation type: {type(obs)}')

    def step(self, state: State) -> Action:
        """Performs one step using the Tester Agent.
        This includes gathering info on previous steps and prompting the model to make a command to execute.

        Parameters:
        - state (State): used to get updated info

        Returns:
        - CmdRunAction(command) - bash command to run
        - IPythonRunCellAction(code) - IPython code to run
        - MessageAction(content) - Message action to run (e.g. ask for clarification)
        - AgentFinishAction() - end the interaction
        """
        # if we're done, go back
        latest_user_message = state.history.get_last_user_message()
        if latest_user_message and latest_user_message.strip() == '/exit':
            return AgentFinishAction()

        # prepare what we want to send to the LLM
        messages = self._get_messages(state)
        params = {
            'messages': self.llm.format_messages_for_llm(messages),
            'stop': [
                '</execute_ipython>',
                '</execute_bash>',
            ],
        }

        response = self.llm.completion(**params)

        return self.action_parser.parse(response)

    def _get_messages(self, state: State) -> list[Message]:
        task = state.inputs.get('task', '')
        summary = state.inputs.get('summary', '')

        messages: list[Message] = [
            Message(
                role='system',
                content=[
                    TextContent(
                        text=get_prompt(task, summary),
                        cache_prompt=self.llm.is_caching_prompt_active(),  # Cache system prompt
                    )
                ],
            ),
        ]

        for event in state.history.get_events():
            # create a regular message from an event
            if isinstance(event, Action):
                message = self.get_action_message(event)
            elif isinstance(event, Observation):
                message = self.get_observation_message(event)
            else:
                raise ValueError(f'Unknown event type: {type(event)}')

            # add regular message
            if message:
                # handle error if the message is the SAME role as the previous message
                if messages and messages[-1].role == message.role:
                    messages[-1].content.extend(message.content)
                else:
                    messages.append(message)

        # Add caching to the last 2 user messages
        if self.llm.is_caching_prompt_active():
            user_turns_processed = 0
            for message in reversed(messages):
                if message.role == 'user' and user_turns_processed < 2:
                    message.content[
                        -1
                    ].cache_prompt = True  # Last item inside the message content
                    user_turns_processed += 1

        # Add environment reminder to the latest user message
        latest_user_message = next(
            (m for m in reversed(messages) if m.role == 'user'),
            None,
        )

        if latest_user_message:
            reminder_text = f'\n\nENVIRONMENT REMINDER: You have {state.max_iterations - state.iteration} turns left to complete the task. When finished reply with <finish></finish>.'
            latest_user_message.content.append(TextContent(text=reminder_text))

        return messages
