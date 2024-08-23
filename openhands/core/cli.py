import asyncio
import sys
from typing import Type

from termcolor import colored

import agenthub  # noqa F401 (we import this to get the agents registered)
from openhands.controller import AgentController
from openhands.controller.agent import Agent
from openhands.core.config import (
    load_app_config,
)
from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import AgentState
from openhands.events import EventSource, EventStream, EventStreamSubscriber
from openhands.events.action import Action, CmdRunAction, MessageAction
from openhands.events.event import Event
from openhands.events.observation import (
    AgentStateChangedObservation,
    CmdOutputObservation,
)
from openhands.llm.llm import LLM
from openhands.runtime import get_runtime_cls
from openhands.runtime.runtime import Runtime
from openhands.storage import get_file_store


def display_message(message: str):
    print(colored(message, 'yellow'))


def display_command(command: str):
    print(colored(command, 'green'))


def display_command_output(output: str):
    print(colored(output, 'blue'))


def display_event(event: Event):
    if isinstance(event, Action):
        if hasattr(event, 'thought'):
            display_message(event.thought)
    if isinstance(event, MessageAction):
        display_message(event.content)
    if isinstance(event, CmdRunAction):
        display_command(event.command)
    if isinstance(event, CmdOutputObservation):
        display_command_output(event.content)


async def main():
    """Runs the agent in CLI mode"""
    config = load_app_config()
    sid = 'cli'

    agent_cls: Type[Agent] = Agent.get_cls(config.default_agent)
    agent_config = config.get_agent_config(config.default_agent)
    llm_config = config.get_llm_config_from_agent(config.default_agent)
    agent = agent_cls(
        llm=LLM(config=llm_config),
        config=agent_config,
    )

    file_store = get_file_store(config.file_store, config.file_store_path)
    event_stream = EventStream(sid, file_store)

    runtime_cls = get_runtime_cls(config.runtime)
    logger.info(f'Initializing runtime: {runtime_cls}')
    runtime: Runtime = runtime_cls(
        config=config,
        event_stream=event_stream,
        sid=sid,
        plugins=agent_cls.sandbox_plugins,
    )
    await runtime.ainit()

    # init controller with this initial state
    controller = AgentController(
        agent=agent,
        max_iterations=config.max_iterations,
        max_budget_per_task=config.max_budget_per_task,
        agent_to_llm_config=config.get_agent_to_llm_config_map(),
        event_stream=event_stream,
    )

    async def prompt_for_next_task():
        next_message = input('How can I help? >> ')
        if next_message == 'exit':
            print('Exiting...')
            await controller.close()
            sys.exit(0)
        action = MessageAction(content=next_message)
        event_stream.add_event(action, EventSource.USER)

    async def on_event(event: Event):
        display_event(event)
        if isinstance(event, AgentStateChangedObservation):
            if event.agent_state == AgentState.AWAITING_USER_INPUT:
                message = input('Request user input >> ')
                action = MessageAction(content=message)
                event_stream.add_event(action, EventSource.USER)
            elif event.agent_state == AgentState.FINISHED:
                await prompt_for_next_task()
            elif event.agent_state == AgentState.ERROR:
                print('An error occurred. Please try again.')
                await prompt_for_next_task()

    event_stream.subscribe(EventStreamSubscriber.MAIN, on_event)

    await prompt_for_next_task()

    while controller.state.agent_state not in [
        AgentState.REJECTED,
        AgentState.ERROR,
        AgentState.STOPPED,
    ]:
        print('tick')
        await asyncio.sleep(1)  # Give back control for a tick, so the agent can run

    await controller.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        pass
