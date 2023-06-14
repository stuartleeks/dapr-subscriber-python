from typing import Optional
import asyncio
import logging
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver
from azure.servicebus.amqp import AmqpAnnotatedMessage
from azure.servicebus import ServiceBusReceivedMessage
from azure.servicebus._common.utils import utc_now


from .consumer_app import ConsumerApp, ConsumerResult, StateChangeEventBase


# Based on https://github.com/Azure/azure-sdk-for-python/blob/1356c85959f4ba182a92491f6d99d016411c8ab1/sdk/servicebus/azure-servicebus/tests/mocks.py#L18
class MockReceivedMessage(ServiceBusReceivedMessage):
    def __init__(self, prevent_renew_lock=False, exception_on_renew_lock=False, **kwargs):
        self._lock_duration = kwargs.get("lock_duration", 2)

        # Create AmqpAnnotatedMessage from value_body as per:
        # https://github.com/Azure/azure-sdk-for-python/blob/28e19bd7d8221479b9091f70aa6a84d40c3549a0/sdk/servicebus/azure-servicebus/samples/async_samples/send_and_receive_amqp_annotated_message_async.py#L49-L60
        # value_body = kwargs.pop("value_body", None)
        data_body = kwargs.pop("data_body", None)
        value_message = AmqpAnnotatedMessage(
            # value_body=value_body,
            data_body=data_body,
        )
        self._raw_amqp_message = value_message
        self.message_id = "todo-message-id"

        self._received_timestamp_utc = utc_now()
        self.locked_until_utc = self._received_timestamp_utc + timedelta(seconds=self._lock_duration)
        self._settled = False
        # self._receiver = MockReceiver()
        self._receiver = kwargs.pop("receiver", None)

        self._prevent_renew_lock = prevent_renew_lock
        self._exception_on_renew_lock = exception_on_renew_lock

    @property
    def _lock_expired(self):
        if self.locked_until_utc and self.locked_until_utc <= utc_now():
            return True
        return False

    @property
    def locked_until_utc(self):
        return self._locked_until_utc

    @locked_until_utc.setter
    def locked_until_utc(self, value):
        self._locked_until_utc = value


class MockServiceBusClientBuilder:
    _topics: dict  # key: topic name, value: (dict keyed on subscription name, value: list of messages)
    _topic_subscription_receivers = dict  # [str, ServiceBusReceiver]  # keyed on <topic_name>|<subscription_name>

    def __init__(self):
        self._topics = {}
        self._topic_subscription_receivers = {}

    def add_messages_for_topic_subscription(self, topic_name: str, subscription_name: str, messages: list[str]):
        topic = self._topics.get(topic_name)
        if topic is None:
            topic = {}
            self._topics[topic_name] = topic

        topic_subscription = topic.get(subscription_name)
        if topic_subscription is not None:
            raise Exception(f"Messages already added for topic {topic_name} and subscription {subscription_name}")

        topic[subscription_name] = messages
        return self

    def get_subscription_receiver(self, topic_name, subscription_name):
        key = f"{topic_name}|{subscription_name}"
        receiver = self._topic_subscription_receivers.get(key)
        if not receiver is None:
            return receiver

        # else create a new receiver
        topic = self._topics.get(topic_name)
        if topic is None:
            raise Exception(f"No messages added for topic {topic_name}")
        messages = topic.get(subscription_name)
        if messages is None:
            raise Exception(f"No messages added for topic {topic_name} and subscription {subscription_name}")

        receiver = AsyncMock(spec=ServiceBusReceiver)
        receiver._running = False

        async def receive_messages(max_message_count=None, max_wait_time=None):
            nonlocal messages
            logging.info("In receive_messages")
            if messages == []:
                logging.info(f"No messages to return - sleeping (max_wait_time: {max_wait_time})")
                await asyncio.sleep(max_wait_time or 1)
                return []

            messages_to_return = [MockReceivedMessage(data_body=message, receiver=receiver) for message in messages]
            messages = []
            logging.info(f"returning messages: {messages_to_return}")
            return messages_to_return

        receiver.receive_messages = receive_messages

        # save receiver (enables us to retrieve the receiver in the test code to make assertions on it)
        self._topic_subscription_receivers[key] = receiver

        return receiver

    def build(self):
        mock_sb_client = AsyncMock(spec=ServiceBusClient)
        mock_sb_client.get_subscription_receiver = Mock(side_effect=self.get_subscription_receiver)
        return mock_sb_client


