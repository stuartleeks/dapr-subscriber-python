import asyncio
import logging
from datetime import timedelta
from typing import Optional
from unittest.mock import AsyncMock, Mock

from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver
from azure.servicebus.amqp import AmqpAnnotatedMessage
from azure.servicebus import ServiceBusReceivedMessage
from azure.servicebus._common.utils import utc_now

from .consumer_app import ConsumerApp


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

    def get_subscription_receiver(self, topic_name, subscription_name, auto_lock_renewer=None):
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
