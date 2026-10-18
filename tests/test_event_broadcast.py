"""A list tab and an add tab must both receive every completion."""
import asyncio
import json
import app
from event_broadcast import EventBroadcast


def test_two_event_streams_receive_success_and_failure_and_release_subscriptions(monkeypatch):
    class Request:
        async def is_disconnected(self):
            return False

    async def scenario():
        bus = EventBroadcast()
        monkeypatch.setattr(app, "_event_queue", bus)
        left, right = await app.event_stream(Request()), await app.event_stream(Request())
        streams = (left.body_iterator, right.body_iterator)
        try:
            assert await asyncio.gather(*(s.__anext__() for s in streams)) == [": connected\n\n"] * 2
            assert len(bus._subscribers) == 2
            for event_type in ("enriched", "enrich_failed"):
                event = {"type": event_type, "word_id": "contract", "definition": "n. 合同"}
                await bus.put(event)
                received = await asyncio.wait_for(asyncio.gather(*(s.__anext__() for s in streams)), 1)
                assert [json.loads(item.removeprefix("data: ")) for item in received] == [event, event]
            await streams[0].aclose()
            assert len(bus._subscribers) == 1
            await bus.put({"type": "enriched", "word_id": "law"})
            assert '"law"' in await asyncio.wait_for(streams[1].__anext__(), 1)
        finally:
            for stream in streams:
                await stream.aclose()
        assert not bus._subscribers
    asyncio.run(scenario())
