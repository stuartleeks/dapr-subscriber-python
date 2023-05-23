#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

acr_login_server=$(jq -r '.acr_login_server' < "$script_dir/../infra/output.json")
if [[ ${#acr_login_server} -eq 0 ]]; then
  echo 'ERROR: Missing output value acr_login_server' 1>&2
  exit 6
fi

echo "### Deploying components"
kubectl apply -f "$script_dir/../components.k8s"


echo "### Deploying subscriber"
cat "$script_dir/../src/subscriber/deploy.yaml" \
  | REGISTRY_NAME=$acr_login_server envsubst \
  | kubectl apply -f -