import logging

from openhands.agenthub.searcher_agent.action_parser import SearcherAgentResponseParser
from openhands.agenthub.searcher_agent.prompt import get_prompt
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.config.llm_config import LLMConfig
from openhands.core.message import Message, TextContent
from openhands.events.action import Action, AgentFinishAction, IPythonRunCellAction
from openhands.events.action.commands import CmdRunAction
from openhands.events.action.message import MessageAction
from openhands.events.observation import IPythonRunCellObservation
from openhands.events.observation.commands import CmdOutputObservation
from openhands.events.observation.error import ErrorObservation
from openhands.events.observation.observation import Observation
from openhands.events.observation.reject import UserRejectObservation
from openhands.llm.llm import LLM
from openhands.runtime.plugins.agent_skills import AgentSkillsRequirement
from openhands.runtime.plugins.jupyter import JupyterRequirement
from openhands.runtime.plugins.requirement import PluginRequirement


# WIP: Make this agent be able to detect when to stop and automatically stop (or make the supervisor able to stop the agent).
class SearcherAgent(Agent):
    VERSION = '1.0'
    """
    The Searcher Agent is an agent that searches the codebase for relevant information.
    """

    sandbox_plugins: list[PluginRequirement] = [
        # NOTE: AgentSkillsRequirement need to go before JupyterRequirement, since
        # AgentSkillsRequirement provides a lot of Python functions,
        # and it needs to be initialized before Jupyter for Jupyter to use those functions.
        AgentSkillsRequirement(),
        JupyterRequirement(),
    ]

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
            splitted = text.split('\n')
            for i, line in enumerate(splitted):
                if '![image](data:image/png;base64,' in line:
                    splitted[i] = (
                        '![image](data:image/png;base64, ...) already displayed to user'
                    )
            text = '\n'.join(splitted)
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
        """Performs one step using the SearcherAgent.
        This includes gathering info on previous steps and prompting the model to make a command to execute.

        Parameters:
        - state (State): used to get updated info

        Returns:
        - CmdRunAction(command) - bash command to run
        - IPythonRunCellAction(code) - IPython code to run
        - MessageAction(content) - Message action to run (e.g. ask for clarification)
        - AgentFinishAction() - end the interaction
        """

        # prepare what we want to send to the LLM
        messages = self._get_messages(state)
        params = {
            'messages': self.llm.format_messages_for_llm(messages),
            'stop': [
                '</execute_bash>',
                '</execute_ipython>',
            ],
        }

        response = self.llm.completion(**params)

        return self.action_parser.parse(response)

    def _get_messages(self, state: State) -> list[Message]:
        # Get task and suggested approach from state inputs
        task = state.inputs.get('task', '')
        suggested_approach = state.inputs.get('suggested_approach', '')

        messages: list[Message] = [
            Message(
                role='system',
                content=[
                    TextContent(
                        text=get_prompt(task, suggested_approach),
                        cache_prompt=self.llm.is_caching_prompt_active(),
                    )
                ],
            ),
        ]

        for event in state.history.get_events():
            # create message from event
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
                    message.content[-1].cache_prompt = True
                    user_turns_processed += 1

        return messages
