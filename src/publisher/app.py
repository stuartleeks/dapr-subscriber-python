import os
import requests
import uuid

dapr_http_port = os.getenv("DAPR_HTTP_PORT", 3500)
pubsub_name = os.getenv("PUBSUB_NAME", "notifications-pubsub-publisher")
topic_name = os.getenv("TOPIC_NAME", "task-notifications")

base_url = f"http://localhost:{dapr_http_port}"


print(f"🏃 Publishing message to topic '{topic_name}' in pubsub '{pubsub_name}'...")

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
