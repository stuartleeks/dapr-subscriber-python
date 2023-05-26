#!/bin/bash
set -e

#
# This script expects to find an output.json in the infra folder with the values
# from the infrastructure deployment.
# It then creates the env files etc for each component
#

script_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

output_file="$script_dir/../infra/output.json"

if [[ -f "$script_dir/../.env" ]]; then
	source "$script_dir/../.env"
fi

service_bus_namespace_name=$(jq -r '.service_bus_namespace_name' < "$output_file")
if [[ ${#service_bus_namespace_name} -eq 0 ]]; then
  echo 'ERROR: Missing output value service_bus_namespace_name' 1>&2
  exit 6
fi
service_bus_connection_string=$(az servicebus namespace authorization-rule keys list --resource-group $RESOURCE_GROUP --namespace-name $service_bus_namespace_name --name RootManageSharedAccessKey --query primaryConnectionString -o tsv)

#create secret file with connection string for pubsub
cat <<EOF > "$script_dir/../components.k8s/pubsub.secret.yaml"
apiVersion: v1
data:
  connectionString: $(echo -n "$service_bus_connection_string" | base64 -w 0)
kind: Secret
metadata:
  name: servicebus-pubsub-secret
  namespace: default
type: Opaque
EOF
echo "CREATED: k8s secret file"



cat <<EOF > "$script_dir/../src/publisher/local.secret.json"
{
  "SERVICE_BUS_CONNECTION_STRING": "$service_bus_connection_string"
}
EOF
echo "CREATED: local secret file for publisher"

cat <<EOF > "$script_dir/../src/subscriber-dapr-api/local.secret.json"
{
  "SERVICE_BUS_CONNECTION_STRING": "$service_bus_connection_string"
}
EOF
echo "CREATED: local secret file for subscriber-dapr-api"

cat <<EOF > "$script_dir/../src/subscriber-dapr-simplified/local.secret.json"
{
  "SERVICE_BUS_CONNECTION_STRING": "$service_bus_connection_string"
}
EOF
echo "CREATED: local secret file for subscriber-dapr-simplified"


cat <<EOF > "$script_dir/../src/subscriber-sdk-direct/.env"
SERVICE_BUS_CONNECTION_STRING="$service_bus_connection_string"
EOF
echo "CREATED: env file for SDK subscriber-sdk-direct"

cat <<EOF > "$script_dir/../src/subscriber-sdk-simplified/.env"
SERVICE_BUS_CONNECTION_STRING="$service_bus_connection_string"
EOF
echo "CREATED: env file for SDK subscriber-sdk-simplified"
