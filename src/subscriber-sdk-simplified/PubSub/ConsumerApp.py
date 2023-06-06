import asyncio
from enum import Enum
import functools
import inspect
import jsons
import logging
import os
from typing import Optional
from azure.servicebus.aio import ServiceBusClient, AutoLockRenewer, ServiceBusReceiver
from azure.servicebus import ServiceBusReceivedMessage
from azure.identity.aio import WorkloadIdentityCredential
from timeit import default_timer as timer

from dotenv import load_dotenv

# TODO - refactor config storage/handling
load_dotenv()

CONNECTION_STR = os.environ.get('SERVICE_BUS_CONNECTION_STRING')
AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID', '')
AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID', '')
AZURE_AUTHORITY_HOST = os.getenv('AZURE_AUTHORITY_HOST', '')
AZURE_FEDERATED_TOKEN_FILE = os.getenv('AZURE_FEDERATED_TOKEN_FILE', '')
SERVICE_BUS_NAMESPACE = os.getenv('SERVICE_BUS_NAMESPACE', '')

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
    max_message_count: Optional[int]
    max_wait_time: Optional[int]

    def __init__(
        self,
        topic: str,
        subscription_name,
        handler: callable,
        max_message_count: Optional[int] = None,
        max_wait_time: Optional[int] = None,
        max_lock_renewal_duration: Optional[int] = None
    ):
        self.topic = topic
        self.subscription_name = subscription_name
        self.handler = handler
        self.max_message_count = max_message_count
        self.max_wait_time = max_wait_time
        self.max_lock_renewal_duration = max_lock_renewal_duration


