from typing import Optional
import asyncio
import logging
from unittest.mock import patch

from .consumer_app import ConsumerApp, ConsumerResult, StateChangeEventBase
from .test_helpers import MockServiceBusClientBuilder, run_app_with_timeout


class SampleEventStateChangeEvent(StateChangeEventBase):
    pass


class SampleEvent1StateChangeEvent(StateChangeEventBase):
    pass


class SampleEvent2StateChangeEvent(StateChangeEventBase):
    pass


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

    assert isinstance(
        received_message, SampleEventStateChangeEvent
    ), f"Unexpected message type, got {type(received_message)}"
    assert received_message.entity_id == "123", "Unexpected message body"


def test_consumer_with_no_annotation_receives_event_type():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message = None

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message):
            nonlocal received_message
            logging.info("In on_sample_event")
            received_message = message

        asyncio.run(run_app_with_timeout(app))

    assert isinstance(
        received_message, SampleEventStateChangeEvent
    ), f"Unexpected message type, got {type(received_message)}"
    assert received_message.entity_id == "123", "Unexpected message body"


def test_consumer_with_dict_annotation_receives_dict_type():
    messages = ['{"entity_id": "123"}']
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.add_messages_for_topic_subscription(
        "sample-event", "TEST_SUB", messages=messages
    ).build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        app = ConsumerApp(default_subscription_name="TEST_SUB")

        received_message = None

        @app.consume(max_wait_time=0.1)
        async def on_sample_event(message: dict):
            nonlocal received_message
            logging.info("In on_sample_event")
            received_message = message

        asyncio.run(run_app_with_timeout(app))

    assert isinstance(received_message, dict), f"Unexpected message type, got {type(received_message)}"
    assert received_message["entity_id"] == "123", "Unexpected message body"


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
