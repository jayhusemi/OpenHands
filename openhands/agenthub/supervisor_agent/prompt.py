from typing import Dict, List

from openhands.core.utils import json

HISTORY_SIZE = 20

# General Description
general_description = """
You are a strategic manager AI in a software development team. You MUST think CAREFULLY how to complete the task assigned to you.
You MUST think on a HIGHER LEVEL view always.

You've been given the following task:
%(task)s

As a strategic manager, you create a plan with different sub-tasks and delegate the tasks to your team.
At your disposal, you have a team of agents who will complete tasks for you. However, those agents only focus on the details.
They CANNOT see the big picture.
They need you to define self-contained tasks, that are easy for them to understand and complete.

"""

# Initial Prompt
initial_prompt = """
## Plan
Your goal is to create a high-level plan, a list of subtasks that will bring you closer to the completion of the task. Remember to think
CAREFULLY about how to complete the task. With each subtask, you MUST provide a "suggested approach".
Think, step by step, how you would complete the subtask. Then provide that as the suggested approach.
Try to be as detailed as possible, your goal is to HELP the agent finish the subtask as soon as possible.

You MAY provide a list of "important details" for each subtask. These are details that the agent MUST consider when completing the subtask.

ONLY generate tasks that are necessary to complete the task.

You MUST ONLY generate a list of JSONs:

[
    {
      "task": "<Task 1 name>",
      "suggested_approach": "<suggested approach>",
      "important_details": "<important details>"
    },
    {
      "task": "<Task 2 name>",
      "suggested_approach": "<suggested approach>",
      "important_details": "<important details>"
    },
    {
      "task": "<Task 3 name>",
      "suggested_approach": "<suggested approach>",
      "important_details": "<important details>"
    },
]

The tasks MUST be generated in order, they MUST NOT depend on future tasks or previous tasks. They MUST be independent.
You MUST generate at least 1 task.

For example:
User prompt:

"
Enable quiet mode/no-verbose in CLI for use in pre-commit hook There seems to be only an option to increase the level of verbosity when using
SQLFluff [CLI](https://docs.sqlfluff.com/en/stable/cli.html), not to limit it further. It would be great to have an option to further limit the amount of prints when running
`sqlfluff fix`, especially in combination with deployment using a pre-commit hook. For example, only print the return status and the number of fixes applied, similar to how it
is when using `black` in a pre-commit hook: ![image](https://user-images.githubusercontent.com/10177212/140480676-dc98d00b-4383-44f2-bb90-3301a6eedec2.png) This hides the potentially
long list of fixes that are being applied to the SQL files, which can get quite verbose.
"

Your response:

[
    {
        "task": "Research SQLFluff CLI verbosity options",
        "suggested_approach": "Investigate the current SQLFluff CLI documentation and source code to understand how verbosity levels are currently implemented. Identify if there are any existing flags or settings that can be adjusted to reduce verbosity.",
        "important_details": "Focus on the 'fix' command and any related verbosity settings. Document any findings that could be useful for implementing a quiet mode."
    },
    {
        "task": "Design a quiet mode feature for SQLFluff CLI",
        "suggested_approach": "Based on the research findings, design a new feature that allows users to enable a quiet mode. This mode should minimize output to only essential information such as return status and number of fixes applied.",
        "important_details": "Ensure the design is compatible with existing CLI options and does not interfere with other functionalities."
    },
    {
        "task": "Implement the quiet mode feature",
        "suggested_approach": "Modify the SQLFluff CLI codebase to add the new quiet mode feature. Implement the necessary changes in the code to support this feature and ensure it can be activated via a command-line flag.",
        "important_details": "Write unit tests to verify that the quiet mode works as expected and does not affect other CLI functionalities."
    },
    {
        "task": "Test the quiet mode feature",
        "suggested_approach": "Conduct thorough testing of the new quiet mode feature in various scenarios, including its use in a pre-commit hook. Ensure that it behaves as expected and provides the desired level of output reduction.",
        "important_details": "Test with different verbosity levels to ensure compatibility and check for any edge cases that might cause unexpected behavior."
    },
    {
        "task": "Document the new feature",
        "suggested_approach": "Update the SQLFluff CLI documentation to include information about the new quiet mode feature. Provide examples of how to use it and explain its benefits.",
        "important_details": "Ensure the documentation is clear and easy to understand for users who may not be familiar with the technical details."
    }
]
"""

adjustment_prompt = """

    This is the current active plan that your subordinates are working on:
    %(milestones)s

    And this is the current subtask that your subordinates are working on:
    ## Current subtask
    subtask: %(milestone_task)s
    Suggested Approach: %(milestone_suggested_approach)s
    Important Details: %(milestone_important_details)s

    However, it seems that the current subtask is not being completed successfully.
    Because of the following reason: %(reason)s

    You have the following contextual information that has been gathered up to this point.
    This information MIGHT help you adjust the plan:
    %(summary)s

    ## Task
    As a strategic manager, you must reflect on the failed subtask and decide on the necessary adjustments. Consider the following:

    1. Analyze the reason for failure and determine if the suggested approach or important details need modification.
    2. Decide if the failed subtask should be split into smaller, more manageable tasks.
    3. Consider if new plan need to be added to address any gaps in the plan.
    4. Update the remaining plan to ensure the overall plan remains feasible and effective.

    You MUST NOT change the task you were given.

    You MUST make changes to the current subtask or to the ones AFTER. In NO case you can change the ones BEFORE.
    Generate ONLY a list of JSONs. Do NOT generate any markdown or comments.
    """


def get_initial_prompt(task: str) -> str:
    """Gets the prompt for the planner agent.

    Formatted with the most recent action-observation pairs, current task, and hint based on last action

    Parameters:
    - state (State): The state of the current agent

    Returns: with historical values
    """
    return (general_description + initial_prompt) % {
        'task': task,
    }


def adjust_milestones(
    milestones: List[Dict],
    subtask: Dict[str, str],
    reason: str,
    summary: str,
    task: str,
) -> str:
    """Adjusts the milestones based on a failed subtask and its reason.

    Parameters:
    - milestones (List[Dict]): The current list of milestones.
    - subtask (Dict): The subtask that was not completed successfully.
    - reason (str): The reason provided for the failure.
    - summary (str): A summary of everything up to this point.
    - task (str): The user's task.

    Returns: A prompt for the strategic manager agent to self-reflect and adjust the milestones.
    """
    # Extract values from the subtask dictionary
    milestone_task = subtask['task']
    milestone_suggested_approach = subtask['suggested_approach']
    milestone_important_details = subtask['important_details']

    # Use the extracted values in the string formatting
    return (general_description + adjustment_prompt) % {
        'milestones': json.dumps(milestones),
        'reason': reason,
        'summary': summary,
        'task': task,
        'milestone_task': milestone_task,
        'milestone_suggested_approach': milestone_suggested_approach,
        'milestone_important_details': milestone_important_details,
    }
