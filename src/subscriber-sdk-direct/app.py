import asyncio
import time
import jsons
import os
from azure.servicebus.aio import ServiceBusClient, AutoLockRenewer, ServiceBusReceiver
from azure.servicebus import ServiceBusReceivedMessage
from dotenv import load_dotenv
from azure.identity.aio import WorkloadIdentityCredential

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


TOPIC_NAME = "task-created"
SUBSCRIPTION_NAME = "subscriber-sdk-direct"

async def wrap_handler(receiver: ServiceBusReceiver, handler, msg: ServiceBusReceivedMessage):
    try:
        # TODO - allow success/retry/drop to be returned from handler
        parsed_message = jsons.loads(str(msg), dict)
        await handler(parsed_message)
        await receiver.complete_message(msg)
    except Exception as e:
        print(f"Error processing message: {e}")
        await receiver.abandon_message(msg, reason=str(e))


async def process_messages(handler):
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

    try:
        async with servicebus_client:
            print("Creating service bus receiver...", flush=True)
            receiver = servicebus_client.get_subscription_receiver(
                topic_name=TOPIC_NAME,
                subscription_name=SUBSCRIPTION_NAME
            )
            async with receiver:
                # AutoLockRenewer performs message lock renewal (for long message processing)
                # TODO - do we want to provide a callback for renewal failure? What action would we take?
                # TODO - make max_lock_renewal_duration configurable
                renewer = AutoLockRenewer(max_lock_renewal_duration=5*60)

                print("Starting message receiver...", flush=True)
                while True:
                    # TODO: Add back-off logic when no messages?
                    # TODO: Add max message count etc to config
                    received_msgs = await receiver.receive_messages(max_message_count=10, max_wait_time=30)

                    # Set up message renewal for the batch
                    for msg in received_msgs:
                        renewer.register(receiver, msg)

                    # process messages in parallel
                    await asyncio.gather(*[wrap_handler(receiver, handler, msg) for msg in received_msgs])
    finally:
        if workload_identity_credential:
            await workload_identity_credential.close()

async def on_task_notification(msg):
    entity_id = msg["entity_id"]
    print(f"🔔 [{entity_id}] Received message: ", msg, flush=True)
    for i in range(0, 5):
        print(
            f"💤 [{entity_id}] sleeping to simulate long-running-work (i={i})...", flush=True)
        await asyncio.sleep(2)
    print(f"✅ [{entity_id}] Done sleeping", flush=True)


asyncio.run(process_messages(on_task_notification))
