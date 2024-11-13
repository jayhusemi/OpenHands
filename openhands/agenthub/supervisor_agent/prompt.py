from typing import Optional

from openhands.core.message import Message, TextContent

HISTORY_SIZE = 20

# General Description, the goal is to devise a manager that is able to iterate if the solution has not been found yet.
# In order to successfully fix an issue there are two phases:
# 1. Exploring the codebase, finding the root cause of the issue.
# 2. Implementing the solution.
# Then the manager needs to check if the issue has been fixed, if not, it needs to iterate.
general_description = """
You are a helpful assistant that provides a detailed step-by-step plan.
"""
side_effects_description = """
You are a helpful assistant that creative insights into the side-effects of changes made.

%(approach)s

Imagine that the changes described in <pr_description> have been implemented.
Now this feature is being used. During the usage of this feature, what are the parts of the codebase that could be affected?
Your thinking should be thorough and so it's fine if it's very long.
ALWAYS output all your reasoning, be as detailed as possible.

<IMPORTANT>
- Documentation has been taken into account, so you should not mention it in any way!
- Testing has been taken into account, so you should not mention it in any way!
- Be aware of consistency issues!
- Provide ONLY the related functions. (e.g. If the <pr_description> mentions the write function, then generate the read function).
- Encapsulate your suggestions in between <suggestions> and </suggestions> tags.
</IMPORTANT>

EXAMPLE:
<pr_description>
The changes require to change how the data is stored.
</pr_description>
After implementing those changes:
- The parser functions that read the data might need to be updated to adapt to the new format.

END OF EXAMPLE
"""

high_level_task = """

%(task)s

Can you create a summary with all the functional and non-functional requirements for the task described in <pr_description>?

<IMPORTANT>
- Encapsulate your suggestions in between <requirements> and </requirements> tags.
- Documentation has been taken into account, so you should not mention it in any way!
- Testing has been taken into account, so you should not mention it in any way!
- Do NOT consider performance implications
</IMPORTANT>
"""

initial_prompt = """
I am trying to fix the following issue:

%(task)s

I have already thought out the functional and non-functional requirements for the task described in <pr_description>:

<requirements>
%(requirements)s
</requirements>

create a step-by-step plan broken down into phases for how to implement this using requirements mentioned in <requirements>.

Your thinking should be thorough and so it's fine if it's very long.

Documentation has been taken into account, so you should not repeat it in the <steps>.
I've already taken care of all changes to any of the test files described in the <pr_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!

<IMPORTANT>
- Encapsulate your suggestions in between <steps> and </steps> tags.
- One step MUST be about reproducing the issue with a simple script, no pytest!
- The goal is to fix the issue with the MINIMAL changes to non-tests files in the /workspace directory.
</IMPORTANT>

REMEMBER: the idea is to fix the issue with the MINIMAL changes to non-tests files in the /workspace directory.
"""

code_act_agent_prompt = """

Can you help me implement the necessary changes to the repository so that the requirements specified in the <pr_description> are met?
I've already taken care of all changes to any of the test files described in the <pr_description>. This means you DON'T have to modify the testing logic or any of the tests in any way!
Your task is to make the minimal changes to non-tests files in the /workspace directory to ensure the <pr_description> is satisfied.
Follow the steps described in <steps> to resolve the issue:

<steps>
%(steps)s
</steps>

<IMPORTANT>
- When reproducing the issue, use a simple Python script and directly examine its output instead of pytest.
</IMPORTANT>

Your turn!
"""

right_track_prompt = """

I am trying to fix the issue described in the <pr_description> following the steps described in the <pr_description>
I keep track of everything I did in the <pr_approach>

<pr_approach>
%(approach)s
</pr_approach>

Take a step back and reconsider everything I have done in the <pr_approach>.
Your thinking should be thorough and so it's fine if it's very long.
Can you help me identify if I am on the right track?

<IMPORTANT>
- If there are many code changes, I am probably not on the right track.
- Only reply with yes or no enclosed in between <answer> and </answer> tags
</IMPORTANT>
"""

refactor_prompt = """
The assistant is super CREATIVE always thinks of different ways of approaching the problem.

I am trying to fix the issue described in the <pr_description> following the steps described in the <pr_description>
I keep track of everything I did in the <pr_approach>

<pr_approach>
%(approach)s
</pr_approach>

Take a step back and reconsider everything I have done in the <pr_approach>.
The idea is to make the minimal changes to non-tests files in the /workspace directory to ensure the <pr_description> is satisfied.
I believe my approach is not the best one, can you suggest what my INMEDIATE next step should be? (You can suggest to revert changes and try to do something else)
Your thinking should be thorough and so it's fine if it's very long.
if possible suggest ONLY code changes and the reasoning behind those changes.
Do not use assertive language, use the language of a suggestion.
REMEMBER: I might have written too many lines of code, so it might be better to discard those changes and start again.

<IMPORTANT>
- Reply with the suggested approach enclosed in between <next_step> and </next_step> tags
</IMPORTANT>
"""

critical_prompt = """
The assistant is super CREATIVE, it considers every possible scenario that is DIFFERENT from the ones described in the <pr_description>.

I believe I have fixed the issue described in the <pr_description> following the steps described in the <pr_approach>
<pr_approach>
%(approach)s
</pr_approach>

After fixing the issue, there might be some side-effects that we need to consider.
(e.g. if we fix the way data is written, then we might need to modify the way data is read)
Your thinking should be thorough and so it's fine if it's very long.

<IMPORTANT>
- Only reply with ONE side-effect enclosed in between <next_step> and </next_step> tags starting with the phrase "Have you considered..."
- If you thing everything is covered, just reply with "everything is covered" enclosed in between <next_step> and </next_step> tags
</IMPORTANT>
"""


def format_conversation(trajectory: Optional[list[Message]] = None) -> str:
    """Format a conversation history into a readable string.

    Args:
        trajectory: List of Message objects containing conversation turns

    Returns:
        Formatted string representing the conversation
    """
    if trajectory is None:
        trajectory = []
    formatted_parts = []

    for message in trajectory:
        role = message.role
        # Join all TextContent messages together
        content_text = ' '.join(
            item.text for item in message.content if isinstance(item, TextContent)
        )

        if content_text.strip():  # Only add non-empty content
            formatted_parts.append(f'{role}: {content_text}\n')

    return '\n'.join(formatted_parts)


def get_prompt(
    task: str,
    trajectory: Optional[list[Message]] = None,
    prompt_type: str = 'initial',
    augmented_task: str = '',
    requirements: str = '',
) -> str:
    """Format and return the appropriate prompt based on prompt_type.

    Args:
        task: The task description
        trajectory: List of Message objects containing conversation history
        prompt_type: Type of prompt to return ("initial" or "refactor")
        augmented_task: The augmented task description
    Returns:
        Formatted prompt string
    """
    if trajectory is None:
        trajectory = []
    # If approach is a conversation history, format it
    approach = format_conversation(trajectory)

    # Select the appropriate prompt template
    template = {
        'initial': initial_prompt,
        'right_track': right_track_prompt,
        'refactor': refactor_prompt,
        'critical': critical_prompt,
        'high_level_task': high_level_task,
    }[prompt_type]

    return general_description + template % {
        'task': task,
        'approach': approach,
        'augmented_pr_description': augmented_task,
        'requirements': requirements,
    }
