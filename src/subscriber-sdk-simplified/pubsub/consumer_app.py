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

from . import case
from dotenv import load_dotenv

# TODO - refactor config storage/handling
load_dotenv()

CONNECTION_STR = os.environ.get("SERVICE_BUS_CONNECTION_STRING")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_AUTHORITY_HOST = os.getenv("AZURE_AUTHORITY_HOST", "")
AZURE_FEDERATED_TOKEN_FILE = os.getenv("AZURE_FEDERATED_TOKEN_FILE", "")
SERVICE_BUS_NAMESPACE = os.getenv("SERVICE_BUS_NAMESPACE", "")


class ConsumerResult(Enum):
    """ConsumerResult is used to indicate the result when a consumer processes a message"""

    SUCCESS = 0
    """The message was processed successfully and should be marked as completed"""

    RETRY = 1
    """The message was not processed successfully and should be marked as abandoned and retried"""

    DROP = 2
    """The message was not processed successfully but is invalid and should be sent to the dead-letter queue"""


class StateChangeEventBase:
    """StateChangeEventBase is the base type for state change events"""

    _entity_type: str
    _new_state: str
    _entity_id: str

    def __init__(self, entity_type: str, entity_id: str, new_state: str):
        self._entity_type = entity_type
        self._new_state = new_state
        self._entity_id = entity_id

    def __repr__(self) -> str:
        return f"StateChangeEventBase(entity_type={self._entity_type}, new_state={self._new_state}, entity_id={self._entity_id})"

    @property
    def entity_type(self) -> str:
        return self._entity_type

    @property
    def new_state(self) -> str:
        return self._new_state

    @property
    def entity_id(self) -> str:
        return self._entity_id

    def get_event_classes():
        event_classes = []
        StateChangeEventBase._append_event_classes_for_type(event_classes, StateChangeEventBase)
        return event_classes

    def _append_event_classes_for_type(event_classes, type):
        for event_class in type.__subclasses__():
            if not event_class.__name__.endswith("Base"):
                event_classes.append(event_class)
            StateChangeEventBase._append_event_classes_for_type(event_classes, event_class)


class Subscription:
    topic: str
    subscription_name: str
    handler: callable
    max_message_count: Optional[int]
    max_wait_time: Optional[int]
    func_name: str

    def __init__(
        self,
        topic: str,
        subscription_name,
        handler: callable,
        func_name: str,
        max_message_count: Optional[int] = None,
        max_wait_time: Optional[int] = None,
        max_lock_renewal_duration: Optional[int] = None,
    ):
        self.topic = topic
        self.subscription_name = subscription_name
        self.handler = handler
        self.func_name = func_name
        self.max_message_count = max_message_count
        self.max_wait_time = max_wait_time
        self.max_lock_renewal_duration = max_lock_renewal_duration


