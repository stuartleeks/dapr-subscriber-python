_default:
  @just --list --unsorted

# initialize dapr locally
dapr-init:
	dapr uninstall
	dapr init

# run the subscriber app locally to receive messages
run-subscriber env="redis":
	cd src/subscriber && \
	dapr run --app-id subscriber --app-port 8000 --resources-path ../../components.local-{{env}}/ -- uvicorn app:app --reload 

# run the subscriber2 app locally to receive messages
run-subscriber2 env="redis":
	cd src/subscriber2 && \
	dapr run --app-id subscriber2 --app-port 8002 --resources-path ../../components.local-{{env}}/ -- uvicorn --port 8002 app:app --reload 

# run the publisher locally to submit a message
run-publisher env="redis":
	cd src/publisher && \
	dapr run --app-id publisher --app-port 8001 --resources-path ../../components.local-{{env}}/ python app.py

# deploy (create AKS cluster, deploy dapr components etc)
deploy:
	./deploy.sh

# get the kubectl credentials for the AKS cluster
get-kubectl-credentials:
	./scripts/get-kube-login.sh


# build Dapr services (useful if you want to deploy updates to the components)
build-dapr:
	./scripts/docker-build-and-push.sh

# deploy Dapr components (useful if you want to deploy updates to the components)
deploy-dapr:
	./scripts/dapr-deploy.sh
