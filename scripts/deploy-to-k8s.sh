#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

acr_login_server=$(jq -r '.acr_login_server' < "$script_dir/../infra/output.json")
if [[ ${#acr_login_server} -eq 0 ]]; then
  echo 'ERROR: Missing output value acr_login_server' 1>&2
  exit 6
fi

service_bus_namespace_qualified_name=$(jq -r '.service_bus_namespace_qualified_name' < "$script_dir/../infra/output.json")
if [[ ${#service_bus_namespace_qualified_name} -eq 0 ]]; then
  echo 'ERROR: Missing output value service_bus_namespace_qualified_name' 1>&2
  exit 6
fi

echo "### Deploying components"
kubectl apply -f "$script_dir/../components.k8s"


echo "### Deploying subscriber-dapr-api"
cat "$script_dir/../src/subscriber-dapr-api/deploy.yaml" \
  | REGISTRY_NAME=$acr_login_server SERVICE_BUS_NAMESPACE=$service_bus_namespace_qualified_name envsubst \
  | kubectl apply -f -

echo "### Deploying subscriber-dapr-simplified"
cat "$script_dir/../src/subscriber-dapr-simplified/deploy.yaml" \
  | REGISTRY_NAME=$acr_login_server SERVICE_BUS_NAMESPACE=$service_bus_namespace_qualified_name envsubst \
  | kubectl apply -f -

echo "### Deploying subscriber-sdk-direct"
cat "$script_dir/../src/subscriber-sdk-direct/deploy.yaml" \
  | REGISTRY_NAME=$acr_login_server SERVICE_BUS_NAMESPACE=$service_bus_namespace_qualified_name envsubst \
  | kubectl apply -f -

echo "### Deploying subscriber-sdk-simplified"
cat "$script_dir/../src/subscriber-sdk-simplified/deploy.yaml" \
  | REGISTRY_NAME=$acr_login_server SERVICE_BUS_NAMESPACE=$service_bus_namespace_qualified_name envsubst \
  | kubectl apply -f -