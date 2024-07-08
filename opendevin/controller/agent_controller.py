import asyncio
import traceback
from typing import Optional, Tuple, Type

from opendevin.controller.agent import Agent, AsyncAgent
from opendevin.controller.state.state import State, TrafficControlState
from opendevin.controller.stuck import StuckDetector
from opendevin.core.config import config
from opendevin.core.exceptions import (
    LLMMalformedActionError,
    LLMNoActionError,
    LLMResponseError,
)
from opendevin.core.logger import opendevin_logger as logger
from opendevin.core.schema import AgentState
from opendevin.events import EventSource, EventStream, EventStreamSubscriber
from opendevin.events.action import (
    Action,
    AddTaskAction,
    AgentDelegateAction,
    AgentFinishAction,
    AgentRejectAction,
    ChangeAgentStateAction,
    MessageAction,
    ModifyTaskAction,
    NullAction,
)
from opendevin.events.event import Event
from opendevin.events.observation import (
    AgentDelegateObservation,
    AgentStateChangedObservation,
    CmdOutputObservation,
    ErrorObservation,
    Observation,
)

MAX_ITERATIONS = config.max_iterations
MAX_BUDGET_PER_TASK = config.max_budget_per_task
# note: RESUME is only available on web GUI
TRAFFIC_CONTROL_REMINDER = (
    "Please click on resume button if you'd like to continue, or start a new task."
)


