import logging

from fastapi import FastAPI

from PubSub.ConsumerApp import ConsumerApp, CloudEvent

logging.basicConfig(level=logging.INFO)

app = FastAPI()
consumer_app = ConsumerApp(
    app, default_pubsub_name="notifications-pubsub-subscriber")

# TODO parse data into a model instead of CloudEvent


@consumer_app.consume
async def on_task_notification(notification: CloudEvent):
    message_id = notification.data["id"]
    print(f"🔔 new notification: id={message_id}")
    # raise Exception("oops")
    # pubsub API docs (response format): https://docs.dapr.io/reference/api/pubsub_api/#expected-http-response
    # return {"status": "RETRY"} # TODO - ensure that retry/drop work
    # return {"status": "DROP"} # TODO - ensure that retry/drop work
    return {"status": "SUCCESS"}


# Can also specify pubsub_name and topic_name explicitly:
# @consumer_app.consume(topic_name="task-notifications")
# def on_task_notification(notification: CloudEvent):
#     message_id = notification.data["id"]
#     print(f"🔔 new notification: id={message_id}")
