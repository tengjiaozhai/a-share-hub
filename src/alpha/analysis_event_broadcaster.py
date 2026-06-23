import asyncio
from collections import defaultdict
from typing import TypeAlias

Subscriber: TypeAlias = tuple[asyncio.AbstractEventLoop, asyncio.Queue]


class EventBroadcaster:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[Subscriber]] = defaultdict(set)

    def publish(self, run_id: str, event: dict) -> None:
        for loop, queue in list(self._subscribers.get(run_id, ())):
            if loop.is_closed():
                self._subscribers[run_id].discard((loop, queue))
                continue
            loop.call_soon_threadsafe(queue.put_nowait, event)

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_id].add((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[run_id] = {
            item for item in self._subscribers[run_id] if item[1] is not queue
        }
        if not self._subscribers[run_id]:
            self._subscribers.pop(run_id, None)