async def run_app_with_timeout(app: ConsumerApp, timeout_seconds: int = 0.1, filter: Optional[list[str]] = None):
    async def cancel_after_n_seconds(n):
        await asyncio.sleep(n)
        app.cancel()

    logging.info("Calling app.run...")
    await asyncio.gather(app.run(filter=filter), cancel_after_n_seconds(timeout_seconds))


class SampleEventStateChangeEvent(StateChangeEventBase):
    def __init__(self, entity_id: str):
        super().__init__(entity_type="sample", new_state="event", entity_id=entity_id)

    def from_dict(data: dict):
        logging.info(f"In SampleEventStateChangeEvent.from_dict: {dict}")
        return SampleEventStateChangeEvent(data["entity_id"])


class SampleEvent1StateChangeEvent(StateChangeEventBase):
    def __init__(self, entity_id: str):
        super().__init__(entity_type="sample", new_state="event", entity_id=entity_id)

    def from_dict(data: dict):
        logging.info(f"In SampleEvent1StateChangeEvent.from_dict: {dict}")
        return SampleEvent1StateChangeEvent(data["entity_id"])


class SampleEvent2StateChangeEvent(StateChangeEventBase):
    def __init__(self, entity_id: str):
        super().__init__(entity_type="sample", new_state="event", entity_id=entity_id)

    def from_dict(data: dict):
        logging.info(f"In SampleEvent2StateChangeEvent.from_dict: {dict}")
        return SampleEvent2StateChangeEvent(data["entity_id"])


def test_consumer_receives_single_message():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message = None

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message: SampleEventStateChangeEvent):
            nonlocal received_message
            logging.info("In on_sample_event")
            received_message = message

        asyncio.run(run_app_with_timeout(app))

    assert isinstance(received_message, SampleEventStateChangeEvent), "Unexpected message type"
    assert received_message.entity_id == "123", "Unexpected message body"


def test_consumer_completes_message_when_no_return_value():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message: SampleEventStateChangeEvent):
            logging.info("In on_sample_event")

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app, timeout_seconds=0.1))

    mock_receiver = mock_client_builder.get_subscription_receiver("sample-event", "TEST_SUB")
    assert mock_receiver.complete_message.call_count == 1, "Message not completed"
    completed_message = mock_receiver.complete_message.call_args[0][0]
    assert str(completed_message) == '{"entity_id": "123"}', "Unexpected message completed"


def test_consumer_completes_message_when_success_is_returned():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message: SampleEventStateChangeEvent):
            logging.info("In on_sample_event")
            return ConsumerResult.SUCCESS

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app))

    mock_receiver = mock_client_builder.get_subscription_receiver("sample-event", "TEST_SUB")
    assert mock_receiver.complete_message.call_count == 1, "Message not completed"
    completed_message = mock_receiver.complete_message.call_args[0][0]
    assert str(completed_message) == '{"entity_id": "123"}', "Unexpected message completed"


def test_consumer_abandons_message_when_retry_is_returned():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message: SampleEventStateChangeEvent):
            logging.info("In on_sample_event")
            return ConsumerResult.RETRY

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app))

    mock_receiver = mock_client_builder.get_subscription_receiver("sample-event", "TEST_SUB")
    assert mock_receiver.abandon_message.call_count == 1, "Message not abandoned"
    abandoned_message = mock_receiver.abandon_message.call_args[0][0]
    assert str(abandoned_message) == '{"entity_id": "123"}', "Unexpected message abandoned"


