import functools
import logging
import uuid
from pydantic import BaseModel
from fastapi import FastAPI


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


class ConsumerApp:
    def __init__(self, app: FastAPI, default_pubsub_name=None):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SubscriberApp initialized")
        self.app = app
        self.default_pubsub_name = default_pubsub_name
        self.subscriptions = []

        @self.app.get("/")
        def root():
            self.logger.info("In root")
            return {"message": "Consumer is running"}

        @self.app.get("/dapr/subscribe")
        def subscriptions():
            self.logger.info("In /dapr/subscribe")
            for subscription in self.subscriptions:
                self.logger.info(f"subscription: {subscription}")
            return self.subscriptions

    @property
    def FastAPIApp(self):
        return self.app

    def consume(self, func=None, *, pubsub_name=None, topic_name=None):

        @functools.wraps(func)
        def decorator(func):
            nonlocal pubsub_name
            nonlocal topic_name

            # TODO - If invoked without pubsub_name/topic_name, we need to generate them based on the function name
            if pubsub_name is None:
                self.logger.info(f"pubsub_name not set, using default pubsub_name: {self.default_pubsub_name}")
                pubsub_name = self.default_pubsub_name

            if topic_name is None:
                function_name = func.__name__
                if function_name.startswith("on_"):
                    topic_base_name = function_name.split("_")[1]
                    if topic_base_name:
                        topic_name = topic_base_name + "-notifications"
                        self.logger.info(f"topic_name not set, using topic_name from function name: {topic_name}")
            
            if topic_name is None:
                raise ValueError("topic_name must be specified, or function name must be in the form on_<topic_name>_notification")

            # generate a unique route for the subscription and track in subscriptions
            # so that we can return them in the /dapr/subscribers endpoint
            subscription_url = f"/handler/{uuid.uuid4()}"
            self.logger.info(f"Adding subscription: {pubsub_name}/{topic_name} -> {subscription_url}")
            self.subscriptions.append({
                "pubsubname": pubsub_name,
                "topic": topic_name,
                "route": subscription_url
            })

            @self.app.post(subscription_url)
            async def api_handler(notification: CloudEvent):
                self.logger.info(f"Received notification: {notification}")
                return await func(notification)

            return func

        if func is None:
            # We are called with keyword arguments
            return decorator
        else:
            # We are called as a simple decorator
            return decorator(func)