class ConsumerApp:
    """ConsumerApp is a helper for simplifying the consumption of messages from a Service Bus topic/subscription"""

    _subscriptions: list[Subscription]
    _is_cancelled: bool = False

    def __init__(
        self,
        default_subscription_name: str = None,
        max_message_count: int = 10,
        max_wait_time: int = 30,
        max_lock_renewal_duration: int = 5 * 60,
    ):
        self.logger = logging.getLogger(__name__)
        self.logger.info("SubscriberApp initialized")
        self._subscriptions = []
        if not default_subscription_name:
            default_subscription_name = os.environ.get("DEFAULT_SUBSCRIPTION_NAME")
        if not default_subscription_name:
            raise Exception("default_subscription_name must be provided or set in env var DEFAULT_SUBSCRIPTION_NAME")
        self.default_subscription_name = default_subscription_name
        self.max_message_count = max_message_count
        self.max_wait_time = max_wait_time
        self.max_lock_renewal_duration = max_lock_renewal_duration
        self._init_event_classes()

    def _init_event_classes(self):
        event_classes = StateChangeEventBase.get_event_classes()
        # build a map of event types to converters
        self._payload_type_converters = {
            # note the event_class=event_class to capture the current value of event_class on each iteration
            event_class: lambda msg_dict, event_class=event_class: event_class.from_dict(msg_dict)
            for event_class in event_classes
        }
        self._topic_to_event_class_map = {
            ConsumerApp._get_topic_name_from_event_class(event_class): event_class for event_class in event_classes
        }

        for event_class in event_classes:
            self.logger.info(f"Found state event class: {event_class}")

    def _get_topic_name_from_method(func):
        function_name = func.__name__
        if not function_name.startswith("on_"):
            raise Exception(f"Function name must be in the form on_<entity-name>_<event-name>")
        topic_name = case.snake_to_kebab_case(function_name[3:])
        return topic_name

    def _get_event_class_from_method(self, func):
        topic_name = ConsumerApp._get_topic_name_from_method(func)
        return self._topic_to_event_class_map[topic_name]

    def _get_topic_name_from_event_class(event_class):
        event_class_name = event_class.__name__
        if not event_class_name.endswith("StateChangeEvent"):
            raise Exception(f"Event class name must end with StateChangeEvent")

        topic_name = event_class_name.replace("StateChangeEvent", "")

        return case.pascal_to_kebab_case(topic_name)

    def _get_payload_converter_from_method(self, func):
        argspec = inspect.getfullargspec(func)

        # For simplicity currently, limit to a single argument that is the notification payload
        if len(argspec.args) != 1:
            raise Exception("Function must have exactly one argument (the notification)")

        arg0_annotation = argspec.annotations.get(argspec.args[0], None)
        if arg0_annotation is None:
            # default to dict for now
            # TODO - use func name to determine default type
            self.logger.debug("No event payload annotation found, defaulting to dict")
            arg0_annotation = dict

        if arg0_annotation == dict:
            # no conversion needed
            self.logger.debug("Using no-op converter for dict payload")
            return lambda msg_dict: msg_dict

        self.logger.debug(f"Using converter for payload type: {arg0_annotation}")
        converter = self._payload_type_converters.get(arg0_annotation, None)
        if converter is None:
            raise Exception(f"Unsupported payload type: {arg0_annotation}")

        return converter

    def consume(
        self,
        func=None,
        *,
        topic_name: Optional[str] = None,
        subscription_name: Optional[str] = None,
        max_message_count: Optional[int] = None,
        max_wait_time: Optional[int] = None,
        max_lock_renewal_duration: Optional[int] = None,
    ):
        """Decorator for consuming messages from a Service Bus topic/subscription

        By default, the topic and subscription names are derived from the function name.
        For this, the function name should be in the for on_<entity-name>_<event-name>, e.g. on_task_created.

        Alternatively, the topic and subscription names can be provided as arguments to the decorator.
        """

        @functools.wraps(func)
        def decorator(func):
            nonlocal subscription_name
            nonlocal topic_name

            # Generate Subscription to capture func ready for use in run() later
            subscription = self._get_subscription_from_method(
                func, topic_name, subscription_name, max_message_count, max_wait_time, max_lock_renewal_duration
            )
            self._subscriptions.append(subscription)
            return func

        if func is None:
            # We are called with keyword arguments
            return decorator
        else:
            # We are called as a simple decorator
            return decorator(func)

    def _get_subscription_from_method(
        self,
        func,
        topic_name: Optional[str] = None,
        subscription_name: Optional[str] = None,
        max_message_count: Optional[int] = None,
        max_wait_time: Optional[int] = None,
        max_lock_renewal_duration: Optional[int] = None,
    ):
        notification_type = ConsumerApp._get_topic_name_from_method(func)

        if subscription_name is None:
            subscription_name = self.default_subscription_name

        if topic_name is None:
            topic_name = notification_type
            self.logger.debug(f"topic_name not set, using topic_name from function name: {topic_name}")

        if self._topic_to_event_class_map.get(topic_name, None) is None:
            raise Exception(f"No event class found to match topic name '{topic_name}'")

        self.logger.info(f"🔎 Found consumer {func.__qualname__} (topic={topic_name}, subscription={subscription_name}")

        payload_converter = self._get_payload_converter_from_method(func)

        async def wrap_handler(receiver: ServiceBusReceiver, msg: ServiceBusReceivedMessage):
            try:
                # Convert message to correct payload type
                parsed_message = jsons.loads(str(msg), dict)
                payload = payload_converter(parsed_message)

                # Call the decorated function
                result = await func(payload)

                # Handle the response
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

        func_name = func.__qualname__
        subscription = Subscription(
            topic=topic_name,
            subscription_name=subscription_name,
            handler=wrap_handler,
            func_name=func_name,
            max_message_count=max_message_count,
            max_wait_time=max_wait_time,
            max_lock_renewal_duration=max_lock_renewal_duration,
        )
        return subscription

    async def _process_subscription(self, servicebus_client: ServiceBusClient, subscription: Subscription):
        receiver = servicebus_client.get_subscription_receiver(
            topic_name=subscription.topic,
            subscription_name=subscription.subscription_name,
        )
        # TODO - set up a logger for the subscription that includes the topic and subscription with log output

        max_message_count = subscription.max_message_count or self.max_message_count
        max_wait_time = subscription.max_wait_time or self.max_wait_time
        max_lock_renewal_duration = subscription.max_lock_renewal_duration or self.max_lock_renewal_duration
        async with receiver:
            # AutoLockRenewer performs message lock renewal (for long message processing)
            renewer = AutoLockRenewer(max_lock_renewal_duration=max_lock_renewal_duration)

            self.logger.info(
                f"👂 Starting message receiver for {subscription.func_name} (topic={subscription.topic}, subscription={subscription.subscription_name}..."
            )
            while not self._is_cancelled:
                # TODO: Add back-off logic when no messages?
                self.logger.debug("Receiving messages...")
                received_msgs = await receiver.receive_messages(
                    max_message_count=max_message_count, max_wait_time=max_wait_time
                )

                if len(received_msgs) == 0:
                    self.logger.debug(f"No messages received(topic={subscription.topic})")
                    continue

                self.logger.info(f"📦 Batch received, size =  {len(received_msgs)}")
                start = timer()

                # Set up message renewal for the batch
                for msg in received_msgs:
                    self.logger.debug(f"Received message {msg.message_id}, registering for renewal")
                    renewer.register(receiver, msg)

                # process messages in parallel
                await asyncio.gather(*[subscription.handler(receiver, msg) for msg in received_msgs])
                end = timer()
                duration = end - start
                self.logger.info(f"📦 Batch done, size={len(received_msgs)}, duration={duration}s")

            self.logger.info(
                f"Finished processing messages for {subscription.func_name} (topic={subscription.topic}, subscription={subscription.subscription_name})"
            )

    async def run(self):
        """Run the consumer app, i.e. begin processing messages from the Service Bus subscriptions"""

        # TODO - ensure only a single runner, check not cancelled, ...

        if len(self._subscriptions) == 0:
            raise Exception("No consumers registered - ensure you have added @consumer decorators to your handlers")

        workload_identity_credential = None
        servicebus_client = None

        self.logger.info("Connecting to service bus...")
        if AZURE_CLIENT_ID and AZURE_TENANT_ID and AZURE_AUTHORITY_HOST and AZURE_FEDERATED_TOKEN_FILE:
            self.logger.info("Using workload identity credentials")
            workload_identity_credential = WorkloadIdentityCredential(
                client_id=AZURE_CLIENT_ID,
                tenant_id=AZURE_TENANT_ID,
                token_file_path=AZURE_FEDERATED_TOKEN_FILE,
            )
            servicebus_client = ServiceBusClient(
                fully_qualified_namespace=SERVICE_BUS_NAMESPACE,
                credential=workload_identity_credential,
            )
        else:
            self.logger.info("No workload identity credentials found, using connection string")
            servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR)

        try:
            async with servicebus_client:
                self.logger.info("Starting subscription processors...")
                await asyncio.gather(
                    *[
                        self._process_subscription(servicebus_client, subscription)
                        for subscription in self._subscriptions
                    ]
                )
                self.logger.info("Subscription processors completed")

        finally:
            if workload_identity_credential:
                await workload_identity_credential.close()

    def cancel(self):
        """Mark the consumer app as cancelled to shut down processing loops"""
        self._is_cancelled = True
