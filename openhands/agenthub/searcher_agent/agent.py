import logging

from openhands.agenthub.searcher_agent.action_parser import SearcherAgentResponseParser
from openhands.agenthub.searcher_agent.prompt import get_prompt
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


class SearcherAgent(Agent):
    VERSION = '1.0'
    """
    The Searcher Agent is an agent that searches the codebase for relevant information.
    """

    action_parser = SearcherAgentResponseParser()

    def __init__(self, llm: LLM, config: AgentConfig):
        """Initialize the Searcher Agent with an LLM

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

    def step(self, state: State) -> Action:
        """Performs one step using the Searcher Agent.
        This includes gathering info about the codebase and summarizing relevant information.

        Parameters:
        - state (State): used to get updated info

        Returns:
        - Action: The next action to take
        """
        # Check if we should exit
        latest_user_message = state.history.get_last_user_message()
        if latest_user_message and latest_user_message.strip() == '/exit':
            return AgentFinishAction()

        # Prepare messages for LLM
        messages = []

        # Add system and initial messages
        task: str = state.inputs.get('task', '')
        suggested_approach: str = state.inputs.get('suggested_approach', '')
        messages.extend(
            [
                Message(
                    role='system',
                    content=[TextContent(text=get_prompt(task, suggested_approach))],
                )
            ]
        )

        # Add history messages
        for event in state.history.get_events():
            if isinstance(event, Action):
                message = self.get_action_message(event)
            elif isinstance(event, Observation):
                message = self.get_observation_message(event)
            else:
                raise ValueError(f'Unknown event type: {type(event)}')

            if message:
                # Handle consecutive messages from same role
                if messages and messages[-1].role == message.role:
                    messages[-1].content.extend(message.content)
                else:
                    messages.append(message)

        # Get response from LLM
        params = {
            'messages': self.llm.format_messages_for_llm(messages),
            'stop': [
                '</execute_ipython>',
                '</execute_bash>',
                '</finish>',
            ],
        }

        response = self.llm.completion(**params)

        # Parse and return the next action
        return self.action_parser.parse(response)

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
