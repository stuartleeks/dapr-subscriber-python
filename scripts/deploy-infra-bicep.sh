#!/bin/bash
set -e


#
# This script generates the bicep parameters file and then uses that to deploy the infrastructure
# An output.json file is generated in the project root containing the outputs from the deployment
# The output.json format is consistent between Terraform and Bicep deployments
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [[ -f "$script_dir/../.env" ]]; then
	source "$script_dir/../.env"
fi

if [[ -z "$RESOURCE_PREFIX" ]]; then
	echo 'RESOURCE_PREFIX not set - ensure you have specifed a value for it in your .env file' 1>&2
	exit 6
fi

az group create --name $RESOURCE_GROUP --location $LOCATION

cat << EOF > "$script_dir/../infra/azuredeploy.parameters.json"
{
  "\$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "resourceNamePrefix": {
      "value": "${RESOURCE_PREFIX}"
    }
  }
}
EOF

output_file="$script_dir/../infra/output.json"
output_bak_file="$script_dir/../infra/output.bak"
deployment_name="deployment-${USERNAME}-${LOCATION}"
cd infra
echo "Deploying to $RESOURCE_GROUP in $LOCATION"
result=$(az deployment group create \
	--resource-group $RESOURCE_GROUP \
  --template-file main.bicep \
  --name "$deployment_name" \
  --parameters azuredeploy.parameters.json \
  --output json)
# Capture output in result env var and pass to jq in a separate step
# This avoids creating an empty output.json file if the deployment fails
if [[ -f "$output_file" ]]; then
  if [[ -f "$output_bak_file" ]]; then
    rm "$output_bak_file"
  fi
  mv "$output_file" "$output_bak_file"
fi
echo "$result" | jq "[.properties.outputs | to_entries | .[] | {key:.key, value: .value.value}] | from_entries" > "$script_dir/../infra/output.json"

echo "Ensure k8s-extension extension is installed"
extension_installed=$(az extension list --query "length([?contains(name, 'k8s-extension')])")
if [[ $extension_installed -eq 0 ]]; then
  echo "Installing k8s-extension extension for az CLI"
  az extension add --name k8s-extension
fi

provider_state=$(az provider list --query "[?contains(namespace,'Microsoft.KubernetesConfiguration')] | [0].registrationState" -o tsv)
if [[ $provider_state != "Registered" ]]; then
  echo "Registering Microsoft.KubernetesConfiguration provider"
  az provider register --namespace Microsoft.KubernetesConfiguration
fi

resource_group=$(jq -r '.rg_name' < "$output_file")
if [[ ${#resource_group} -eq 0 ]]; then
  echo 'ERROR: Missing output value rg_name' 1>&2
  exit 6
fi

managed_identity_name=$(jq -r '.managed_identity_name' < "$output_file")
if [[ ${#managed_identity_name} -eq 0 ]]; then
  echo 'ERROR: Missing output value managed_identity_name' 1>&2
  exit 6
fi

aks_name=$(jq -r '.aks_name' < "$output_file")
if [[ ${#aks_name} -eq 0 ]]; then
  echo 'ERROR: Missing output value aks_name' 1>&2
  exit 6
fi

dapr_installed=$(az k8s-extension list --resource-group $RESOURCE_GROUP --cluster-name $aks_name --cluster-type managedClusters --query "length([?name=='dapr'])" -o tsv)
if [[ "$dapr_installed" == "1" ]]; then
  echo "Dapr extension already installed"
else
  echo "Create Dapr extension for AKS cluster"
  az k8s-extension create --cluster-type managedClusters \
  --cluster-name $aks_name \
  --resource-group $RESOURCE_GROUP \
  --name dapr \
  --extension-type Microsoft.Dapr
fi