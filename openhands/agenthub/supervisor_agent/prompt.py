from typing import Optional

from openhands.core.message import Message, TextContent

HISTORY_SIZE = 20

# General Description, the goal is to devise a manager that is able to iterate if the solution has not been found yet.
# In order to successfully fix an issue there are two phases:
# 1. Exploring the codebase, finding the root cause of the issue.
# 2. Implementing the solution.
# Then the manager needs to check if the issue has been fixed, if not, it needs to iterate.
general_description = """
You are a helpful assistant that provides a DETAILED step-by-step plan.
"""

high_level_task = """

%(task)s

Can you create a step-by-step plan on how to fix the issue described in <pr_description>?
Feel free to generate as many steps as necessary to fix the issue described in <pr_description>.

Make the plan in a way that the changes are minimal and only affect non-tests files in the /workspace directory.
Your thinking should be thorough and so it's fine if it's very long.
Generate bullet points, highlevel steps. This means do NOT generate code snippets.

EXAMPLE:

<steps>
- 1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.
- 2. Create a script to reproduce the error and execute it with `python <filename.py>` using the BashTool, to confirm the error
- 3. Edit the sourcecode of the repo to resolve the issue
- 4. Rerun your reproduce script and confirm that the error is fixed!
- 5. Think about edgecases and make sure your fix handles them as well
</steps>

END OF EXAMPLE

<IMPORTANT>
- Encapsulate your suggestions in between <steps> and </steps> tags.
- Documentation has been taken into account, so you should not mention it in any way!
- Testing has been taken into account, so you should not mention it in any way!
- Generate ONLY high-level steps.
- One of those steps must be to create a script to reproduce the error and execute it with `python <filename.py>` using the BashTool, to confirm the error
- Be CONCISE.
</IMPORTANT>

Your turn!
"""

right_track_prompt = """

I am trying to fix the issue described in the <pr_description>.
I kept track of everything I did in the <pr_approach>

<pr_approach>
%(approach)s
</pr_approach>

As a reminder, this is the <pr_description>:

%(task)s

The plan I followed in my <pr_approach> is described in the <plan> tag:

<plan>
%(plan)s
</plan>

Can you suggest me a new plan to fix the issue described in the <pr_description>?
Pay attention at the errors I faced in the <pr_approach>. Extract information from the errors to shape a new plan.
One of initial steps would be to see if the issue is still present, if it is not, then it should expand on the edgecases.

EXAMPLE:

<steps>
- 1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.
- 2. Create a script to reproduce the error and execute it with `python <filename.py>` using the BashTool, to confirm the error
- 3. Edit the sourcecode of the repo to resolve the issue
- 4. Rerun your reproduce script and confirm that the error is fixed!
- 5. Think about edgecases and make sure your fix handles them as well
</steps>

END OF EXAMPLE

<IMPORTANT>
- Encapsulate your suggestions in between <steps> and </steps> tags.
- Documentation has been taken into account, so you should not mention it in any way!
- Testing has been taken into account, so you should not mention it in any way!
- Generate ONLY high-level steps.
- The second step must be to create a script to reproduce the error and execute it with `python <filename.py>` using the BashTool, to confirm the error
- The goal is to fix the issue described in <pr_description> with the MINIMAL changes to non-tests files in the /workspace directory.
- Be CONCISE.
- Be CREATIVE, your plan MUST be DIFFERENT from the one described in <plan>.
</IMPORTANT>

Your turn!
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
    prompt_type: str = 'initial',
    trajectory: Optional[list[Message]] = None,
    plan: str = '',
    requirements: str = '',
) -> str:
    """Format and return the appropriate prompt based on prompt_type.

    Args:
        task: The task description
        trajectory: List of Message objects containing conversation history
        prompt_type: Type of prompt to return ("initial" or "refactor")
        plan: The augmented task description
    Returns:
        Formatted prompt string
    """
    if trajectory is None:
        trajectory = []
    # If approach is a conversation history, format it
    approach = format_conversation(trajectory)

    # Select the appropriate prompt template
    template = {
        'right_track': right_track_prompt,
        'refactor': refactor_prompt,
        'critical': critical_prompt,
        'high_level_task': high_level_task,
    }[prompt_type]

    return general_description + template % {
        'task': task,
        'approach': approach,
        'plan': plan,
        'requirements': requirements,
    }
