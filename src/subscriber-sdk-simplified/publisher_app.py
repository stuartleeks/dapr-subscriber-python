import asyncio
import logging
import sys
import uuid
from timeit import default_timer as timer

from pubsub import models, publish

#
# This application demonstrates how the Service Bus SDK API could be abstracted to
# provde a simplified dev experience for subscribing to messages through
# the use of helper code and conventions.
#


logging.basicConfig(level=logging.INFO)
logging.getLogger("azure.servicebus._pyamqp.aio").setLevel(logging.WARNING)
logging.getLogger("PubSub.ConsumerApp").setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


allowed_topics = ["task-created", "task-updated", "user-created"]

topic_types = {
    "task-created": models.TaskCreatedStateChangeEvent,
    "task-updated": models.TaskUpdatedStateChangeEvent,
    "user-created": models.UserCreatedStateChangeEvent,
}

if len(sys.argv) != 3:
    print(f"ℹ  Usage: {sys.argv[0]} <{'|'.join(allowed_topics)}> <count>")
    sys.exit(1)

topic_name = sys.argv[1]
if topic_name not in allowed_topics:
    print(f"ℹ Invalid topic: {topic_name}")
    sys.exit(1)

count = int(sys.argv[2])


async def run_publish():
    print(f"🏃 Publishing {count} message(s) to topic '{topic_name}'...")
    start = timer()
    for i in range(0, count):
        # generate a new uuid
        id = str(uuid.uuid4())
        try:
            message = topic_types[topic_name](entity_id=id)
            await publish(message)
            print(f"✅ Published message with id {id}")
        except Exception as e:
            print(f"ℹ❌ Failed to publish message. Error: {e}")

    end = timer()
    duration = end - start
    print(f"👋 Done! (took {duration} seconds for {count} messages)")


asyncio.run(run_publish())
