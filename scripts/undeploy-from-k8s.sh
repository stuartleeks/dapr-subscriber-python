#!/bin/bash
set -e

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# In deploy file we run envsubst to replace the variables with values from the environment
# On undeploy, we don't need to do that since the delete just needs the names
echo "### Undeploying subscriber-sdk-direct"
kubectl delete -f "$script_dir/../src/subscriber-sdk-direct/deploy.yaml"

echo "### Undeploying subscriber-sdk-simplified"
kubectl delete -f "$script_dir/../src/subscriber-sdk-simplified/deploy.yaml"

echo "### Undeploying components"
kubectl delete -f "$script_dir/../components.k8s"

