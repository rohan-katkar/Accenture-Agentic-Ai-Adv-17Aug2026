// Northwind reconciliation platform — Lab 1.4 blueprint
// Deploy: az deployment group create -g <rg> -f main.bicep
param location string = resourceGroup().location
param baseName string = 'nwrecon'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: '${baseName}sa${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false }
}

resource queueSvc 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource reviewQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueSvc
  name: 'human-review'
}

resource ingestQueue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' = {
  parent: queueSvc
  name: 'raw-settlements'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${baseName}-agents-mi'
  location: location
}

resource aca 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${baseName}-agents'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    configuration: { activeRevisionsMode: 'Single' }
    template: {
      containers: [ { name: 'agents', image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest',
                      resources: { cpu: json('0.5'), memory: '1Gi' } } ]
    }
  }
}

output reviewQueueName string = reviewQueue.name
output managedIdentityId string = identity.id
