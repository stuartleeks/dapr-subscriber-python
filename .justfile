_default:
  @just --list --unsorted

# run the subscriber-sdk-direct app locally to receive messages
run-subscriber-sdk-direct:
	cd src/subscriber-sdk-direct && \
	python app.py

# run the subscriber-sdk-simplified app locally to receive messages
run-subscriber-sdk-simplified:
	cd src/subscriber-sdk-simplified && \
	DEFAULT_SUBSCRIPTION_NAME=subscriber-sdk-simplified python app.py

# run the publisher locally to submit a message
run-publisher topic="task-created" count="1":
	cd src/publisher && \
	python app.py {{topic}} {{count}}

# deploy (create AKS cluster, deploy services etc)
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

# Un-deploy subscribers to Kubernetes components)
undeploy-from-k8s:
	./scripts/undeploy-from-k8s.sh

py-format:
	black src

test:
	pytest -v 