import asyncio

from opendevin.lib.command_manager import CommandManager
from opendevin.lib.event import Event

def print_callback(event):
    print(event.str_truncated(), flush=True)

class AgentController:
    def __init__(self, agent, workdir, max_iterations=100, callbacks=[]):
        self.agent = agent
        self.max_iterations = max_iterations
        self.background_commands = []
        self.command_manager = CommandManager(workdir)
        self.callbacks = callbacks
        self.callbacks.append(self.agent.add_event)
        self.callbacks.append(print_callback)

    def maybe_perform_action(self, event):
        if not (event and event.is_runnable()):
            return
        action = 'output'
        try:
            output = event.run(self)
        except Exception as e:
            output = 'Error: ' + str(e)
            action = 'error'
        out_event = Event(action, {'output': output})
        return out_event

    async def start_loop(self):
        for i in range(self.max_iterations):
            await asyncio.sleep(0.001) # Give back control for a tick, so we can await in callbacks
            print("STEP", i, flush=True)
            done = await self.step()
            if done:
                break

    async def step(self) -> bool:
        log_events = self.command_manager.get_background_events()
        for event in log_events:
            for callback in self.callbacks:
                callback(event)

        action_event = self.agent.step(self.command_manager)
        for callback in self.callbacks:
            callback(action_event)
        if action_event.action == 'finish':
            return True
        print("---", flush=True)

        output_event = self.maybe_perform_action(action_event)
        if output_event is not None:
            for callback in self.callbacks:
                callback(output_event)
        print("==============", flush=True)
        return False
