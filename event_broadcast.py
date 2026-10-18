"""Broadcast completion events to each connected page, without competing consumers."""
import asyncio
from contextlib import contextmanager


class EventBroadcast:
    def __init__(self):
        self._subscribers = set()

    @contextmanager
    def subscribe(self):
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def put(self, event):
        # No await between subscribers: every currently connected page gets it.
        for queue in self._subscribers:
            queue.put_nowait(event)
