import logging
import re
from typing import Any, Dict, List

from openhands.agenthub.supervisor_agent.prompt import (
    get_prompt,
)
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.config.llm_config import LLMConfig
from openhands.core.message import Message, TextContent
from openhands.events.action import Action, AgentDelegateAction, AgentFinishAction
from openhands.events.observation.delegate import AgentDelegateObservation
from openhands.llm.llm import LLM
from openhands.runtime.plugins.agent_skills import AgentSkillsRequirement
from openhands.runtime.plugins.jupyter import JupyterRequirement
from openhands.runtime.plugins.requirement import PluginRequirement


class SupervisorAgent(Agent):
    VERSION = '1.0'
    """
    The Supervisor Agent is an agent that collects information from other agents
    and makes decisions based on the information.
    """

    current_delegate: str = ''
    suggested_approaches: List[Dict[str, List[str]]] = []
    suggested_approach_index: int = -1  # -1 Because we increment it before using it
    results: Dict[str, List[Any]] = {'search': [], 'code': []}
    condensed_information: str = ''
    does_it_needs_a_test: bool = False
    task: str = ''
    test_command: str = ''
    time_to_stop: int = 60  # Every 60 iterations, we stop and evaluate the approach

    sandbox_plugins: list[PluginRequirement] = [
        # NOTE: AgentSkillsRequirement need to go before JupyterRequirement, since
        # AgentSkillsRequirement provides a lot of Python functions,
        # and it needs to be initialized before Jupyter for Jupyter to use those functions.
        AgentSkillsRequirement(),
        JupyterRequirement(),
    ]

    # Add class attribute for tried_direct_code
    tried_direct_code: bool = False

    # Add class attribute for augmented_task
    augmented_task: str = ''

    def __init__(self, llm: LLM, config: AgentConfig):
        """Initialize the Supervisor Agent with an LLM

        Parameters:
        - llm (LLM): The llm to be used by this agent
        """
        llm_config = LLMConfig(
            model='openai/o1-mini', api_key='REDACTED', temperature=1.0
        )
        llm = LLM(llm_config)
        # TODO: Remove this once we have a real AgentConfig
        config = AgentConfig(llm_config='o1-mini')
        super().__init__(llm, config)
        # Set up logger
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.DEBUG)  # Set the logging level
        self.llm_config = llm.config

    def step(self, state: State) -> Action:
        self.logger.debug('Starting step with state: %s', state)
        self.logger.debug('LLM config: %s', self.llm_config)
        last_observation = state.history[-1]
        task, _ = state.get_current_user_intent()
        self.task = task or ''

        # import pdb; pdb.set_trace()
        # Try CodeActAgent first if we haven't tried it yet
        if not self.tried_direct_code:
            prompt = get_prompt(self.task, [], 'initial')
            raw_response = self.get_response(prompt)
            match = re.search(
                r'<augmented_pr_description>(.*?)</augmented_pr_description>',
                raw_response,
                re.DOTALL,
            )
            self.augmented_task = match.group(1).strip('"') if match else self.task
            self.tried_direct_code = True
            return AgentDelegateAction(
                agent='CodeActAgent',
                inputs={
                    'task': self.task,
                    'augmented_task': self.augmented_task,
                    'when_to_stop': self.time_to_stop,
                },
            )

        if not isinstance(last_observation, AgentDelegateObservation):
            raise ValueError('Last observation is not an AgentDelegateObservation')

        if not last_observation.outputs.get('fixed', False):
            trayectory: List[Dict] = last_observation.outputs['trayectory']
            deserialized_trajectory = [
                Message(
                    role=msg_dict['role'],
                    content=[
                        TextContent(text=content_text)
                        for content_text in [
                            msg_dict['content'][0]['text']
                            if isinstance(msg_dict['content'], list)
                            else msg_dict['content']
                        ]
                    ],
                    tool_call_id=msg_dict.get('tool_call_id'),
                    name=msg_dict.get('name'),
                )
                for msg_dict in trayectory
            ]
            # import pdb; pdb.set_trace()
            prompt = get_prompt(self.task, deserialized_trajectory, 'right_track')
            raw_response = self.get_response(prompt)
            match = re.search(r'<answer>(.*?)</answer>', raw_response, re.DOTALL)
            if match and 'yes' in match.group(1).lower():
                return AgentDelegateAction(
                    agent='CodeActAgent',
                    inputs={
                        'task': self.task,
                        'trayectory': trayectory,
                        'when_to_stop': self.time_to_stop,
                    },
                )
            # pdb.set_trace()
            prompt = get_prompt(self.task, deserialized_trajectory, 'refactor')
            raw_response = self.get_response(prompt)
            match = re.search(r'<next_step>(.*?)</next_step>', raw_response, re.DOTALL)
            next_step = match.group(1).strip('"') if match else ''
            self.logger.debug('Suggested approach: %s', next_step)
            return AgentDelegateAction(
                agent='CodeActAgent',
                inputs={
                    'task': self.task,
                    'trayectory': trayectory,
                    'next_step': next_step,
                    'when_to_stop': self.time_to_stop,
                },
            )
        return AgentFinishAction()

    def get_response(self, prompt: str) -> str:
        message = Message(role='user', content=[TextContent(text=prompt)])
        response = self.llm.completion(
            messages=self.llm.format_messages_for_llm(message)
        )
        return response['choices'][0]['message']['content']
