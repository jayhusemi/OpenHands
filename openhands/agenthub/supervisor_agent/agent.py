import logging
from typing import Any, Dict, List, Literal, Union

from openhands.agenthub.supervisor_agent.prompt import (
    TASK_TYPE_ISSUE,
    get_prompt,
)
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.config.llm_config import LLMConfig
from openhands.core.message import Message, TextContent
from openhands.core.utils import json
from openhands.events.action import Action, AgentDelegateAction, AgentFinishAction
from openhands.events.action.agent import AgentRejectAction
from openhands.events.observation.delegate import AgentDelegateObservation
from openhands.llm.llm import LLM


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
    phase: Literal['search', 'summary', 'code'] = 'search'

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

        if len(self.suggested_approaches) == 0:
            self.suggested_approaches = self.get_suggested_approaches(state)
        self.suggested_approach_index += 1

        last_observation = state.history.get_last_observation()
        # At first the history is empty, so we proceed to the SearchAgent
        if isinstance(last_observation, AgentDelegateObservation):
            self.results[self.phase].append(last_observation.outputs.get('output', ''))

        if self.suggested_approach_index < len(self.suggested_approaches):
            # Delegate to the SearcherAgent as we need to gather more information
            return self.delegate_to_agent(
                'SearcherAgent',
                self.task,
                self.suggested_approaches[self.suggested_approach_index].get(
                    'suggested_approach', []
                ),
            )

        if self.phase == 'search':
            condensed_information = self.ask_llm(
                self.task, 'summary', self.results[self.phase]
            )
            if condensed_information and len(condensed_information) > 0:
                first_result = condensed_information[0]
                if first_result.get('summary', '') != '':
                    self.phase = 'summary'
                    self.condensed_information = first_result.get('summary', '')
                else:
                    suggested_approach: str | list[str] = first_result.get(
                        'suggested_approach', []
                    )
                    self.results['search'].append(suggested_approach)
                    return self.delegate_to_agent(
                        'SearcherAgent', self.task, suggested_approach
                    )

        if self.phase == 'summary':
            if not self.does_it_needs_a_test:
                test_check = self.ask_llm(self.task, 'code', self.condensed_information)
                first_check = (
                    test_check[0] if test_check and len(test_check) > 0 else {}
                )
                self.does_it_needs_a_test = (
                    first_check.get('suggested_approach', '') == TASK_TYPE_ISSUE
                )
                self.phase = 'code'
                if self.does_it_needs_a_test:
                    self.current_delegate = 'TesterAgent'
                    return AgentDelegateAction(
                        agent='TesterAgent',
                        inputs={
                            'task': self.task,
                            'summary': self.condensed_information,
                        },
                    )
        if self.phase == 'code':
            if (
                self.does_it_needs_a_test
                and last_observation is not None
                and isinstance(last_observation, AgentDelegateObservation)
            ):
                self.test_command = last_observation.outputs.get('output', '')
                return AgentDelegateAction(
                    agent='CoderAgent',
                    inputs={
                        'task': self.task,
                        'summary': self.condensed_information,
                        'test_command': self.test_command,
                    },
                )

        return AgentFinishAction()

    def get_suggested_approaches(self, state: State):
        self.logger.debug('No suggested approaches found, breaking down task.')
        self.task, _ = state.get_current_user_intent()
        suggested_approaches = self.ask_llm(self.task, 'search')
        self.logger.debug('Suggested approaches: %s', self.suggested_approaches)
        if not suggested_approaches:
            return AgentRejectAction()
        return suggested_approaches

    def delegate_to_agent(
        self, agent_name: str, task: str, suggested_approach: Union[str, List[str]]
    ) -> AgentDelegateAction:
        self.logger.debug(f'Delegating to agent: {agent_name}')
        self.current_delegate = agent_name
        # Join the list of strings with newlines if it's a list
        approach = (
            '\n'.join(suggested_approach)
            if isinstance(suggested_approach, list)
            else suggested_approach
        )
        return AgentDelegateAction(
            agent=agent_name, inputs={'task': task, 'suggested_approach': approach}
        )

    def ask_llm(
        self, task: str, phase: str, search_results: Union[str, List[str]] = ''
    ) -> List[Dict[str, str]]:
        # Format search_results as one item per line if it's a list
        if isinstance(search_results, list):
            search_results = '\n'.join(search_results)
        prompt = get_prompt(task, phase, search_results)
        return self.get_response(prompt)

    def get_response(self, prompt: str) -> List[Dict[str, str]]:
        content = [TextContent(text=prompt)]
        message = Message(role='user', content=content)
        response = self.llm.completion(
            messages=self.llm.format_messages_for_llm(message)
        )
        if isinstance(response, list):
            return json.loads(response[0]['message']['content'])
        return json.loads(response['choices'][0]['message']['content'])