class AgentController:
    id: str
    agent: Agent
    max_iterations: int
    event_stream: EventStream
    state: State
    agent_task: Optional[asyncio.Task] = None
    parent: 'AgentController | None' = None
    delegate: 'AgentController | None' = None
    _pending_action: Action | None = None

    def __init__(
        self,
        agent: Agent,
        event_stream: EventStream,
        sid: str = 'default',
        max_iterations: int | None = MAX_ITERATIONS,
        max_budget_per_task: float | None = MAX_BUDGET_PER_TASK,
        initial_state: State | None = None,
        is_delegate: bool = False,
    ):
        """Initializes a new instance of the AgentController class.

        Args:
            agent: The agent instance to control.
            event_stream: The event stream to publish events to.
            sid: The session ID of the agent.
            max_iterations: The maximum number of iterations the agent can run.
            max_budget_per_task: The maximum budget (in USD) allowed per task, beyond which the agent will stop.
            initial_state: The initial state of the controller.
            is_delegate: Whether this controller is a delegate.
        """
        self._is_closing = False
        self._close_event = asyncio.Event()
        self._step_lock = asyncio.Lock()
        self.id = sid
        self.agent = agent

        # subscribe to the event stream
        self.event_stream = event_stream
        self.event_stream.subscribe(
            EventStreamSubscriber.AGENT_CONTROLLER, self.on_event, append=is_delegate
        )

        # state from the previous session, state from a parent agent, or a fresh state
        max_iterations = (
            max_iterations if max_iterations is not None else MAX_ITERATIONS
        )
        self.set_initial_state(
            state=initial_state,
            max_iterations=max_iterations,
        )

        self.max_budget_per_task = max_budget_per_task

        # stuck helper
        self._stuck_detector = StuckDetector(self.state)

        if not is_delegate:
            self.agent_task = asyncio.create_task(self._start_step_loop())

    async def close(self):
        if self._is_closing:
            return
        self._is_closing = True

        if self.agent_task is not None:
            self.agent_task.cancel()
            try:
                await self.agent_task
            except asyncio.CancelledError:
                logger.info(f'AgentController task was cancelled for {self.id}')

        await self.set_agent_state_to(AgentState.STOPPED)
        self.event_stream.unsubscribe(EventStreamSubscriber.AGENT_CONTROLLER)
        self._close_event.set()

    def update_state_before_step(self):
        self.state.iteration += 1

    async def update_state_after_step(self):
        # update metrics especially for cost
        self.state.metrics = self.agent.llm.metrics

    async def report_error(self, message: str, exception: Exception | None = None):
        """
        This error will be reported to the user and sent to the LLM next step, in the hope it can self-correct.

        This method should be called for a particular type of errors, which have:
        - a user-friendly message, which will be shown in the chat box. This should not be a raw exception message.
        - an ErrorObservation that can be sent to the LLM by the agent, with the exception message, so it can self-correct next time.
        """
        self.state.last_error = message
        if exception:
            self.state.last_error += f': {exception}'
        await self.event_stream.add_event(ErrorObservation(message), EventSource.AGENT)

    async def _start_step_loop(self):
        logger.info(f'[Agent Controller {self.id}] Starting step loop...')
        try:
            while not self._is_closing:
                try:
                    await self._step()
                except asyncio.CancelledError:
                    logger.info(f'AgentController step was cancelled for {self.id}')
                    break
                except Exception as e:
                    traceback.print_exc()
                    logger.error(f'Error while running the agent: {e}')
                    logger.error(traceback.format_exc())
                    await self.report_error(
                        'There was an unexpected error while running the agent',
                        exception=e,
                    )
                    await self.set_agent_state_to(AgentState.ERROR)
                    break

                await asyncio.sleep(0.1)
        finally:
            self._close_event.set()

    async def on_event(self, event: Event):
        # Only parse agent_state for ChangeAgentStateAction
        new_state = None
        if isinstance(event, ChangeAgentStateAction):
            success, parsed_state = self._parse_agent_state(event.agent_state)
            if success:
                new_state = parsed_state
            else:
                logger.error(f'Invalid agent state received: {event.agent_state}')
                return  # Exit early if the state is invalid

        if self.get_agent_state() == AgentState.STOPPED:
            if isinstance(event, Observation) and not isinstance(
                event, AgentStateChangedObservation
            ):
                logger.info('Task cancelled.')
                return
            elif isinstance(event, ChangeAgentStateAction):
                # Allow ChangeAgentStateAction to be processed even when stopped
                pass
            else:
                # Ignore all other events when stopped
                logger.debug(f'Ignoring event in STOPPED state: {event}')
                return

        if isinstance(event, ChangeAgentStateAction):
            if new_state is not None and new_state != self.state.agent_state:
                await self.set_agent_state_to(new_state)
        elif isinstance(event, MessageAction):
            if event.source == EventSource.USER:
                if self.get_agent_state() != AgentState.RUNNING:
                    await self.set_agent_state_to(AgentState.RUNNING)
            elif event.source == EventSource.AGENT and event.wait_for_response:
                await self.set_agent_state_to(AgentState.AWAITING_USER_INPUT)
        elif isinstance(event, AgentDelegateAction):
            await self.start_delegate(event)
        elif isinstance(event, AddTaskAction):
            self.state.root_task.add_subtask(event.parent, event.goal, event.subtasks)
        elif isinstance(event, ModifyTaskAction):
            self.state.root_task.set_subtask_state(event.task_id, event.state)
        elif isinstance(event, AgentFinishAction):
            self.state.outputs = event.outputs  # type: ignore[attr-defined]
            await self.set_agent_state_to(AgentState.FINISHED)
        elif isinstance(event, AgentRejectAction):
            self.state.outputs = event.outputs  # type: ignore[attr-defined]
            await self.set_agent_state_to(AgentState.REJECTED)
        elif isinstance(event, Observation):
            if self._pending_action and self._pending_action.id == event.cause:
                self._pending_action = None
                logger.info(event, extra={'msg_type': 'OBSERVATION'})
            elif isinstance(event, CmdOutputObservation):
                logger.info(event, extra={'msg_type': 'OBSERVATION'})
            elif isinstance(event, AgentDelegateObservation):
                self.state.history.on_event(event)
                logger.info(event, extra={'msg_type': 'OBSERVATION'})
            elif isinstance(event, ErrorObservation):
                logger.info(event, extra={'msg_type': 'OBSERVATION'})

    def reset_task(self):
        self.almost_stuck = 0
        self.agent.reset()

    async def set_agent_state_to(self, new_state: AgentState):
        if new_state == self.state.agent_state:
            return

        logger.debug(
            f'[Agent Controller {self.id}] Setting agent({self.agent.name}) state from {self.state.agent_state} to {new_state}'
        )

        if (
            self.state.agent_state == AgentState.PAUSED
            and new_state == AgentState.RUNNING
            and self.state.traffic_control_state == TrafficControlState.THROTTLING
        ):
            # user intends to interrupt traffic control and let the task resume temporarily
            self.state.traffic_control_state = TrafficControlState.PAUSED

        self.state.agent_state = new_state
        if new_state == AgentState.STOPPED:
            self.reset_task()
            # Reset to AWAITING_USER_INPUT after STOPPED
            new_state = AgentState.AWAITING_USER_INPUT
            self.state.agent_state = new_state
            logger.info(
                f'[Agent Controller] Setting agent({type(self.agent).__name__}) to {new_state}'
            )
        elif new_state == AgentState.ERROR:
            self.reset_task()

        await self.event_stream.add_event(
            AgentStateChangedObservation('', self.state.agent_state), EventSource.AGENT
        )

        if new_state == AgentState.INIT and self.state.resume_state:
            await self.set_agent_state_to(self.state.resume_state)
            self.state.resume_state = None

    def get_agent_state(self):
        """Returns the current state of the agent task."""
        return self.state.agent_state

    async def start_delegate(self, action: AgentDelegateAction):
        agent_cls: Type[Agent] = Agent.get_cls(action.agent)
        agent = agent_cls(llm=self.agent.llm)
        state = State(
            inputs=action.inputs or {},
            iteration=0,
            max_iterations=self.state.max_iterations,
            delegate_level=self.state.delegate_level + 1,
            # metrics should be shared between parent and child
            metrics=self.state.metrics,
        )
        logger.info(f'[Agent Controller {self.id}]: start delegate')
        self.delegate = AgentController(
            sid=self.id + '-delegate',
            agent=agent,
            event_stream=self.event_stream,
            max_iterations=self.state.max_iterations,
            max_budget_per_task=self.max_budget_per_task,
            initial_state=state,
            is_delegate=True,
        )
        await self.delegate.set_agent_state_to(AgentState.RUNNING)

    async def _step(self):
        if self.get_agent_state() != AgentState.RUNNING:
            await asyncio.sleep(1)
            return

        if self._pending_action:
            logger.debug(
                f'[Agent Controller {self.id}] waiting for pending action: {self._pending_action}'
            )
            await asyncio.sleep(1)
            return

        if self.delegate is not None:
            logger.debug(f'[Agent Controller {self.id}] Delegate not none, awaiting...')
            assert self.delegate != self
            await self.delegate._step()
            logger.debug(f'[Agent Controller {self.id}] Delegate step done')
            assert self.delegate is not None
            delegate_state = self.delegate.get_agent_state()
            if delegate_state == AgentState.ERROR:
                # close the delegate upon error
                await self.delegate.close()
                self.delegate = None
                self.delegateAction = None
                await self.report_error('Delegator agent encounters an error')
                return
            delegate_done = delegate_state in (AgentState.FINISHED, AgentState.REJECTED)
            if delegate_done:
                logger.info(
                    f'[Agent Controller {self.id}] Delegate agent has finished execution'
                )
                # retrieve delegate result
                outputs = self.delegate.state.outputs if self.delegate.state else {}

                # close delegate controller: we must close the delegate controller before adding new events
                await self.delegate.close()

                # update delegate result observation
                # TODO: replace this with AI-generated summary (#2395)
                formatted_output = ', '.join(
                    f'{key}: {value}' for key, value in outputs.items()
                )
                content = (
                    f'{self.delegate.agent.name} finishes task with {formatted_output}'
                )
                obs: Observation = AgentDelegateObservation(
                    outputs=outputs, content=content
                )

                # clean up delegate status
                self.delegate = None
                self.delegateAction = None
                await self.event_stream.add_event(obs, EventSource.AGENT)
            return

        logger.info(
            f'{self.agent.name} LEVEL {self.state.delegate_level} STEP {self.state.iteration}',
            extra={'msg_type': 'STEP'},
        )

        if self.state.iteration >= self.state.max_iterations:
            if self.state.traffic_control_state == TrafficControlState.PAUSED:
                logger.info(
                    'Hitting traffic control, temporarily resume upon user request'
                )
                self.state.traffic_control_state = TrafficControlState.NORMAL
            else:
                self.state.traffic_control_state = TrafficControlState.THROTTLING
                await self.report_error(
                    f'Agent reached maximum number of iterations, task paused. {TRAFFIC_CONTROL_REMINDER}'
                )
                await self.set_agent_state_to(AgentState.PAUSED)
                return
        elif self.max_budget_per_task is not None:
            current_cost = self.state.metrics.accumulated_cost
            if current_cost > self.max_budget_per_task:
                if self.state.traffic_control_state == TrafficControlState.PAUSED:
                    logger.info(
                        'Hitting traffic control, temporarily resume upon user request'
                    )
                    self.state.traffic_control_state = TrafficControlState.NORMAL
                else:
                    self.state.traffic_control_state = TrafficControlState.THROTTLING
                    await self.report_error(
                        f'Task budget exceeded. Current cost: {current_cost:.2f}, Max budget: {self.max_budget_per_task:.2f}, task paused. {TRAFFIC_CONTROL_REMINDER}'
                    )
                    await self.set_agent_state_to(AgentState.PAUSED)
                    return

        self.update_state_before_step()
        action: Action = NullAction()
        try:
            if isinstance(self.agent, AsyncAgent):
                action = await self.agent.async_step(self.state)
            else:
                action = self.agent.step(self.state)
            if action is None:
                raise LLMNoActionError('No action was returned')
        except (LLMMalformedActionError, LLMNoActionError, LLMResponseError) as e:
            # report to the user
            # and send the underlying exception to the LLM for self-correction
            await self.report_error(str(e))
            return

        if action.runnable:
            self._pending_action = action

        if not isinstance(action, NullAction):
            await self.event_stream.add_event(action, EventSource.AGENT)

        await self.update_state_after_step()
        logger.info(action, extra={'msg_type': 'ACTION'})

        if self._is_stuck():
            await self.report_error('Agent got stuck in a loop')
            await self.set_agent_state_to(AgentState.ERROR)

    def get_state(self):
        return self.state

    def set_initial_state(
        self, state: State | None, max_iterations: int = MAX_ITERATIONS
    ):
        # state from the previous session, state from a parent agent, or a new state
        # note that this is called twice when restoring a previous session, first with state=None
        if state is None:
            self.state = State(inputs={}, max_iterations=max_iterations)
        else:
            self.state = state

        # when restored from a previous session, the State object will have history, start_id, and end_id
        # connect it to the event stream
        self.state.history.set_event_stream(self.event_stream)

        # if start_id was not set in State, we're starting fresh, at the top of the stream
        start_id = self.state.start_id
        if start_id == -1:
            start_id = self.event_stream.get_latest_event_id() + 1
        else:
            logger.debug(f'AgentController {self.id} restoring from event {start_id}')

        # make sure history is in sync
        self.state.start_id = start_id
        self.state.history.start_id = start_id

        # if there was an end_id saved in State, set it in history
        # currently not used, later useful for delegates
        if self.state.end_id > -1:
            self.state.history.end_id = self.state.end_id

    def _is_stuck(self):
        # check if delegate stuck
        if self.delegate and self.delegate._is_stuck():
            return True

        return self._stuck_detector.is_stuck()

    def __repr__(self):
        return (
            f'AgentController(id={self.id}, agent={self.agent!r}, '
            f'event_stream={self.event_stream!r}, '
            f'state={self.state!r}, agent_task={self.agent_task!r}, '
            f'delegate={self.delegate!r}, _pending_action={self._pending_action!r})'
        )

    async def wait_closed(self):
        await self._close_event.wait()

    async def stop(self) -> None:
        await self.set_agent_state_to(AgentState.STOPPED)

    def _parse_agent_state(self, state_str: str) -> Tuple[bool, AgentState | None]:
        """
        Parse a string into an AgentState enum value.

        Args:
            state_str (str): The string representation of the agent state.

        Returns:
            Tuple[bool, AgentState | None]: A tuple containing:
                - A boolean indicating whether the parsing was successful.
                - The AgentState enum value if successful, None otherwise.
        """
        try:
            new_state = AgentState(state_str)
            return True, new_state
        except ValueError:
            logger.error(f'Invalid agent state received: {state_str}')
            return False, None

    def is_stopped(self):
        return self.state.agent_state == AgentState.STOPPED.value
