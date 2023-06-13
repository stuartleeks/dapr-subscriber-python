import asyncio
import logging
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver
from azure.servicebus.amqp import AmqpAnnotatedMessage
from azure.servicebus import ServiceBusReceivedMessage
from azure.servicebus._common.utils import utc_now


from .consumer_app import ConsumerApp, StateChangeEventBase

## TODO - refactor helper code


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


def mock_get_subscription_receiver(expected_topic_name, expected_subscription_name, messages: list[str] = []):
    receiver = None

    def side_effect(topic_name, subscription_name):
        nonlocal receiver
        if receiver is not None:
            return receiver

        if topic_name != expected_topic_name:
            assert False, "Unexpected topic name: " + topic_name
        if subscription_name != expected_subscription_name:
            assert False, "Unexpected subscription name: " + subscription_name

        mock_receiver = AsyncMock(spec=ServiceBusReceiver)
        mock_receiver._running = False

        async def receive_messages(max_message_count=None, max_wait_time=None):
            nonlocal messages
            logging.info("In receive_messages")
            if messages == []:
                logging.info(f"No messages to return - sleeping (max_wait_time: {max_wait_time})")
                await asyncio.sleep(max_wait_time or 1)
                return []

            messages_to_return = [
                MockReceivedMessage(data_body=message, receiver=mock_receiver) for message in messages
            ]
            messages = []
            logging.info(f"returning messages: {messages_to_return}")
            return messages_to_return

        mock_receiver.receive_messages = receive_messages

        # mock_receiver.receive_messages = AsyncMock(side_effect=[messages])

        return mock_receiver

    return side_effect


async def run_app_with_timeout(app: ConsumerApp, timeout_seconds: int = 1):
    async def cancel_after_n_seconds(n):
        await asyncio.sleep(n)
        app.cancel()

    logging.info("Calling app.run...")
    await asyncio.gather(app.run(), cancel_after_n_seconds(timeout_seconds))


class SampleEventStateChangeEvent(StateChangeEventBase):
    def __init__(self, entity_id: str):
        super().__init__(entity_type="sample", new_state="event", entity_id=entity_id)

    def from_dict(data: dict):
        logging.info(f"In SampleEventStateChangeEvent.from_dict: {dict}")
        return SampleEventStateChangeEvent(data["entity_id"])


def test_consumer_receives_single_message():
    global on_message

    mock_sb_client = AsyncMock(spec=ServiceBusClient)
    messages = ['{"entity_id": "123"}']
    mock_sb_client.get_subscription_receiver = Mock(
        side_effect=mock_get_subscription_receiver("sample-event", "TEST_SUB", messages=messages),
    )
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message = None

        async def on_sample_event(message: SampleEventStateChangeEvent):
            nonlocal received_message
            logging.info("In on_sample_event")
            received_message = message

        # Directly call consume rather than decorating to keep tests encapsulated
        app.consume(on_sample_event, max_wait_time=0.1)

        asyncio.run(run_app_with_timeout(app, timeout_seconds=0.1))

    assert isinstance(received_message, SampleEventStateChangeEvent), "Unexpected message type"
    assert received_message.entity_id == "123", "Unexpected message body"


def test_consumer_completes_message_when_no_return_value():
    global on_message

    mock_sb_client = AsyncMock(spec=ServiceBusClient)
    messages = ['{"entity_id": "123"}']
    # TODO - temp hack to re-use existing function - clean up if this approach works overall
    mock_receiver = mock_get_subscription_receiver("sample-event", "TEST_SUB", messages=messages)(
        "sample-event", "TEST_SUB"
    )
    mock_sb_client.get_subscription_receiver = Mock(return_value=mock_receiver)
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message = None

        async def on_sample_event(message: SampleEventStateChangeEvent):
            nonlocal received_message
            logging.info("In on_sample_event")
            received_message = message

        # Directly call consume rather than decorating to keep tests encapsulated
        app.consume(on_sample_event, max_wait_time=0.1)

        # Here we set timeout_seconds to 1 which will invoke the cancel() method after 1 second
        # The message processor will sleep for 2 seconds
        asyncio.run(run_app_with_timeout(app, timeout_seconds=0.1))

    assert isinstance(received_message, SampleEventStateChangeEvent), "Unexpected message type"
    assert received_message.entity_id == "123", "Unexpected message body"
    assert mock_receiver.complete_message.call_count == 1, "Message not completed"
    completed_message = mock_receiver.complete_message.call_args[0][0]
    assert str(completed_message) == '{"entity_id": "123"}', "Unexpected message completed"
