from enum import Enum
import functools
import inspect
import logging
from typing import Optional
import uuid
from pydantic import BaseModel
from fastapi import FastAPI

# TODO - split types into separate file(s)

class ConsumerResult(Enum):
    SUCCESS = 0
    RETRY = 1
    DROP = 2

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


class StateChangeEvent:
    """StateChangeEvent is the base type for state change events"""
    entity_type: str
    entity_id: str
    new_state: str

    def __init__(self, entity_type: str, entity_id: str, new_state: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.new_state = new_state

    def from_dict(data: dict):
        entity_type = data["entity_type"]
        entity_id = data["entity_id"]
        new_state = data["new_state"]
        return StateChangeEvent(entity_type, entity_id, new_state)

    def __repr__(self) -> str:
        return f"StateChangeEvent(entity_type={self.entity_type}, entity_id={self.entity_id}, new_state={self.new_state})"

_payload_type_converters = {
    CloudEvent: lambda cloudEvent: cloudEvent,
    StateChangeEvent: lambda cloudEvent: StateChangeEvent.from_dict(
        cloudEvent.data)
}


class ConsumerApp:
    """ConsumerApp is a wrapper around a FastAPI app that provides a decorator for subscribing to pubsub events using Dapr"""

    def __init__(self, app: FastAPI, default_pubsub_name: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SubscriberApp initialized")
        self.app = app
        self.default_pubsub_name = default_pubsub_name
        self.subscriptions = []

        self.app.add_api_route(
            "/dapr/subscribe", self._get_subscriptions, methods=["GET"])
        self.app.add_api_route(
            "/test", lambda: {"message": "test"}, methods=["GET"])

    def _get_subscriptions(self):
        self.logger.info("⚡ In /dapr/subscribe")
        for subscription in self.subscriptions:
            self.logger.info(f"subscription: {subscription}")
        return self.subscriptions

    @property
    def FastAPIApp(self):
        return self.app

    def _get_notification_type_from_method(func):
        function_name = func.__name__
        if not function_name.startswith("on_"):
            raise Exception(
                f"Function name must be in the form on_<topic_name>_notification")
        notification_type = function_name.split("_")[1]
        return notification_type

    def _get_payload_converter_from_method(func):
        argspec = inspect.getfullargspec(func)

        # For simplicity currently, limit to a single argument that is the notification payload
        if len(argspec.args) != 1:
            raise Exception(
                "Function must have exactly one argument (the notification)")

        arg0_annotation = argspec.annotations.get(argspec.args[0], None)
        converter = _payload_type_converters.get(arg0_annotation, None)
        if converter is None:
            raise Exception(f"Unsupported payload type: {arg0_annotation}")

        return converter

    def consume(self, func=None, *, pubsub_name: Optional[str] = None, topic_name: Optional[str] = None):

        @functools.wraps(func)
        def decorator(func):
            nonlocal pubsub_name
            nonlocal topic_name

            # If invoked without pubsub_name/topic_name, we need to generate them based on the function name
            if pubsub_name is None:
                self.logger.info(
                    f"pubsub_name not set, using default pubsub_name: {self.default_pubsub_name}")
                pubsub_name = self.default_pubsub_name

            notification_type = ConsumerApp._get_notification_type_from_method(
                func)

            # TODO validate notification_type is a valid base for topic name?

            if topic_name is None:
                topic_name = notification_type + "-notifications"
                self.logger.info(
                    f"topic_name not set, using topic_name from function name: {topic_name}")

            # generate a unique route for the subscription and track in subscriptions
            # so that we can return them in the /dapr/subscribers endpoint
            subscription_url = f"/handler/{uuid.uuid4()}"
            self.logger.info(
                f"👂 Adding subscription: {pubsub_name}/{topic_name} -> {subscription_url}")
            self.subscriptions.append({
                "pubsubname": pubsub_name,
                "topic": topic_name,
                "route": subscription_url
            })

            # TODO set default 
            payload_converter = ConsumerApp._get_payload_converter_from_method(func)

            async def func_wrapper(notification: CloudEvent):
                payload = payload_converter(notification)
                result = await func(payload)
            
                # pubsub API docs (response format): https://docs.dapr.io/reference/api/pubsub_api/#expected-http-response
                if result is None or result == ConsumerResult.SUCCESS:
                    return {"status": "SUCCESS"}
                elif result == ConsumerResult.RETRY:
                    return {"status": "RETRY"}
                elif result == ConsumerResult.DROP:
                    return {"status": "DROP"}
                else:
                    return result

            self.app.add_api_route(subscription_url, func_wrapper, methods=["POST"])

            return func

        if func is None:
            # We are called with keyword arguments
            return decorator
        else:
            # We are called as a simple decorator
            return decorator(func)
