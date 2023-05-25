import logging
import asyncio

from fastapi import FastAPI

from PubSub.ConsumerApp import ConsumerApp, CloudEvent, ConsumerResult, StateChangeEvent

#
# This application demonstrates how the Dapr API could be abstracted to
# provde a simplified dev experience for subscribing to pubsub events through
# the use of helper code and conventions.
#


logging.basicConfig(level=logging.INFO)

app = FastAPI()
consumer_app = ConsumerApp(
    app,
    default_pubsub_name="notifications-pubsub-subscriber"
)

# We can consume raw cloud events:
@consumer_app.consume
async def on_task_notification(notification: CloudEvent):
    print(f"🔔 new notification (auto-generated): {notification.data}", flush=True)
    return ConsumerResult.SUCCESS


# Or we can consume strongly typed events:
# @consumer_app.consume
# async def on_task_notification(state_changed_event: StateChangeEvent):
#     print(f"🔔 new state changed event: {state_changed_event}")
#     return ConsumerResult.SUCCESS


# Can also specify pubsub_name and/or topic_name explicitly via the decorator:
# notifications-pubsub-subscriber-2 specifies consumerID as task-notification-subscriber-2
@consumer_app.consume(pubsub_name="notifications-pubsub-subscriber-2")
def on_task_notification(notification: CloudEvent):
    message_id = notification.data["id"]
    print(f"🔔 new notification (subscriber-2): id={message_id}")


@app.get("/",)
def root():
    return {"message": "Consumer is running"}
