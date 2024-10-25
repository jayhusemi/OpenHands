import re

from openhands.controller.action_parser import (
    ActionParser,
    ResponseParser,
)
from openhands.events.action import (
    Action,
    AgentFinishAction,
    CmdRunAction,
    IPythonRunCellAction,
    MessageAction,
)


class SearcherAgentResponseParser(ResponseParser):
    """Parser action:
    - CmdRunAction(command) - bash command to run
    - IPythonRunCellAction(code) - IPython code to run
    - MessageAction(content) - Message action to run (e.g. ask for clarification)
    - AgentFinishAction() - end the interaction
    """

    def __init__(self):
        # Need pay attention to the item order in self.action_parsers
        super().__init__()
        self.action_parsers = [
            SearcherAgentActionParserFinish(),
            SearcherAgentActionParserCmdRun(),
            SearcherAgentActionParserIPythonRunCell(),
        ]
        self.default_parser = SearcherAgentActionParserMessage()

    def parse(self, response) -> Action:
        action_str = self.parse_response(response)
        return self.parse_action(action_str)

    def parse_response(self, response) -> str:
        action = response.choices[0].message.content
        if action is None:
            return ''
        for lang in ['bash', 'ipython', 'browse']:
            # special handling for DeepSeek: it has stop-word bug and returns </execute_ipython instead of </execute_ipython>
            if f'</execute_{lang}' in action and f'</execute_{lang}>' not in action:
                action = action.replace(f'</execute_{lang}', f'</execute_{lang}>')

            if f'<execute_{lang}>' in action and f'</execute_{lang}>' not in action:
                action += f'</execute_{lang}>'
        if '<file_edit' in action and '</file_edit>' not in action:
            action += '</file_edit>'
        return action

    def parse_action(self, action_str: str) -> Action:
        for action_parser in self.action_parsers:
            if action_parser.check_condition(action_str):
                return action_parser.parse(action_str)
        return self.default_parser.parse(action_str)


class SearcherAgentActionParserFinish(ActionParser):
    """Parser action:
    - AgentFinishAction() - end the interaction
    """

    def __init__(
        self,
    ):
        self.finish_command = None

    def check_condition(self, action_str: str) -> bool:
        self.finish_command = re.search(r'<finish>.*</finish>', action_str, re.DOTALL)
        return self.finish_command is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.finish_command is not None
        ), 'self.finish_command should not be None when parse is called'
        output = action_str.replace(self.finish_command.group(0), '').strip()
        outputs = {'output': output}
        return AgentFinishAction(outputs=outputs)


class SearcherAgentActionParserCmdRun(ActionParser):
    """Parser action:
    - CmdRunAction(command) - bash command to run
    - AgentFinishAction() - end the interaction
    """

    def __init__(
        self,
    ):
        self.bash_command = None

    def check_condition(self, action_str: str) -> bool:
        self.bash_command = re.search(
            r'<execute_bash>(.*?)</execute_bash>', action_str, re.DOTALL
        )
        return self.bash_command is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.bash_command is not None
        ), 'self.bash_command should not be None when parse is called'
        thought = action_str.replace(self.bash_command.group(0), '').strip()
        # a command was found
        command_group = self.bash_command.group(1).strip()
        if command_group.strip() == 'exit':
            return AgentFinishAction(thought=thought)
        return CmdRunAction(command=command_group, thought=thought)


class SearcherAgentActionParserIPythonRunCell(ActionParser):
    """Parser action:
    - IPythonRunCellAction(code) - IPython code to run
    """

    def __init__(
        self,
    ):
        self.python_code = None
        self.jupyter_kernel_init_code: str = 'from agentskills import *'

    def check_condition(self, action_str: str) -> bool:
        self.python_code = re.search(
            r'<execute_ipython>(.*?)</execute_ipython>', action_str, re.DOTALL
        )
        return self.python_code is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.python_code is not None
        ), 'self.python_code should not be None when parse is called'
        code_group = self.python_code.group(1).strip()
        thought = action_str.replace(self.python_code.group(0), '').strip()
        return IPythonRunCellAction(
            code=code_group,
            thought=thought,
            kernel_init_code=self.jupyter_kernel_init_code,
        )


class SearcherAgentActionParserMessage(ActionParser):
    """Parser action:
    - MessageAction(content) - Message action to run (e.g. ask for clarification)
    """

    def __init__(
        self,
    ):
        pass

    def check_condition(self, action_str: str) -> bool:
        # We assume the LLM is GOOD enough that when it returns pure natural language
        # it wants to talk to the user
        return True

    def parse(self, action_str: str) -> Action:
        return MessageAction(content=action_str, wait_for_response=True)
