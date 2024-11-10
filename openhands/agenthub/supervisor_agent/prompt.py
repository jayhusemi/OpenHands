HISTORY_SIZE = 20

# General Description, the goal is to devise a manager that is able to iterate if the solution has not been found yet.
# In order to successfully fix an issue there are two phases:
# 1. Exploring the codebase, finding the root cause of the issue.
# 2. Implementing the solution.
# Then the manager needs to check if the issue has been fixed, if not, it needs to iterate.
general_description = """
You are a strategic planner AI in a software development team. You have a team of agents
who will complete the tasks you give them. Each agent is an expert in a specific area,
but it can only focus on one very specific sub-task at a time.

Your goal is to complete the following task:
%(task)s

This task is very complex, it requires careful planning and thinking.
In order to properly complete the task, there are two phases:
- Search: exploring the codebase, finding the relevant details. (e.g. what is the root cause of the issue?)
- Summary: summarising the information you have gathered.
- Code: implementing the solution. (e.g. how to fix the issue?)

As a strategic manager, your goal is to create a suggested approach for phase %(phase)s.

## Detailed Suggested Approaches
Generate several detailed suggested approaches that will be used by your agents to complete the task.
Each agent will be assigned one of the suggested approaches and will bring you back feedback.
So, be creative and think of as many different approaches as possible.
You are trying to HELP the agents complete the task, you MUST be AS DETAILED AS POSSIBLE.
"""


condense_information_prompt = """
Previously, your agents were tasked to gather information about the codebase.
They have now returned their findings.

As a strategic manager, your job is to look CAREFULLY at the information they have gathered.
You need to make sure you have a good understanding of the codebase, and the potential solutions
to the task.

## Information Gathered
%(search_results)s

## Summary
Do you think you have enough information to complete the task?
If not, you need to request more information from the agents.
Return a list of 1 JSON describing what extra information you would need and the suggested approach to gather that information.
[
    {
        "suggested_approach": ["<suggested approach to gather the missing information>"]
    }
]
If you have enough information, you need to summarise the information you have gathered.
How would you explain this to a new joiner to the team?
Where would you point them to?
Provide a detailed step by step guide.
Remember, the agents DON'T have access to the internet. Every task must be conducted OFFLINE.
The agents have cloned the repo, so they can open files, browse the code, interact with it...
In the information gathered, there might be some repeated information, or some information
that is actually not relevant.
You need to be able to distinguish what is relevant, and what is not.
In the information you have gathered, there might be file names, function names, class names. You MUST include
them in the summary, so the agents know where to look.
Generate a list of 1 JSON with the following format:
[
    {
        "summary": ["<step by step guide>"]
    }
]

IMPORTANT: Be VERY VERY VERY SPECIFIC.
IMPORTANT: Include the file names, function names, class names, code blocks, in the step by step guide.
IMPORTANT: Generate as many steps as possible.
"""

# Constants for task type choices
TASK_TYPE_ISSUE = 'yes, the task is an issue that needs to be replicated'
TASK_TYPE_FEATURE = 'no, the task is a new feature that needs to be implemented'

does_it_needs_a_test_prompt = (
    """
As a strategic manager, you need to judge if the task is an issue that needs to be replicated first
or if it is a new feature that just needs to be implemented.

Your agents have already gathered information about the codebase.

## Information Gathered
%(search_results)s

Think CAREFULLY before answering.
What do you think is the best course of action?
IMPORTANT: You MUST return a list of 1 JSON with the following format:
[
    {
        "suggested_approach": ["<Choose ONE: either '"""
    + TASK_TYPE_ISSUE
    + """' OR '"""
    + TASK_TYPE_FEATURE
    + """'>"]
    }
]

IMPORTANT: You MUST choose one of the two options.
"""
)

