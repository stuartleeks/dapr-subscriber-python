param location string = resourceGroup().location

@description('Resource name prefix')
param resourceNamePrefix string
var envResourceNamePrefix = toLower(resourceNamePrefix)

@description('Disk size (in GB) to provision for each of the agent pool nodes. Specifying 0 will apply the default disk size for that agentVMSize')
@minValue(0)
@maxValue(1023)
param aksDiskSizeGB int = 30

@description('The number of nodes for the AKS cluster')
@minValue(1)
@maxValue(50)
param aksNodeCount int = 1

@description('The size of the Virtual Machine nodes in the AKS cluster')
param aksVMSize string = 'Standard_B2s'
// param aksVMSize string = 'Standard_D2s_v3'

@description('The Service Bus SKU to use')
param serviceBusSku string = 'Standard'

/////////////////////////////////////
// Container registry
//

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2022-02-01-preview' = {
  name: '${envResourceNamePrefix}registry'
  location: location
  sku: {
    name: 'Standard'
  }
}

/////////////////////////////////////
// AKS Cluster
//

resource aks 'Microsoft.ContainerService/managedClusters@2023-03-02-preview' = {
  name: '${envResourceNamePrefix}cluster'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: 'aks'
    agentPoolProfiles: [
      {
        name: 'agentpool'
        osDiskSizeGB: aksDiskSizeGB
        count: aksNodeCount
        minCount: 1
        maxCount: aksNodeCount
        vmSize: aksVMSize
        osType: 'Linux'
        mode: 'System'
        enableAutoScaling: true
      }
    ]
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
  }
}

// Enable cluster to pull images from container registry
var roleAcrPullName = 'b24988ac-6180-42a0-ab88-20f7382dd24c'
resource contributorRoleDefinition 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: subscription()
  name: roleAcrPullName

}
resource assignAcrPullToAks 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, containerRegistry.name, aks.name, 'AssignAcrPullToAks')
  scope: containerRegistry
  properties: {
    description: 'Assign AcrPull role to AKS'
    principalId: aks.properties.identityProfile.kubeletidentity.objectId
    principalType: 'ServicePrincipal'
    roleDefinitionId: contributorRoleDefinition.id
  }
}

/////////////////////////////////////
// Service bus namespace
//

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2021-11-01' = {
  name: '${envResourceNamePrefix}sb'
  location: location
  sku: {
    name: serviceBusSku
  }
  properties: {}
}


// https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#azure-service-bus-data-receiver
var roleServiceBusDataReceiverName = '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
resource roleServiceBusDataReceiver 'Microsoft.Authorization/roleDefinitions@2018-01-01-preview' existing = {
  scope: subscription()
  name: roleServiceBusDataReceiverName
}

/////////////////////////////////////
//
// Task event topics

// task-created topic + subscriptions
resource taskCreatedTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' = {
  parent: serviceBusNamespace
  name: 'task-created'
  properties: {}
}

resource taskCreatedSubscriber1 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskCreatedTopic
  name: 'task-created-subscriber-1'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}
resource taskCreatedSubscriber2 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskCreatedTopic
  name: 'task-created-subscriber-2'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}

resource taskCreatedSubscriberSdkDirect 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskCreatedTopic
  name: 'subscriber-sdk-direct'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}
resource taskCreatedSubscriberSdkSimplified 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskCreatedTopic
  name: 'subscriber-sdk-simplified'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}

// task-updated topic + subscriptions
resource taskUpdatedTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' = {
  parent: serviceBusNamespace
  name: 'task-updated'
  properties: {}
}
resource taskUpdatedSubscriberSdkSimplified 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskUpdatedTopic
  name: 'subscriber-sdk-simplified'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}

/////////////////////////////////////
//
// User event topics

// user-created topic + subscriptions
resource userCreatedTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' = {
  parent: serviceBusNamespace
  name: 'user-created'
  properties: {}
}
resource userCreatedSubscriberSdkSimplified 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: userCreatedTopic
  name: 'subscriber-sdk-simplified'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}

// user-inactive topic + subscriptions
resource userInactiveTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' = {
  parent: serviceBusNamespace
  name: 'user-inactive'
  properties: {}
}
resource userInactiveSubscriberSdkSimplified 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: userInactiveTopic
  name: 'subscriber-sdk-simplified'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}

