import asyncio
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable

from openhands.core.logger import openhands_logger as logger
from openhands.core.utils import json
from openhands.events.event import Event, EventSource
from openhands.events.serialization.event import event_from_dict, event_to_dict
from openhands.runtime.utils.shutdown_listener import should_continue
from openhands.storage import FileStore


class EventStreamSubscriber(str, Enum):
    AGENT_CONTROLLER = 'agent_controller'
    SECURITY_ANALYZER = 'security_analyzer'
    RESOLVER = 'openhands_resolver'
    SERVER = 'server'
    RUNTIME = 'runtime'
    MAIN = 'main'
    TEST = 'test'


def session_exists(sid: str, file_store: FileStore) -> bool:
    try:
        file_store.list(f'sessions/{sid}')
        return True
    except FileNotFoundError:
        return False


@dataclass
class EventStream:
    sid: str
    file_store: FileStore
    # For each subscriber ID, there is a stack of callback functions - useful
    # when there are agent delegates
    _subscribers: dict[str, dict[str, Callable]] = field(default_factory=dict)
    _cur_id: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        try:
            events = self.file_store.list(f'sessions/{self.sid}/events')
        except FileNotFoundError:
            logger.debug(f'No events found for session {self.sid}')
            self._cur_id = 0
            return

        # if we have events, we need to find the highest id to prepare for new events
        for event_str in events:
            id = self._get_id_from_filename(event_str)
            if id >= self._cur_id:
                self._cur_id = id + 1

    def _get_filename_for_id(self, id: int) -> str:
        return f'sessions/{self.sid}/events/{id}.json'

    @staticmethod
    def _get_id_from_filename(filename: str) -> int:
        try:
            return int(filename.split('/')[-1].split('.')[0])
        except ValueError:
            logger.warning(f'get id from filename ({filename}) failed.')
            return -1

    def get_events(
        self,
        start_id=0,
        end_id=None,
        reverse=False,
        filter_out_type: tuple[type[Event], ...] | None = None,
        filter_hidden=False,
    ) -> Iterable[Event]:
        def should_filter(event: Event):
            if filter_hidden and hasattr(event, 'hidden') and event.hidden:
                return True
            if filter_out_type is not None and isinstance(event, filter_out_type):
                return True
            return False

        if reverse:
            if end_id is None:
                end_id = self._cur_id - 1
            event_id = end_id
            while event_id >= start_id:
                try:
                    event = self.get_event(event_id)
                    if not should_filter(event):
                        yield event
                except FileNotFoundError:
                    logger.debug(f'No event found for ID {event_id}')
                event_id -= 1
        else:
            event_id = start_id
            while should_continue():
                if end_id is not None and event_id > end_id:
                    break
                try:
                    event = self.get_event(event_id)
                    if not should_filter(event):
                        yield event
                except FileNotFoundError:
                    break
                event_id += 1

    def get_event(self, id: int) -> Event:
        filename = self._get_filename_for_id(id)
        content = self.file_store.read(filename)
        data = json.loads(content)
        return event_from_dict(data)

    def get_latest_event(self) -> Event:
        return self.get_event(self._cur_id - 1)

    def get_latest_event_id(self) -> int:
        return self._cur_id - 1

    def subscribe(
        self, event_id: EventStreamSubscriber, callback: Callable, callback_id: str
    ):
        if event_id not in self._subscribers:
            self._subscribers[event_id] = {}

        if callback_id in self._subscribers[event_id]:
            logger.warning(f'Subscribed ID already exists: {callback_id}')

        self._subscribers[event_id][callback_id] = callback

    def unsubscribe(self, event_id: EventStreamSubscriber, callback_id):
        if event_id not in self._subscribers:
            logger.warning(f'Subscriber not found during unsubscribe: {id}')
            return

        if callback_id not in self._subscribers[event_id]:
            logger.warning(f'Listener not found during unsubscribe: {callback_id}')
            return

        del self._subscribers[event_id][callback_id]

    def add_event(self, event: Event, source: EventSource):
        try:
            asyncio.get_running_loop().create_task(self.async_add_event(event, source))
        except RuntimeError:
            # No event loop running...
            asyncio.run(self.async_add_event(event, source))

    async def async_add_event(self, event: Event, source: EventSource):
        with self._lock:
            event._id = self._cur_id  # type: ignore [attr-defined]
            self._cur_id += 1
        logger.debug(f'Adding {type(event).__name__} id={event.id} from {source.name}')
        event._timestamp = datetime.now().isoformat()
        event._source = source  # type: ignore [attr-defined]
        data = event_to_dict(event)
        if event.id is not None:
            self.file_store.write(self._get_filename_for_id(event.id), json.dumps(data))
        tasks = []
        for key in sorted(self._subscribers.keys()):
            callbacks = self._subscribers[key]
            # callback = stack[-1]
            for callback_id in callbacks:
                logger.debug(f'emitting on {key} {callback_id}')
                callback = callbacks[callback_id]
                tasks.append(asyncio.create_task(callback(event)))
        if tasks:
            await asyncio.wait(tasks)

    def _callback(self, callback: Callable, event: Event):
        asyncio.run(callback(event))

    def filtered_events_by_source(self, source: EventSource):
        for event in self.get_events():
            if event.source == source:
                yield event

    def clear(self):
        self.file_store.delete(f'sessions/{self.sid}')
        self._cur_id = 0
        # self._subscribers = {}
        self.__post_init__()
