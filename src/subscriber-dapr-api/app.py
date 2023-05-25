from fastapi import FastAPI
from pydantic import BaseModel

#
# This application demonstrates how to work directly with the Dapr API
# to subscribe to a topic and receive events.
#


class CloudEvent(BaseModel):
    datacontenttype: str
    source: str
    topic: str
    pubsubname: str
    data: dict
    id: str
    specversion: str
    tracestate: str
    type: str
    traceid: str


app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/dapr/subscribe")
def dapr_subscribe():
    print(
        "⚡ In /dapr/subscribe - returning subscriptions for notifications-pubsub-subscriber1 & notifications-pubsub-subscriber2 ")
    return [
        # notifications-pubsub-subscriber doesn't specify consumerID so will use app-id
        # as the consumerID/subscription name
        {
            "pubsubname": "notifications-pubsub-subscriber",
            "topic": "task-notifications",
            "route": "new-tasks-notification-subscriber",
        },
        # notifications-pubsub-subscriber-1 specifies consumerID as task-notification-subscriber-1
        {
            "pubsubname": "notifications-pubsub-subscriber-1",
            "topic": "task-notifications",
            "route": "new-tasks-notification-subscriber-1",
        },
        # # notifications-pubsub-subscriber-2 specifies consumerID as task-notification-subscriber-2
        # {
        #     "pubsubname": "notifications-pubsub-subscriber-2",
        #     "topic": "task-notifications",
        #     "route": "new-tasks-notification-subscriber-2",
        # }
    ]


@app.post("/new-tasks-notification-subscriber")
def new_notification(notification: CloudEvent):
    print(f"🔔 new notification (subscriber): {notification.data}")

    # pubsub API docs (response format): https://docs.dapr.io/reference/api/pubsub_api/#expected-http-response
    # return {"status": "SUCCESS"} # <--- default response that is assumed for success status codes
    # return {"status": "RETRY"}
    # return {"status": "DROP"}


@app.post("/new-tasks-notification-subscriber-1")
def new_notification(notification: CloudEvent):
    print(f"🔔 new notification (subscriber-1): {notification.data}")


@app.post("/new-tasks-notification-subscriber-2")
def new_notification(notification: CloudEvent):
    print(f"🔔 new notification (subscriber-2): {notification.data}")


print("🏃 Subscriber starting...")
