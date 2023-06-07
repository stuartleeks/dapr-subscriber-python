import logging
import asyncio


from PubSub.ConsumerApp import ConsumerApp, ConsumerResult, StateChangeEventBase, TaskCreatedStateChangeEvent, TaskUpdatedStateChangeEvent, UserCreatedStateChangeEvent

#
# This application demonstrates how the Service Bus SDK API could be abstracted to
# provde a simplified dev experience for subscribing to messages through
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



@consumer_app.consume
async def on_task_created(notification: dict):
    entity_id = notification["entity_id"]
    print("🔔 [{entity_id}] Received message: ", notification, flush=True)
    # await simulate_long_running(entity_id)
    return ConsumerResult.SUCCESS

# Or we can consume strongly typed events:
# @consumer_app.consume
# async def on_task_created(state_changed_event: TaskCreatedStateChangeEvent):
#     logger.info(f"🔔 new task-created event: {state_changed_event}")
#     # await simulate_long_running(state_changed_event.entity_id)
#     return ConsumerResult.SUCCESS

@consumer_app.consume
async def on_task_updated(state_changed_event: TaskUpdatedStateChangeEvent):
    logger.info(f"🔔 new task-updated event: {state_changed_event}")
    # await simulate_long_running(state_changed_event.entity_id)
    return ConsumerResult.SUCCESS


@consumer_app.consume
async def on_user_created(state_changed_event: UserCreatedStateChangeEvent):
    logger.info(f"🔔 new user-created event: {state_changed_event}")
    # await simulate_long_running(state_changed_event.entity_id)
    return ConsumerResult.SUCCESS


# # Can also specify topic_name/subscription_name explicitly via the decorator
# @consumer_app.consume(topic_name="task-created" pubsub_name="subscriber-sdk-simplified")
# def non_conventional_method_name(notification: CloudEvent):
#     message_id = notification.data["id"]
#     print(f"🔔 new notification (subscriber-2): id={message_id}")


asyncio.run(consumer_app.run())