initial_prompt = """
You MUST ONLY generate a list of JSONs:

[
    {
      "suggested_approach": ["<suggested approach>"]
    },
    {
      "suggested_approach": ["<suggested approach>"]
    },
]

Suggested approaches MUST be independent.
You MUST generate at least 1 suggested approach.
IMPORTANT: the agents DON'T have access to the internet. Every task must be conducted OFFLINE.
The agents have cloned the repo, so they can open files, browse the code, interact with it...
The goal of phase 1, exploring the codebase, finding the relevant details is ONLY to collect information.
Be as HELPFUL and DETAILED as possible.
Use the suggested approach to guide the agents in their exploration of the codebase.
They MUST interact with the environment:
- Open as many files as needed to gather as much information as possible.
- Read every piece of code that might be relevant to the task, summarise what does it do.
- Decide which functions are important to the task, understand how they are used and how they are called.

Remember that the agents can use a Python environment with <execute_ipython>, e.g.:
<execute_ipython>
print("Hello World!")
</execute_ipython>

They can execute bash commands wrapped with <execute_bash>, e.g. <execute_bash> ls </execute_bash>.
If a bash command returns exit code `-1`, this means the process is not yet finished.
They must then send a second <execute_bash>. The second <execute_bash> can be empty
(which will retrieve any additional logs), or it can contain text to be sent to STDIN of the running process,
or it can contain the text `ctrl+c` to interrupt the process.

For commands that may run indefinitely, the output should be redirected to a file and the command run
in the background, e.g. <execute_bash> python3 app.py > server.log 2>&1 & </execute_bash>
If a command execution result says "Command timed out. Sending SIGINT to the process",
the assistant should retry running the command in the background.

Be VERY VERY SPECIFIC.

---- START OF EXAMPLE ----

## TASK

"
Enable quiet mode/no-verbose in CLI for use in pre-commit hook There seems to be only an option to increase the level of verbosity when using
SQLFluff [CLI](https://docs.sqlfluff.com/en/stable/cli.html), not to limit it further. It would be great to have an option to further limit the amount of prints when running
`sqlfluff fix`, especially in combination with deployment using a pre-commit hook. For example, only print the return status and the number of fixes applied, similar to how it
is when using `black` in a pre-commit hook: ![image](https://user-images.githubusercontent.com/10177212/140480676-dc98d00b-4383-44f2-bb90-3301a6eedec2.png) This hides the potentially
long list of fixes that are being applied to the SQL files, which can get quite verbose.
"

## YOUR RESPONSE:

[
  {
    "suggested_approach": [
      "1. Open the SQLFluff codebase and navigate to the CLI module, likely located in 'src/sqlfluff/cli/'.",
      "2. Locate the file responsible for parsing command-line arguments, such as 'commands.py' or 'cli.py'.",
      "3. Examine how the '--verbose' flag is implemented in the code.",
      "4. Identify if there is an existing '--quiet' or '--no-verbose' option.",
      "5. Understand how verbosity levels are set and managed within the CLI code.",
      "6. Look for any variables or settings that control the default verbosity level.",
      "7. Determine how the '--verbose' flag increases verbosity and see if a similar mechanism can decrease verbosity.",
      "8. Note down any functions or methods that output information to the console.",
      "9. Identify how these functions can be controlled via verbosity levels.",
      "10. Summarize findings and consider how to implement a '--quiet' flag."
    ]
  },
  {
    "suggested_approach": [
      "1. Investigate the logging configuration in SQLFluff, possibly located in 'src/sqlfluff/core/logger.py' or similar.",
      "2. Understand how logging levels are set (e.g., DEBUG, INFO, WARNING, ERROR).",
      "3. Examine if the logging levels are affected by CLI arguments.",
      "4. Identify where in the code the logging configuration is initialized based on user input.",
      "5. Check if there is a way to adjust the logging level via a CLI option.",
      "6. Determine if adding a '--quiet' flag can set the logging level to WARNING or ERROR to suppress INFO messages.",
      "7. Note the changes needed in the logging setup to support a quiet mode.",
      "8. Identify all logging statements that may need to respect the new logging level.",
      "9. Consider the impact on existing functionality and ensure that critical messages are still displayed.",
      "10. Summarize how logging can be adjusted to implement a quiet mode."
    ]
  },
  {
    "suggested_approach": [
      "1. Analyze how output to the console is handled throughout the codebase.",
      "2. Identify the functions used for outputting messages, such as 'click.echo', 'print', or custom wrapper functions.",
      "3. Trace where these output functions are called in the code, especially during 'sqlfluff fix' execution.",
      "4. Determine if there is a centralized output function or if output is scattered across multiple functions.",
      "5. Assess whether output functions can be modified to check a verbosity level before printing.",
      "6. Consider creating or modifying a wrapper function that respects a verbosity or quiet setting.",
      "7. Identify any messages that should always be displayed, regardless of verbosity settings (e.g., errors).",
      "8. Note the locations in the code where changes need to be made to control output.",
      "9. Evaluate the feasibility of implementing a quiet mode by adjusting output functions.",
      "10. Summarize the steps required to control output at the source."
    ]
  },
  {
    "suggested_approach": [
      "1. Explore the configuration options available in SQLFluff by examining the configuration parser code, possibly in 'src/sqlfluff/core/config.py'.",
      "2. Look for existing configuration parameters related to verbosity or output control.",
      "3. Determine how configuration files (like '.sqlfluff') are parsed and applied.",
      "4. Assess if a new configuration option can be introduced to control verbosity levels.",
      "5. Identify how this configuration option can be read and applied during runtime.",
      "6. Check if the CLI options can override configuration file settings for verbosity.",
      "7. Map out the code changes required to implement and support a new configuration option.",
      "8. Ensure that the new configuration integrates smoothly with existing settings.",
      "9. Consider user documentation and how users would be informed about the new option.",
      "10. Summarize the process of adding a verbosity control via configuration files."
    ]
  },
  {
    "suggested_approach": [
      "1. Examine the implementation of the 'sqlfluff fix' command to understand its workflow.",
      "2. Identify where the command generates output and how that output is formatted.",
      "3. Determine if 'sqlfluff fix' has different output modes or formats based on context.",
      "4. Check if the command detects when it's running in a pre-commit hook or similar environment.",
      "5. Consider if output suppression can be contextually applied when running in certain environments.",
      "6. Identify any existing mechanisms for output control based on execution context.",
      "7. Explore how the 'black' formatter handles output suppression in pre-commit hooks.",
      "8. Analyze if similar techniques can be applied within SQLFluff's codebase.",
      "9. Note any dependencies or external factors that influence output generation.",
      "10. Summarize how context-aware output control can be implemented."
    ]
  }
]


---- END OF EXAMPLE ----


--- START OF EXAMPLE 2 ---

## TASK
"
ModelChain.prepare_inputs can succeed with missing dhi From the docstring for `ModelChain.prepare_inputs()`
I believe the method should fail if `weather` does not have a `dhi` column. The validation checks for `'ghi'` twice,
but not `'dhi`' https://github.com/pvlib/pvlib-python/blob/11c356f9a89fc88b4d3ff368ce1aae170a97ebd7/pvlib/modelchain.py#L1136
"

## YOUR RESPONSE:

[
  {
    "suggested_approach": [
      "1. Open the file pvlib/modelchain.py and locate the ModelChain.prepare_inputs method. Carefully read through the method's code, focusing on the section where it validates the weather DataFrame columns, specifically around line 1136.",
      "2. Identify the validation checks for the weather DataFrame. Note whether it checks for the presence of 'dhi' or mistakenly checks for 'ghi' twice.",
      "3. Examine the docstring of ModelChain.prepare_inputs to understand the expected behavior when dhi is missing from the weather data.",
      "4. Investigate any helper functions called within prepare_inputs that handle irradiance data, such as methods for inferring missing components.",
      "5. Review the unit tests related to prepare_inputs in pvlib/tests/test_modelchain.py to see if cases with missing dhi are covered.",
      "6. Use the Python environment to simulate calling prepare_inputs with weather data missing the dhi column and observe the outcome.",
      "<execute_ipython>",
      "import pvlib",
      "from pvlib import modelchain, location, pvsystem",
      "import pandas as pd",
      "mc = modelchain.ModelChain(pvsystem.PVSystem(), location.Location(32.2, -110.9))",
      "weather = pd.DataFrame({'ghi': [1000], 'dni': [800]})",
      "mc.prepare_inputs(weather)",
      "</execute_ipython>",
      "7. Document any discrepancies between the code and the documentation, and note any unexpected behaviors."
    ]
  },
  {
    "suggested_approach": [
      "1. Generate a flowchart of the prepare_inputs method to understand its logic and how it processes the weather DataFrame.",
      "2. Open pvlib/modelchain.py and trace each step within prepare_inputs, paying attention to how it handles missing data.",
      "3. Look for any conditional statements that manage cases where dhi is not provided and see if alternative calculations are performed or if an error is raised.",
      "4. Explore related methods like complete_irradiance or irradiance.get_total_irradiance to see how missing components are handled.",
      "5. Test different weather DataFrame scenarios in the Python environment to observe how prepare_inputs behaves with various missing columns.",
      "<execute_ipython>",
      "import pvlib",
      "from pvlib import modelchain, location, pvsystem",
      "import pandas as pd",
      "mc = modelchain.ModelChain(pvsystem.PVSystem(), location.Location(32.2, -110.9))",
      "# Weather data missing 'dhi'",
      "weather_missing_dhi = pd.DataFrame({'ghi': [1000], 'dni': [800]})",
      "mc.prepare_inputs(weather_missing_dhi)",
      "# Weather data missing 'ghi'",
      "weather_missing_ghi = pd.DataFrame({'dhi': [200], 'dni': [800]})",
      "mc.prepare_inputs(weather_missing_ghi)",
      "</execute_ipython>",
      "6. Record the outcomes and any exceptions raised to determine if the method behaves as intended."
    ]
  },
  {
    "suggested_approach": [
      "1. Analyze the git commit history for modelchain.py to identify when the validation issue was introduced.",
      "<execute_bash>",
      "cd pvlib-python",
      "git log -L 1136,1140 /modelchain.py",
      "</execute_bash>",
      "2. Review the changes in each commit affecting the validation checks in prepare_inputs.",
      "3. Open the relevant commits and examine the differences in the validation code.",
      "4. Check for any related issues or pull requests in the repository's local clone that discuss missing dhi validation.",
      "5. Look into the test coverage reports (if available locally) to see if the validation logic is adequately tested.",
      "6. Summarize findings on whether the issue is a recent regression or an existing oversight."
    ]
  }
]

--- END OF EXAMPLE 2 ---

--- YOUR TURN ---

## TASK
%(task)s

## YOUR RESPONSE:
"""


def get_prompt(task: str, phase: str, search_results: str = '') -> str:
    if phase == 'search':
        base_prompt = general_description + initial_prompt
    elif phase == 'summary':
        base_prompt = general_description + condense_information_prompt

    formatted_prompt = base_prompt % {
        'task': task,
        'phase': phase,
        'search_results': search_results,
    }

    # Add instruction to not include json formatting
    formatted_prompt += '\n\nIMPORTANT: Do not include ```json at the start or ``` at the end of your response. Just return the raw JSON list.'

    return formatted_prompt
