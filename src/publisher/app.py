import os
import sys
import requests
import uuid

dapr_http_port = os.getenv("DAPR_HTTP_PORT", 3500)
pubsub_name = os.getenv("PUBSUB_NAME", "notifications-pubsub-publisher")

allowed_topics = ["task", "user"]

if len(sys.argv) != 3:
    print(f"ℹ  Usage: {sys.argv[0]} <{'|'.join(allowed_topics)}> <count>")
    sys.exit(1)

topic_base = sys.argv[1]
if topic_base not in allowed_topics:
    print(f"ℹ Invalid topic_base: {topic_base}")
    sys.exit(1)
topic_name = f"{topic_base}-notifications"

count = int(sys.argv[2])


base_url = f"http://localhost:{dapr_http_port}"


print(f"🏃 Publishing {count} message(s) to topic '{topic_name}' in pubsub '{pubsub_name}'...")

for i in range(0, count):
    # generate a new uuid
    id = str(uuid.uuid4())
    result = requests.post(
        url=f"{base_url}/v1.0/publish/{pubsub_name}/{topic_name}",
        json={
            "entity_id": id,
            "entity_type": "task",
            "new_state": "completed"
        })

    if result.status_code >= 200 and result.status_code < 300:
        print(f"✅ Published message with id {id}")
    else:
        print(f"ℹ❌ Failed to publish message. status code: {result.status_code}, response: '{result.text}'")

print("👋 Done!")