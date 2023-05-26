import asyncio
from enum import Enum
import functools
import inspect
import jsons
import logging
import os
from typing import Optional
from pydantic import BaseModel
from azure.servicebus.aio import ServiceBusClient, AutoLockRenewer, ServiceBusReceiver
from azure.servicebus import ServiceBusReceivedMessage

from dotenv import load_dotenv

# TODO - refactor config storage/handling
load_dotenv()

CONNECTION_STR = os.environ.get('SERVICE_BUS_CONNECTION_STRING')
DEFAULT_SUBSCRIPTION_NAME = "subscriber-sdk-simplified" # TODO - load from env var

# TODO - split types into separate file(s)

class ConsumerResult(Enum):
    SUCCESS = 0
    RETRY = 1
    DROP = 2

class CloudEvent:
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


class Subscription:
    topic: str
    subscription_name: str
    handler: callable

    def __init__(self, topic: str, subscription_name, handler: callable):
        self.topic = topic
        self.subscription_name = subscription_name
        self.handler = handler

class ConsumerApp:
    """ConsumerApp is a wrapper around a FastAPI app that provides a decorator for subscribing to pubsub events using Dapr"""
    subscriptions: list[Subscription]

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SubscriberApp initialized")
        self.subscriptions = []


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

    def consume(self, func=None, *, subscription_name: Optional[str] = None, topic_name: Optional[str] = None):

        @functools.wraps(func)
        def decorator(func):
            nonlocal subscription_name
            nonlocal topic_name

            notification_type = ConsumerApp._get_notification_type_from_method(
                func)

            if subscription_name is None:
                subscription_name = DEFAULT_SUBSCRIPTION_NAME
            # TODO validate notification_type is a valid base for topic name?

            if topic_name is None:
                topic_name = notification_type + "-notifications"
                self.logger.info(
                    f"topic_name not set, using topic_name from function name: {topic_name}")

            self.logger.info(
                f"👂 Adding subscription: {subscription_name}/{topic_name}")

            # TODO set default 
            payload_converter = ConsumerApp._get_payload_converter_from_method(func)

            async def wrap_handler(receiver: ServiceBusReceiver, msg: ServiceBusReceivedMessage):
                parsed_message = jsons.loads(str(msg), CloudEvent)
                payload = payload_converter(parsed_message)
                try:
                    # TODO - allow success/retry/drop to be returned from handler
                    parsed_message = jsons.loads(str(msg), CloudEvent)
                    result = await func(payload)
                     # pubsub API docs (response format): https://docs.dapr.io/reference/api/pubsub_api/#expected-http-response
                    if result == ConsumerResult.RETRY:
                        self.logger.info(f"Handler returned RETRY ({msg.message_id}) - abandoning")
                        await receiver.abandon_message(msg)
                    elif result == ConsumerResult.DROP:
                        self.logger.info(f"Handler returned DROP ({msg.message_id}) - deadlettering")
                        await receiver.dead_letter_message(msg, reason="dropped by subscriber")
                    else:
                        # Other return values are treated as success
                        self.logger.info(f"Handler returned successfully ({msg.message_id}) - completing")
                        await receiver.complete_message(msg)
                except Exception as e:
                    self.logger.info(f"Error processing message ({msg.message_id}) - abandoning: {e}")
                    await receiver.abandon_message(msg)

            self.subscriptions.append(Subscription(topic_name, subscription_name, wrap_handler))
            return func

        if func is None:
            # We are called with keyword arguments
            return decorator
        else:
            # We are called as a simple decorator
            return decorator(func)
    
    async def process_subscription(self, servicebus_client:ServiceBusClient, subscription: Subscription):
        receiver = servicebus_client.get_subscription_receiver(
                topic_name=subscription.topic,
                subscription_name=subscription.subscription_name
            )
        async with receiver:
            # AutoLockRenewer performs message lock renewal (for long message processing)
            # TODO - do we want to provide a callback for renewal failure? What action would we take?
            renewer = AutoLockRenewer(max_lock_renewal_duration=5*60)

            self.logger.info(f"Starting message receiver (topic={subscription.topic})...")
            while True:
                # TODO: Add back-off logic when no messages?
                # TODO: Add max message count etc to config
                received_msgs = await receiver.receive_messages(max_message_count=10, max_wait_time=30)

                self.logger.debug(f"Received message batch, size =  {len(received_msgs)}")

                # Set up message renewal for the batch
                for msg in received_msgs:
                    self.logger.debug(f"Received message {msg.message_id}, registering for renewal")
                    renewer.register(receiver, msg)

                # process messages in parallel
                await asyncio.gather(*[subscription.handler(receiver, msg) for msg in received_msgs])


    async def run(self):
        self.logger.info("Connecting to service bus...")
        servicebus_client = ServiceBusClient.from_connection_string(
            conn_str=CONNECTION_STR)

        async with servicebus_client:
            await asyncio.gather(*[self.process_subscription(servicebus_client, subscription) for subscription in self.subscriptions])
           
