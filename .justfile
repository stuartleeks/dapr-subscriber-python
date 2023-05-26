_default:
  @just --list --unsorted

# initialize dapr locally
dapr-init:
	dapr uninstall
	dapr init

# run the subscriber-api app locally to receive messages
run-subscriber-dapr-api env="redis":
	cd src/subscriber-dapr-api && \
	dapr run --app-id subscriber-dapr-api --app-port 8000 --resources-path ../../components.local/ -- uvicorn app:app --reload 

# run the subscriber-dapr-simplified app locally to receive messages
run-subscriber-dapr-simplified:
	cd src/subscriber-dapr-simplified && \
	dapr run --app-id subscriber-dapr-simplified --app-port 8002 --resources-path ../../components.local/ -- uvicorn --port 8002 app:app --reload 

# run the subscriber-sdk-direct app locally to receive messages
run-subscriber-sdk-direct:
	cd src/subscriber-sdk-direct && \
	python app.py

# run the subscriber-sdk-simplified app locally to receive messages
run-subscriber-sdk-simplified:
	cd src/subscriber-sdk-simplified && \
	DEFAULT_SUBSCRIPTION_NAME=subscriber-sdk-simplified python app.py

# run the publisher locally to submit a message
run-publisher topic="task" count="1":
	cd src/publisher && \
	dapr run --app-id publisher --app-port 8001 --resources-path ../../components.local/ -- python app.py {{topic}} {{count}}

# deploy (create AKS cluster, deploy dapr components, services etc)
deploy:
	./deploy.sh

# get the kubectl credentials for the AKS cluster
get-kubectl-credentials:
	./scripts/get-kube-login.sh


# build and push subscriber images (useful if you want to deploy updates to the services)
build-images:
	./scripts/docker-build-and-push.sh

# deploy subscribers to Kubernetes components (useful if you want to deploy updates to the services)
deploy-to-k8s:
	./scripts/deploy-to-k8s.sh