/////////////////////////////////////
// Application identities
//

// subscriber-sdk-simplified identity
resource subscriberSdkSimplifiedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2022-01-31-preview' = {
  name: 'subscriber-sdk-simplified'
  location: location
}
resource subscriberSdkSimplifiedFederatedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2022-01-31-preview' = {
  parent: subscriberSdkSimplifiedIdentity
  name: 'subscriber-sdk-simplified-federated-identity'
  properties: {
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:default:subscriber-sdk-simplified' // TODO - parameterise? Find a single place to set this across scripts etc?
    audiences: [ 'api://AzureADTokenExchange' ]
  }
}

resource subscriberSdkSimplifiedServiceBusReadTaskCreated 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, taskCreatedSubscriberSdkSimplified.id, subscriberSdkSimplifiedIdentity.id, roleServiceBusDataReceiver.id)
  scope: taskCreatedSubscriberSdkSimplified
  properties: {
    description: 'Assign ServiceBusDataReceiver role to subscriber-sdk-simplified for task-created/subscriber-sdk-simplified'
    principalId: subscriberSdkSimplifiedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleServiceBusDataReceiver.id
  }
}

resource subscriberSdkSimplifiedServiceBusReadTaskUpdated 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, taskUpdatedSubscriberSdkSimplified.id, subscriberSdkSimplifiedIdentity.id, roleServiceBusDataReceiver.id)
  scope: taskUpdatedSubscriberSdkSimplified
  properties: {
    description: 'Assign ServiceBusDataReceiver role to subscriber-sdk-simplified for task-updated/subscriber-sdk-simplified'
    principalId: subscriberSdkSimplifiedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleServiceBusDataReceiver.id
  }
}

resource subscriberSdkSimplifiedServiceBusReadUserCreated 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, userCreatedSubscriberSdkSimplified.id, subscriberSdkSimplifiedIdentity.id, roleServiceBusDataReceiver.id)
  scope: userCreatedSubscriberSdkSimplified
  properties: {
    description: 'Assign ServiceBusDataReceiver role to subscriber-sdk-simplified for user-created/subscriber-sdk-simplified'
    principalId: subscriberSdkSimplifiedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleServiceBusDataReceiver.id
  }
}

// subscriber-sdk-direct identity
resource subscriberSdkDirectIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2022-01-31-preview' = {
  name: 'subscriber-sdk-direct'
  location: location
}
resource subscriberSdkDirectFederatedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2022-01-31-preview' = {
  parent: subscriberSdkDirectIdentity
  name: 'subscriber-sdk-direct-federated-identity'
  properties: {
    issuer: aks.properties.oidcIssuerProfile.issuerURL
    subject: 'system:serviceaccount:default:subscriber-sdk-direct' // TODO - parameterise? Find a single place to set this across scripts etc?
    audiences: [ 'api://AzureADTokenExchange' ]
  }
}

resource subscriberSdkDirectServiceBusReadTaskCreated 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(resourceGroup().id, taskCreatedSubscriberSdkDirect.id, subscriberSdkDirectIdentity.id, roleServiceBusDataReceiver.id)
  scope: taskCreatedSubscriberSdkDirect
  properties: {
    description: 'Assign Service Bus Reader to subscriber-sdk-direct for task-created/subscriber-sdk-direct'
    principalId: subscriberSdkDirectIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleServiceBusDataReceiver.id
  }
}

output acr_name string = containerRegistry.name
output acr_login_server string = containerRegistry.properties.loginServer

output aks_name string = aks.name

output service_bus_namespace_name string = serviceBusNamespace.name
output service_bus_namespace_qualified_name string = replace(replace(serviceBusNamespace.properties.serviceBusEndpoint, 'https://', ''), ':443/', '')

output subscriber_sdk_simplified_client_id string = subscriberSdkSimplifiedIdentity.properties.clientId
output subscriber_sdk_simplified_principal_id string = subscriberSdkSimplifiedIdentity.properties.principalId

output subscriber_sdk_direct_client_id string = subscriberSdkDirectIdentity.properties.clientId
output subscriber_sdk_direct_principal_id string = subscriberSdkDirectIdentity.properties.principalId
