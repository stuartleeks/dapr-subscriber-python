import logging
import os

from azure.identity.aio import WorkloadIdentityCredential
from azure.servicebus import ServiceBusMessage
from azure.servicebus.aio import ServiceBusClient

from .consumer_app import StateChangeEventBase
from .consumer_app import get_topic_name_from_event_class

from dotenv import load_dotenv

# TODO - refactor config storage/handling
load_dotenv()

CONNECTION_STR = os.environ.get("SERVICE_BUS_CONNECTION_STRING")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_AUTHORITY_HOST = os.getenv("AZURE_AUTHORITY_HOST", "")
AZURE_FEDERATED_TOKEN_FILE = os.getenv("AZURE_FEDERATED_TOKEN_FILE", "")
SERVICE_BUS_NAMESPACE = os.getenv("SERVICE_BUS_NAMESPACE", "")


_logger = logging.getLogger(__name__)

_servicebus_client = None
# dict keyed on topic name, value is ServiceBusSender
_topic_senders = {}

# TODO - do we want to initialise the service bus client up-front? (i.e. to validate connection prior to publishing)


def _get_servicebus_client():
    global _servicebus_client
    if _servicebus_client is None:
        workload_identity_credential = None

        _logger.info("Connecting to service bus...")
        if AZURE_CLIENT_ID and AZURE_TENANT_ID and AZURE_AUTHORITY_HOST and AZURE_FEDERATED_TOKEN_FILE:
            _logger.info("Using workload identity credentials")
            workload_identity_credential = WorkloadIdentityCredential(
                client_id=AZURE_CLIENT_ID,
                tenant_id=AZURE_TENANT_ID,
                token_file_path=AZURE_FEDERATED_TOKEN_FILE,
            )
            _servicebus_client = ServiceBusClient(
                fully_qualified_namespace=SERVICE_BUS_NAMESPACE,
                credential=workload_identity_credential,
            )
        else:
            _logger.info("No workload identity credentials found, using connection string")
            _servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR)
    return _servicebus_client


def _get_topic_sender(topic_name: str):
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
