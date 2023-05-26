import logging
import asyncio


from PubSub.ConsumerApp import ConsumerApp, CloudEvent, ConsumerResult, StateChangeEvent

#
# This application demonstrates how the Dapr API could be abstracted to
# provde a simplified dev experience for subscribing to pubsub events through
# the use of helper code and conventions.
#


logging.basicConfig(level=logging.INFO)
logging.getLogger("azure.servicebus._pyamqp.aio").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def simulate_long_running(id: str):
    for i in range(0, 5):
        logger.info(
            f"💤 [{id}] sleeping to simulate long-running-work (i={i})...")
        await asyncio.sleep(2)
    logger.info("✅ [{entity_id}] Done sleeping")


consumer_app = ConsumerApp()

# We can consume raw cloud events:


# @consumer_app.consume
# async def on_task_notification(notification: CloudEvent):
#     print("🔔 [{entity_id}] Received message: ", notification.data, flush=True)
#     entity_id = notification.data["entity_id"]
#     await simulate_long_running(entity_id)
#     return ConsumerResult.SUCCESS


# Or we can consume strongly typed events:
@consumer_app.consume
async def on_task_notification(state_changed_event: StateChangeEvent):
    logger.info(f"🔔 new task state changed event: {state_changed_event}")
    # await simulate_long_running(state_changed_event.entity_id)
    return ConsumerResult.SUCCESS


@consumer_app.consume
async def on_user_notification(state_changed_event: StateChangeEvent):
    logger.info(f"🔔 new user state changed event: {state_changed_event}")
    # await simulate_long_running(state_changed_event.entity_id)
    return ConsumerResult.SUCCESS


# # Can also specify pubsub_name and/or topic_name explicitly via the decorator:
# # notifications-pubsub-subscriber-2 specifies consumerID as task-notification-subscriber-2
# @consumer_app.consume(pubsub_name="notifications-pubsub-subscriber-2")
# def on_task_notification(notification: CloudEvent):
#     message_id = notification.data["id"]
#     print(f"🔔 new notification (subscriber-2): id={message_id}")


asyncio.run(consumer_app.run())
