from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/dapr/subscribe")
def dapr_subscribe():
    return [
        {
            "pubsubname": "pubsub",
            "topic": "new-notification",
            "route": "new-notification"
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


@app.post("/new-notification")
async def new_notification(notification: CloudEvent):
    message_id = notification.data["id"]
    print(f"new notification: id={message_id}")
    print(f"message: {notification.data['message']}")
    # return {"status": "RETRY"}
