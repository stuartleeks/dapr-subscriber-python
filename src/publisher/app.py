import json
import os
import sys
import uuid
from timeit import default_timer as timer
from azure.servicebus import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from dotenv import load_dotenv
from azure.identity import WorkloadIdentityCredential

#
# This application demonstrates how to work directly with the Service Bus SDK
# to subscribe to a topic and receive events.
#

# Currently working with Azure Service Bus connection string - see the following for Azure AD auth:
# https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-python-how-to-use-queues?tabs=connection-string#authenticate-the-app-to-azure

load_dotenv()

CONNECTION_STR = os.environ.get('SERVICE_BUS_CONNECTION_STRING', '')
AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID', '')
AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID', '')
AZURE_AUTHORITY_HOST = os.getenv('AZURE_AUTHORITY_HOST', '')
AZURE_FEDERATED_TOKEN_FILE = os.getenv('AZURE_FEDERATED_TOKEN_FILE', '')
SERVICE_BUS_NAMESPACE = os.getenv('SERVICE_BUS_NAMESPACE', '')

allowed_topics = ["task-created", "task-updated",
                  "user-created", "user-inactive"]

if len(sys.argv) != 3:
    print(f"ℹ  Usage: {sys.argv[0]} <{'|'.join(allowed_topics)}> <count>")
    sys.exit(1)

topic_name = sys.argv[1]
if topic_name not in allowed_topics:
    print(f"ℹ Invalid topic: {topic_name}")
    sys.exit(1)

count = int(sys.argv[2])


workload_identity_credential = None
servicebus_client = None

print("Connecting to service bus...", flush=True)
if AZURE_CLIENT_ID and AZURE_TENANT_ID and AZURE_AUTHORITY_HOST and AZURE_FEDERATED_TOKEN_FILE:
    print("Using workload identity credentials", flush=True)
    workload_identity_credential = WorkloadIdentityCredential(
        client_id=AZURE_CLIENT_ID, tenant_id=AZURE_TENANT_ID, token_file_path=AZURE_FEDERATED_TOKEN_FILE)
    servicebus_client = ServiceBusClient(
        fully_qualified_namespace=SERVICE_BUS_NAMESPACE, credential=workload_identity_credential)
else:
    print("No workload identity credentials found, using connection string", flush=True)
    servicebus_client = ServiceBusClient.from_connection_string(
        conn_str=CONNECTION_STR)

with servicebus_client:
    print("Creating service bus sender...", flush=True)
    sender = servicebus_client.get_topic_sender(
        topic_name=topic_name
    )

    print(
        f"🏃 Publishing {count} message(s) to topic '{topic_name}'...")
    start = timer()

    for i in range(0, count):
        # generate a new uuid
        id = str(uuid.uuid4())
        try:
            # TODO batch messages
            message = ServiceBusMessage(json.dumps({
                    "entity_id": id,
                }))
            sender.send_messages(message)
            print(f"✅ Published message with id {id}")
        except Exception as e:
            print(
                f"ℹ❌ Failed to publish message. Error: {e}")

    end = timer()
    duration = end - start
    print(f"👋 Done! (took {duration} seconds for {count} messages)")
