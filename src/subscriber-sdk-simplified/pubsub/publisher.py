import logging
import os

from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusSender

from .consumer_app import StateChangeEventBase
from .consumer_app import get_topic_name_from_event_class
from .servicebus_connection import get_servicebus_client

_logger = logging.getLogger(__name__)

_servicebus_client = None
# dict keyed on topic name, value is ServiceBusSender
_topic_senders = {}

# TODO - do we want to initialise the service bus client up-front? (i.e. to validate connection prior to publishing)


def _get_servicebus_client():
    global _servicebus_client
    if _servicebus_client is None:
        (_servicebus_client, workload_identity_credential) = get_servicebus_client(_logger)
    return _servicebus_client


def _get_topic_sender(topic_name: str) -> ServiceBusSender:
    topic_sender = _topic_senders.get(topic_name)
    if topic_sender is None:
        _logger.debug(f"Creating service bus sender for topic '{topic_name}'")
        topic_sender = _get_servicebus_client().get_topic_sender(topic_name=topic_name)
        _topic_senders[topic_name] = topic_sender

    return topic_sender


# TODO - do we want publish to be async? Feels like it could be easy to make a mistake and not await it (resulting in not publishing)


async def publish(message: StateChangeEventBase):
    # Determine topic to publish to from message type
    topic_name = get_topic_name_from_event_class(type(message))

    # Get topic sender
    topic_sender = _get_topic_sender(topic_name)

    # Send message
    _logger.info(f"Publishing message to topic '{topic_name}'")
    await topic_sender.send_messages(ServiceBusMessage(message.json()))
