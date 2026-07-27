import asyncio
from collections import defaultdict


class EventBroker:
    def __init__(self):
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self, batch_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[batch_id].add(q)
        return q

    def unsubscribe(self, batch_id: str, queue: asyncio.Queue) -> None:
        self._subs[batch_id].discard(queue)

    def publish(self, batch_id: str, event: dict) -> None:
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(self._deliver, batch_id, event)

    def _deliver(self, batch_id: str, event: dict) -> None:
        for q in list(self._subs.get(batch_id, ())):
            q.put_nowait(event)
