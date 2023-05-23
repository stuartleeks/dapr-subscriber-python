import os
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

print("🏃 Subscriber starting...")


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/dapr/subscribe")
def dapr_subscribe():
    print(
        "🔔 In /dapr/subscribe - returning subscriptions for notifications-pubsub-subscriber1 & notifications-pubsub-subscriber2 ")
    return [
        {
            "pubsubname": "notifications-pubsub-subscriber1",
            "topic": "task-notifications",
            "route": "new-tasks-notification-subscriber-1",
        }, {
            "pubsubname": "notifications-pubsub-subscriber2",
            "topic": "task-notifications",
            "route": "new-tasks-notification-subscriber-2",
        }
    ]


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


@app.post("/new-tasks-notification-subscriber-1")
async def new_notification(notification: CloudEvent):
    message_id = notification.data["id"]
    print(f"🔔 new notification (subscriber-1): id={message_id}")
    print(f"message: {notification.data['message']}")
    # return {"status": "RETRY"}


@app.post("/new-tasks-notification-subscriber-2")
async def new_notification(notification: CloudEvent):
    message_id = notification.data["id"]
    print(f"🔔 new notification (subscriber-2): id={message_id}")
    print(f"message: {notification.data['message']}")
