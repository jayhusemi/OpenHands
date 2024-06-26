from typing import Any
import asyncio
import json
import os
import websockets
from opendevin.events.serialization.action import ACTION_TYPE_TO_CLASS
from opendevin.events.action.action import Action
from opendevin.events.event import Event
from opendevin.events.observation import Observation
from opendevin.events.stream import EventStream
from opendevin.runtime.plugins import PluginRequirement
from opendevin.events.serialization import event_to_dict
from opendevin.runtime.runtime import Runtime
from opendevin.runtime.sandbox import Sandbox
from opendevin.runtime.tools import RuntimeTool
from opendevin.events.observation import (
    CmdOutputObservation,
    ErrorObservation,
    NullObservation,
    Observation,
)
from opendevin.events.action import (
    AgentRecallAction,
    BrowseInteractiveAction,
    BrowseURLAction,
    CmdKillAction,
    CmdRunAction,
    FileReadAction,
    FileWriteAction,
    IPythonRunCellAction,
)
from opendevin.core.schema import CancellableStream
import asyncio
from opendevin.events import EventSource, EventStream, EventStreamSubscriber

class EventStreamRuntime(Runtime):
    # websocket uri
    uri = 'ws://localhost:8080'

    def __init__(self, event_stream: EventStream, sid: str = 'default', sandbox: Sandbox | None = None):
        self.event_stream = event_stream
        # self._init_event_stream()
        self._init_websocket()
    
    def _init_event_stream(self):
        self.event_stream.subscribe(EventStreamSubscriber.RUNTIME, self.on_event)
        self._bg_task = asyncio.create_task(self._start_background_observation_loop())

    def _init_websocket(self):
        self.websocket = None
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self._init_websocket_connect())
    
    async def _init_websocket_connect(self):
        self.websocket = await websockets.connect(self.uri)
    
    def close(self):
        pass

    def init_sandbox_plugins(self, plugins: list[PluginRequirement]) -> None:
        print("Not implemented yet.")
    
    def init_runtime_tools(self, runtime_tools: list[RuntimeTool], runtime_tools_config: dict[RuntimeTool, Any] | None = None, is_async: bool = True) -> None:
        print("Not implemented yet.")
    
    async def on_event(self, event: Event) -> None:
        if isinstance(event, Action):
            observation = await self.run_action(event)
            observation._cause = event.id  # type: ignore[attr-defined]
            source = event.source if event.source else EventSource.AGENT
            await self.event_stream.add_event(observation, source)
    
    async def run_action(self, action: Action) -> Observation:
        """
        Run an action and return the resulting observation.
        If the action is not runnable in any runtime, a NullObservation is returned.
        If the action is not supported by the current runtime, an ErrorObservation is returned.
        """
        if not action.runnable:
            return NullObservation('')
        action_type = action.action  # type: ignore[attr-defined]
        if action_type not in ACTION_TYPE_TO_CLASS:
            return ErrorObservation(f'Action {action_type} does not exist.')
        if not hasattr(self, action_type):
            return ErrorObservation(
                f'Action {action_type} is not supported in the current runtime.'
            )
        observation = await getattr(self, action_type)(action)
        observation._parent = action.id  # type: ignore[attr-defined]
        return observation
    
    async def execute(
        self, action: Action, stream: bool = False, timeout: int | None = None
    ) -> tuple[int, str | CancellableStream]:
        if self.websocket is None:
            raise Exception("WebSocket is not connected.")
        await self.websocket.send(json.dumps(event_to_dict(action)))
        output = await self.websocket.recv()
        print(output)
        return output
    
    async def run(self, action: CmdRunAction) -> Observation:
        pass

    
    async def kill(self, action: CmdKillAction) -> Observation:
        pass

    
    async def run_ipython(self, action: IPythonRunCellAction) -> Observation:
        pass

    
    async def read(self, action: FileReadAction) -> Observation:
        pass

    
    async def write(self, action: FileWriteAction) -> Observation:
        pass

    
    async def browse(self, action: BrowseURLAction) -> Observation:
        pass

    
    async def browse_interactive(self, action: BrowseInteractiveAction) -> Observation:
        pass

    
    async def recall(self, action: AgentRecallAction) -> Observation:
        pass


    async def _start_background_observation_loop(self):
        while True:
            await self.submit_background_obs()
            await asyncio.sleep(1)

    async def submit_background_obs(self):
        """
        Returns all observations that have accumulated in the runtime's background.
        Right now, this is just background commands, but could include e.g. asynchronous
        events happening in the browser.
        """
        print("Not implemented yet.")
        await asyncio.sleep(2)


if __name__ == "__main__":
    runtime = EventStreamRuntime(None)
    asyncio.run(runtime.execute(CmdRunAction('ls -l')))


    