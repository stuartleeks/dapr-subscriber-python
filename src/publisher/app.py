import os
import requests
import uuid

dapr_http_port = os.getenv("DAPR_HTTP_PORT", 3500)
pubsub_name = os.getenv("PUBSUB_NAME", "pubsub")
topic_name = os.getenv("TOPIC_NAME", "new-notification")

base_url = f"http://localhost:{dapr_http_port}"


# generate a new uuid
id = str(uuid.uuid4())
result = requests.post(
    url=f"{base_url}/v1.0/publish/{pubsub_name}/{topic_name}",
    json={
        "id": id,
        "message": "Hello"
    })

print(result)