class ConsumerApp:
    """ConsumerApp is a wrapper around a FastAPI app that provides a decorator for subscribing to pubsub events using Dapr"""
    subscriptions: list[Subscription]

    def __init__(
            self,
            default_subscription_name: str = None,
            max_message_count: int = 10,
            max_wait_time: int = 30,
            max_lock_renewal_duration: int = 5*60
    ):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SubscriberApp initialized")
        self.subscriptions = []
        if not default_subscription_name:
            default_subscription_name = os.environ.get("DEFAULT_SUBSCRIPTION_NAME")
        if not default_subscription_name:
            raise Exception("default_subscription_name must be provided or set in env var DEFAULT_SUBSCRIPTION_NAME")
        self.default_subscription_name = default_subscription_name
        self.max_message_count = max_message_count
        self.max_wait_time = max_wait_time
        self.max_lock_renewal_duration = max_lock_renewal_duration

    def _get_topic_name_from_method(func):
        function_name = func.__name__
        if not function_name.startswith("on_"):
            raise Exception(
                f"Function name must be in the form on_<entity-name>_<event-name>")
        parts = function_name.split("_")
        if len(parts) < 3:
            raise Exception(
                f"Function name must be in the form on_<entity-name>_<event-name>")
        topic_name = f"{parts[1]}-{parts[2]}"
        return topic_name

    def _get_payload_converter_from_method(func):
        argspec = inspect.getfullargspec(func)

        # For simplicity currently, limit to a single argument that is the notification payload
        if len(argspec.args) != 1:
            raise Exception(
                "Function must have exactly one argument (the notification)")

        arg0_annotation = argspec.annotations.get(argspec.args[0], None)
        if arg0_annotation is None:
            # default to state change event data type
            return _payload_type_converters[StateChangeEvent]

        converter = _payload_type_converters.get(arg0_annotation, None)
        if converter is None:
            raise Exception(f"Unsupported payload type: {arg0_annotation}")

        return converter

    def consume(
        self,
        func=None,
        *,
        subscription_name: Optional[str] = None,
        topic_name: Optional[str] = None,
        max_message_count: Optional[int] = None,
        max_wait_time: Optional[int] = None,
        max_lock_renewal_duration: Optional[int] = None
    ):

        @functools.wraps(func)
        def decorator(func):
            nonlocal subscription_name
            nonlocal topic_name

            notification_type = ConsumerApp._get_topic_name_from_method(
                func)

            if subscription_name is None:
                subscription_name = self.default_subscription_name
            # TODO validate notification_type is a valid base for topic name?

            if topic_name is None:
                topic_name = notification_type
                self.logger.info(
                    f"topic_name not set, using topic_name from function name: {topic_name}")

            self.logger.info(
                f"👂 Adding subscription: {topic_name}/{subscription_name}")

            payload_converter = ConsumerApp._get_payload_converter_from_method(
                func)

            async def wrap_handler(receiver: ServiceBusReceiver, msg: ServiceBusReceivedMessage):
                try:
                    # Convert message to correct payload type
                    parsed_message = jsons.loads(str(msg), CloudEvent)
                    payload = payload_converter(parsed_message)

                    # Call the decorated function
                    result = await func(payload)

                    # Handle the response
                    if result == ConsumerResult.RETRY:
                        self.logger.info(
                            f"Handler returned RETRY ({msg.message_id}) - abandoning")
                        await receiver.abandon_message(msg)
                    elif result == ConsumerResult.DROP:
                        self.logger.info(
                            f"Handler returned DROP ({msg.message_id}) - deadlettering")
                        await receiver.dead_letter_message(msg, reason="dropped by subscriber")
                    else:
                        # Other return values are treated as success
                        self.logger.info(
                            f"Handler returned successfully ({msg.message_id}) - completing")
                        await receiver.complete_message(msg)
                except Exception as e:
                    self.logger.info(
                        f"Error processing message ({msg.message_id}) - abandoning: {e}")
                    await receiver.abandon_message(msg)

            self.subscriptions.append(
                Subscription(
                    topic_name,
                    subscription_name,
                    wrap_handler,
                    max_message_count,
                    max_wait_time,
                    max_lock_renewal_duration
                )
            )
            return func

        if func is None:
            # We are called with keyword arguments
            return decorator
        else:
            # We are called as a simple decorator
            return decorator(func)

    async def process_subscription(self, servicebus_client: ServiceBusClient, subscription: Subscription):
        receiver = servicebus_client.get_subscription_receiver(
            topic_name=subscription.topic,
            subscription_name=subscription.subscription_name
        )
        max_message_count = subscription.max_message_count or self.max_message_count
        max_wait_time = subscription.max_wait_time or self.max_wait_time
        max_lock_renewal_duration = subscription.max_lock_renewal_duration or self.max_lock_renewal_duration
        async with receiver:
            # AutoLockRenewer performs message lock renewal (for long message processing)
            renewer = AutoLockRenewer(
                max_lock_renewal_duration=max_lock_renewal_duration)

            self.logger.info(
                f"Starting message receiver (topic={subscription.topic})...")
            while True:
                # TODO: Add back-off logic when no messages?
                received_msgs = await receiver.receive_messages(max_message_count=max_message_count, max_wait_time=max_wait_time)

                self.logger.info(
                    f"📦 Batch received, size =  {len(received_msgs)}")
                start = timer()

                # Set up message renewal for the batch
                for msg in received_msgs:
                    self.logger.debug(
                        f"Received message {msg.message_id}, registering for renewal")
                    renewer.register(receiver, msg)

                # process messages in parallel
                await asyncio.gather(*[subscription.handler(receiver, msg) for msg in received_msgs])
                end = timer()
                duration = end - start
                self.logger.info(
                    f"📦 Batch done, size={len(received_msgs)}, duration={duration}s")

    async def run(self):
        workload_identity_credential = None
        servicebus_client = None

        self.logger.info("Connecting to service bus...")
        if AZURE_CLIENT_ID and AZURE_TENANT_ID and AZURE_AUTHORITY_HOST and AZURE_FEDERATED_TOKEN_FILE:
            self.logger.info("Using workload identity credentials")
            workload_identity_credential = WorkloadIdentityCredential(
                client_id=AZURE_CLIENT_ID, tenant_id=AZURE_TENANT_ID, token_file_path=AZURE_FEDERATED_TOKEN_FILE)
            servicebus_client = ServiceBusClient(
                fully_qualified_namespace=SERVICE_BUS_NAMESPACE, credential=workload_identity_credential)
        else:
            self.logger.info("No workload identity credentials found, using connection string")
            servicebus_client = ServiceBusClient.from_connection_string(
                conn_str=CONNECTION_STR)

        try:
            async with servicebus_client:
                await asyncio.gather(*[self.process_subscription(servicebus_client, subscription) for subscription in self.subscriptions])
        finally:
            if workload_identity_credential:
                await workload_identity_credential.close()

