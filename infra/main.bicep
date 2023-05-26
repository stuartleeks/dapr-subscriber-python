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

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2022-02-01-preview' = {
  name: '${envResourceNamePrefix}registry'
  location: location
  sku: {
    name: 'Standard'
  }
}

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
  }
}

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2021-11-01' = {
  name: '${envResourceNamePrefix}sb'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {}
}

// task-notifications topic + subscriptions

resource taskNotificationsTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' = {
  parent: serviceBusNamespace
  name: 'task-notifications'
  properties: {}
}

resource taskNotificationSubscriber1 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskNotificationsTopic
  name: 'task-notification-subscriber-1'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}
resource taskNotificationSubscriber2 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskNotificationsTopic
  name: 'task-notification-subscriber-2'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}

resource taskNotificationSubscriberSdkDirect 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskNotificationsTopic
  name: 'subscriber-sdk-direct'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}
resource taskNotificationSubscriberSdkSimplified 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: taskNotificationsTopic
  name: 'subscriber-sdk-simplified'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}

// user-notifications topic + subscriptions

resource userNotificationsTopic 'Microsoft.ServiceBus/namespaces/topics@2021-11-01' = {
  parent: serviceBusNamespace
  name: 'user-notifications'
  properties: {}
}
resource userNotificationSubscriberSdkSimplified 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2021-11-01' = {
  parent: userNotificationsTopic
  name: 'subscriber-sdk-simplified'
  properties: {
    lockDuration: 'PT5M'
    maxDeliveryCount: 10
  }
}


output acr_name string = containerRegistry.name
output acr_login_server string = containerRegistry.properties.loginServer
output aks_name string = aks.name
output service_bus_namespace_name string = serviceBusNamespace.name
