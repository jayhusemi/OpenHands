import logging
from typing import Any, Dict, List, Literal, Union

from openhands.agenthub.supervisor_agent.prompt import (
    TASK_TYPE_ISSUE,
    get_prompt,
)
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.message import Message, TextContent
from openhands.core.schema.action import ActionType
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
    does_it_needs_a_test: str = ''
    task: str = ''
    phase: Literal['search', 'summary', 'code'] = 'search'

    def __init__(self, llm: LLM, config: AgentConfig):
        """Initialize the Supervisor Agent with an LLM

        Parameters:
        - llm (LLM): The llm to be used by this agent
        """
        super().__init__(llm, config)
        # Set up logger
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.DEBUG)  # Set the logging level
        self.llm_config = llm.config

    def step(self, state: State) -> Action:
        self.logger.debug('Starting step with state: %s', state)
        self.logger.debug('LLM config: %s', self.llm_config)

        if not self.suggested_approaches:
            self.suggested_approaches = self.get_suggested_approaches(state)
        self.suggested_approach_index += 1

        last_observation = state.history.get_last_observation()
        if (
            isinstance(last_observation, AgentDelegateObservation)
            and last_observation.outputs.get('action', '') == ActionType.FINISH
        ):
            self.results[self.phase].append(last_observation.outputs.get('output', ''))

        if len(self.results[self.phase]) < len(self.suggested_approaches):
            # Delegate to the SearcherAgent as we need to gather more information
            return self.delegate_to_agent(
                'SearcherAgent',
                self.task,
                self.suggested_approaches[self.suggested_approach_index].get(
                    'suggested_approach', []
                ),
            )

        if self.phase == 'search':
            # We don't change the phase until we have the condensed information
            condensed_information = self.ask_llm(
                self.task, '2', json.dumps(self.results['search'])
            )[0]
            if condensed_information.get('summary', '') != '':
                self.phase = 'summary'
                self.condensed_information = condensed_information.get('summary', '')
            else:
                suggested_approach: str | list[str] = condensed_information.get(
                    'suggested_approach', []
                )
                self.results['search'].append(suggested_approach)
                return self.delegate_to_agent(
                    'SearcherAgent', self.task, suggested_approach
                )

        if self.phase == 'summary':
            # Now we have to judge if this issue requires a test or not before fixing it
            does_it_needs_a_test = self.ask_llm(
                self.task, 'code', self.condensed_information
            )[0]
            if does_it_needs_a_test.get('suggested_approach', '') == TASK_TYPE_ISSUE:
                self.phase = 'code'
            else:
                self.phase = 'code'

        # WIP: Implement the code phase

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
        self, task: str, phase: str, search_results: str = ''
    ) -> List[Dict[str, str]]:
        prompt = get_prompt(task, phase, search_results)
        return self.get_response(prompt)

    def get_response(self, prompt: str) -> List[Dict[str, str]]:
        content = [TextContent(text=prompt)]
        message = Message(role='user', content=content)
        response = self.llm.completion(
            messages=self.llm.format_messages_for_llm(message)
        )
        return json.loads(response['choices'][0]['message']['content'])
