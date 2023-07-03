import logging
import os
from azure.identity.aio import WorkloadIdentityCredential
from azure.servicebus.aio import ServiceBusClient

from dotenv import load_dotenv

load_dotenv()

CONNECTION_STR = os.environ.get("SERVICE_BUS_CONNECTION_STRING")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_AUTHORITY_HOST = os.getenv("AZURE_AUTHORITY_HOST", "")
AZURE_FEDERATED_TOKEN_FILE = os.getenv("AZURE_FEDERATED_TOKEN_FILE", "")
SERVICE_BUS_NAMESPACE = os.getenv("SERVICE_BUS_NAMESPACE", "")


def get_servicebus_client(logger: logging.Logger):
    workload_identity_credential = None

    logger.info("Connecting to service bus...")
    if AZURE_CLIENT_ID and AZURE_TENANT_ID and AZURE_AUTHORITY_HOST and AZURE_FEDERATED_TOKEN_FILE:
        logger.info("Using workload identity credentials")
        workload_identity_credential = WorkloadIdentityCredential(
            client_id=AZURE_CLIENT_ID,
            tenant_id=AZURE_TENANT_ID,
            token_file_path=AZURE_FEDERATED_TOKEN_FILE,
        )
        if not SERVICE_BUS_NAMESPACE:
            raise Exception("No service bus namespace found (required when using workload identity)")
        servicebus_client = ServiceBusClient(
            fully_qualified_namespace=SERVICE_BUS_NAMESPACE,
            credential=workload_identity_credential,
        )
    else:
        logger.info("No workload identity credentials found, using connection string")
        if not CONNECTION_STR:
            raise Exception("No connection string found")
        servicebus_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR)

    return (servicebus_client, workload_identity_credential)