def test_consumer_abandons_message_when_handler_raises_exception():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message: SampleEventStateChangeEvent):
            logging.info("In on_sample_event")
            raise Exception("Something went wrong")

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app))

    mock_receiver = mock_client_builder.get_subscription_receiver("sample-event", "TEST_SUB")
    assert mock_receiver.abandon_message.call_count == 1, "Message not abandoned"
    abandoned_message = mock_receiver.abandon_message.call_args[0][0]
    assert str(abandoned_message) == '{"entity_id": "123"}', "Unexpected message abandoned"


def test_consumer_dead_letters_message_when_retry_is_returned():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message = None

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message: SampleEventStateChangeEvent):
            nonlocal received_message
            logging.info("In on_sample_event")
            received_message = message
            return ConsumerResult.DROP

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app))

    mock_receiver = mock_client_builder.get_subscription_receiver("sample-event", "TEST_SUB")
    assert mock_receiver.dead_letter_message.call_count == 1, "Message not dead-lettered"
    dead_lettered_message = mock_receiver.dead_letter_message.call_args[0][0]
    assert str(dead_lettered_message) == '{"entity_id": "123"}', "Unexpected message dead-lettered"


def test_consumer_handles_multiple_subscribers():
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = (
        mock_client_builder.add_messages_for_topic_subscription(
            "sample-event1", "TEST_SUB", messages=['{"entity_id": "123"}']
        )
        .add_messages_for_topic_subscription("sample-event2", "TEST_SUB", messages=['{"entity_id": "456"}'])
        .build()
    )
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message1 = None
        received_message2 = None

        @app.consume(max_wait_time=0.1)
        async def on_sample_event1(message: SampleEvent1StateChangeEvent):
            nonlocal received_message1
            logging.info("In on_sample_event1")
            received_message1 = message
            return ConsumerResult.SUCCESS

        @app.consume(max_wait_time=0.1)
        async def on_sample_event2(message: SampleEvent2StateChangeEvent):
            nonlocal received_message2
            logging.info("In on_sample_event2")
            received_message2 = message
            return ConsumerResult.SUCCESS

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app))

    assert isinstance(received_message1, SampleEvent1StateChangeEvent), "Unexpected message type"
    assert received_message1.entity_id == "123", "Unexpected message body"
    assert isinstance(received_message2, SampleEvent2StateChangeEvent), "Unexpected message type"
    assert received_message2.entity_id == "456", "Unexpected message body"


def test_consumer_applies_filter():
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = (
        mock_client_builder.add_messages_for_topic_subscription(
            "sample-event1", "TEST_SUB", messages=['{"entity_id": "123"}']
        )
        .add_messages_for_topic_subscription("sample-event2", "TEST_SUB", messages=['{"entity_id": "456"}'])
        .build()
    )
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message1 = None
        received_message2 = None

        @app.consume(max_wait_time=0.1)
        async def on_sample_event1(message: SampleEvent1StateChangeEvent):
            nonlocal received_message1
            logging.info("In on_sample_event1")
            received_message1 = message
            return ConsumerResult.SUCCESS

        @app.consume(max_wait_time=0.1)
        async def on_sample_event2(message: SampleEvent2StateChangeEvent):
            nonlocal received_message2
            logging.info("In on_sample_event2")
            received_message2 = message
            return ConsumerResult.SUCCESS

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app, filter="sample-event2|TEST_SUB"))

    assert received_message1 is None, "Received message when subscriber should have been excluded by filter"
    assert isinstance(received_message2, SampleEvent2StateChangeEvent), "Unexpected message type"
    assert received_message2.entity_id == "456", "Unexpected message body"


# TODO
#  - test renew lock
#  - test concurrent message handling
#  - test multiple subscriptions
#  - test cancellation waits for messages but doesn't send new ones
