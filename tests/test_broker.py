import asyncio

from scoreocr.web.broker import EventBroker


def test_publish_from_thread_reaches_subscriber():
    async def scenario():
        broker = EventBroker()
        broker.bind_loop(asyncio.get_running_loop())
        q = broker.subscribe("b1")
        await asyncio.to_thread(broker.publish, "b1", {"type": "photo", "n": 1})
        event = await asyncio.wait_for(q.get(), timeout=1.0)
        assert event == {"type": "photo", "n": 1}
        broker.unsubscribe("b1", q)

    asyncio.run(scenario())


def test_publish_without_loop_is_noop():
    broker = EventBroker()
    broker.publish("b1", {"type": "photo"})  # must not raise
