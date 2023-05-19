default:
  just --list

dapr-init:
	dapr uninstall
	dapr init

run-subscriber:
	cd src/subscriber && \
	dapr run --app-id python-subscriber --app-port 8000 --resources-path ../../components/ -- uvicorn app:app --reload

run-publisher:
	cd src/publisher && \
	dapr run --app-id python-publisher --app-port 8001 --resources-path ../../components/ python app.py