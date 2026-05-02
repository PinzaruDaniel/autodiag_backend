// ============================================================
// AutoDiag – Core Infrastructure
// Provisions: Storage Account (Blob + Table), Blob container
// ============================================================

@description('Base name used to derive resource names.')
param baseName string = 'autodiag'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Name of the Blob container that stores audio files.')
param audioContainerName string = 'audio'

// Storage account names must be 3-24 lowercase alphanumeric characters.
var storageAccountName = toLower(replace('${baseName}store', '-', ''))

// ── Storage Account ──────────────────────────────────────────
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// ── Blob service + audio container ───────────────────────────
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource audioContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: audioContainerName
  properties: {
    publicAccess: 'None'
  }
}

// ── Outputs ───────────────────────────────────────────────────
@description('Name of the provisioned Storage Account.')
output storageAccountName string = storageAccount.name

@description('Name of the audio Blob container.')
output audioContainerName string = audioContainer.name
