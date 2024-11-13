import logging
import re
from typing import Any, Dict, List

from openhands.agenthub.supervisor_agent.prompt import code_act_agent_prompt, get_prompt
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.config.llm_config import LLMConfig
from openhands.core.message import Message, TextContent
from openhands.events.action import Action, AgentDelegateAction, AgentFinishAction
from openhands.events.observation.delegate import AgentDelegateObservation
from openhands.events.observation.observation import Observation
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
    phase: int = 0

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
            model='openai/o1-preview', api_key='REDACTED', temperature=1.0
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
        last_observation: Observation | None = None
        for event in reversed(state.history):
            if isinstance(event, Observation):
                last_observation = event
                break

        task, _ = state.get_current_user_intent()
        self.task = task or ''

        if self.phase == 0:
            self.phase += 1
            prompt = get_prompt(self.task, None, 'high_level_task')
            return AgentDelegateAction(
                agent='CodeActAgent',
                inputs={
                    'task': prompt,
                    'when_to_stop': 1,
                },
            )

        if not isinstance(last_observation, AgentDelegateObservation):
            return AgentFinishAction()

        if not last_observation.outputs.get('fixed', False):
            response: str = last_observation.outputs['response']
            match = re.search(
                r'<requirements>(.*?)</requirements>', str(response), re.DOTALL
            )
            self.requirements = match.group(1).strip('"') if match else ''

            self.phase += 1
            prompt = get_prompt(
                self.task, None, 'initial', requirements=self.requirements
            )
            raw_response = self.get_response(prompt)
            match = re.search(
                r'<steps>(.*?)</steps>',
                raw_response,
                re.DOTALL,
            )
            steps = match.group(1).strip('"') if match else self.task

            return AgentDelegateAction(
                agent='CodeActAgent',
                inputs={
                    'task': self.task,
                    'next_step': code_act_agent_prompt % {'steps': steps},
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
