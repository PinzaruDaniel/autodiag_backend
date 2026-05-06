// ============================================================
// AutoDiag – Azure Container Apps Hosting
// Depends on: main.bicep (storage account must exist first)
// ============================================================

@description('Base name used to derive resource names.')
param baseName string = 'autodiag'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Name of the container image to deploy, e.g. myregistry.azurecr.io/autodiag-backend:latest')
param containerImage string

@description('Azure Storage connection string (from main.bicep deployment).')
@secure()
param azureStorageConnectionString string

@description('JWT secret used to sign access tokens.')
@secure()
param jwtSecret string

@description('Optional AI inference endpoint URL.')
param aiInferenceEndpoint string = ''

@description('Optional bearer token for the AI inference endpoint.')
@secure()
param aiInferenceToken string = ''

@description('Name of the Blob container for audio files.')
param audioContainerName string = 'audio'

// ── Log Analytics workspace (required by Container Apps) ─────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${baseName}-logs'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ── Container Apps managed environment ───────────────────────
resource containerEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${baseName}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ── Container App ─────────────────────────────────────────────
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: '${baseName}-backend'
  location: location
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      secrets: [
        { name: 'jwt-secret', value: jwtSecret }
        { name: 'storage-conn-string', value: azureStorageConnectionString }
        { name: 'ai-inference-token', value: aiInferenceToken }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
            { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-conn-string' }
            { name: 'AZURE_STORAGE_CONTAINER', value: audioContainerName }
            { name: 'AI_INFERENCE_ENDPOINT', value: aiInferenceEndpoint }
            { name: 'AI_INFERENCE_TOKEN', secretRef: 'ai-inference-token' }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// ── Outputs ───────────────────────────────────────────────────
@description('Public URL of the deployed Container App.')
output backendUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
