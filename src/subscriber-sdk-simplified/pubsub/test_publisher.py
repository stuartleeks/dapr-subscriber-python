from typing import Optional
import asyncio
import logging
import pytest
from unittest.mock import patch

from .publisher import publish
from .consumer_app import StateChangeEventBase
from .test_helpers import MockServiceBusClientBuilder, run_app_with_timeout


class SamplePublisherStateChangeEvent(StateChangeEventBase):
    pass


@pytest.mark.asyncio
async def test_publish():
    mock_client_builder = MockServiceBusClientBuilder()
    mock_sb_client = mock_client_builder.build()
    with patch("azure.servicebus.aio.ServiceBusClient.from_connection_string", return_value=mock_sb_client):
        await publish(SamplePublisherStateChangeEvent(entity_id="123"))

    assert len(mock_client_builder.sentMessages) == 1, "Expected a single message to be sent"
    message = mock_client_builder.sentMessages[0]

    assert message.topic_name == "sample-publisher", "Unexpected topic name"
    assert str(message.message) == '{"entity_id": "123"}', "Unexpected message body"

    assert len(mock_client_builder.topic_senders) == 1, "Expected a single topic sender to be created"
    topic_sender = mock_client_builder.topic_senders[0]
    assert topic_sender.send_messages.call_count == 1, "Expected a single call to send_messages"
    assert topic_sender.entity_name == "sample-publisher", "Unexpected topic name"
