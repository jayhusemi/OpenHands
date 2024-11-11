from openhands.core.message import Message, TextContent

HISTORY_SIZE = 20

# General Description, the goal is to devise a manager that is able to iterate if the solution has not been found yet.
# In order to successfully fix an issue there are two phases:
# 1. Exploring the codebase, finding the root cause of the issue.
# 2. Implementing the solution.
# Then the manager needs to check if the issue has been fixed, if not, it needs to iterate.
general_description = """
You are a helpful assistant that can provides DETAILED guidance on how to fix an issue in a codebase.
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
</IMPORTANT>

EXAMPLE:
<pr_description>
The changes require to change how the data is stored.
</pr_description>
After implementing those changes:
- The parser functions that read the data might need to be updated to adapt to the new format.
"""

initial_prompt = """
I am trying to fix the following issue:

%(task)s

Try to imagine with all details how would you fix the <pr_description>. What is the root cause of the issue?
Consider opposite scenarios (eg. if the <pr_description> is writing to a file, consider what happens when the file is read).
Consider edge cases (eg. what if the file doesn't exist?).

I've already taken care of all changes to any of the test files described in the <pr_description>. This means you DON'T have to think about the testing logic or any of the tests in any way!
The idea is to make the minimal changes to non-tests files in the /workspace directory to ensure the <pr_description> is satisfied.

How would you fix the issue described in the <pr_description> with the least amount of steps? Generate the augmented <pr_description> with the least amount of steps to fix the issue in between <augmented_pr_description> and </augmented_pr_description> tags.
Each step MUST be very detailed as to why is needed.
Your thinking should be thorough and so it's fine if it's very long.
Be as detailed as possible.

Documentation has been taken into account, so you should not repeat it in the <augmented_pr_description>.
Testing has been taken into account, so you should not repeat it in the <augmented_pr_description>. You can create new tests, but never use existing tests.
ALWAYS output all your reasoning, be as detailed as possible.

Follow this structure:
1. As a first step, it might be a good idea to explore the repo to familiarize yourself with its structure.
  - Files to explore, parts of the codebase I should focus on, keywords to look for...
  - Extended reasoning...
2. Create a script to reproduce the error and execute it to confirm that the error is reproducible
  - Ensure that when executing the script, you get the error described in the <pr_description>
  - Suggested code to reproduce the error, keeping in mind the side-effects described in the previous step, so that the error and side-effects are reproducible
  - Extended reasoning...
3. Edit the sourcecode of the repo to resolve the issue
  - Suggest what files to change and code SUGGESTIONS. Trying to fix the issue in <pr_description> with the least amount of changes.
  - Keep in mind for the code suggestions that I might need to change some other functions to prevent the side-effects described in the previous steps.
  - Extended reasoning...
4. Rerun your reproduce script and confirm that the error is fixed!

<IMPORTANT>
One step MUST be to recreate the issue and ensure that the error log is the same as the one described in the <pr_description>.
</IMPORTANT>

Example:
<augmented_pr_description>

</augmented_pr_description>

REMEMBER: you ARE ONLY suggesting steps to fix the issue, do NOT be assertive, use the language of a suggestion.
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


def format_conversation(trajectory: list[Message]) -> str:
    """Format a conversation history into a readable string.

    Args:
        trajectory: List of Message objects containing conversation turns

    Returns:
        Formatted string representing the conversation
    """
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
    trajectory: list[Message],
    prompt_type: str = 'initial',
    augmented_task: str = '',
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
    # If approach is a conversation history, format it
    if trajectory:
        approach = format_conversation(trajectory)
    else:
        approach = ''

    # Select the appropriate prompt template
    if prompt_type == 'initial':
        template = initial_prompt
    elif prompt_type == 'right_track':
        template = right_track_prompt
    elif prompt_type == 'refactor':
        template = refactor_prompt
    elif prompt_type == 'critical':
        template = critical_prompt

    # Format the selected template with the task and approach
    formatted_prompt = general_description + template % {
        'task': task,
        'approach': approach,
        'augmented_pr_description': augmented_task,
    }

    return formatted_prompt
