@minLength(1)
@maxLength(64)
@description('Environment name used for resource naming')
param environmentName string

@minLength(1)
@description('Azure region for all resources')
param location string

// Model configuration
@description('Chat completion model name')
param chatModel string = 'gpt-4o-mini'

@description('Chat model version')
param chatModelVersion string = '2024-07-18'

@description('Embedding model name')
param embeddingModel string = 'text-embedding-3-small'

@description('Chat model capacity (tokens per minute in thousands)')
param chatModelCapacity int = 100

@description('Embedding model capacity (tokens per minute in thousands)')
param embeddingModelCapacity int = 80

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  environment: environmentName
}

module foundry './modules/foundry.bicep' = {
  params: {
    location: location
    tags: tags
    accountName: '${abbrs.ai.aiServices}${resourceToken}'
    projectName: '${abbrs.ai.aiFoundryProject}${resourceToken}'
    searchName: '${abbrs.ai.aiSearch}${resourceToken}'
    storageName: '${abbrs.storage.storageAccount}${resourceToken}'
    logAnalyticsName: '${abbrs.managementGovernance.logAnalyticsWorkspace}${resourceToken}'
    appInsightsName: '${abbrs.managementGovernance.applicationInsights}${resourceToken}'
    chatModel: chatModel
    chatModelVersion: chatModelVersion
    chatModelCapacity: chatModelCapacity
    embeddingModel: embeddingModel
    embeddingModelCapacity: embeddingModelCapacity
    deployingUserPrincipalId: az.deployer().objectId
  }
}

// Outputs for azd
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_SUBSCRIPTION_ID string = subscription().subscriptionId
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_AI_SERVICES_NAME string = foundry.outputs.accountName
output AZURE_AI_PROJECT_NAME string = foundry.outputs.projectName
output AZURE_AI_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output AZURE_AI_ENDPOINT string = foundry.outputs.aiEndpoint
output AZURE_OPENAI_ENDPOINT string = foundry.outputs.openAIEndpoint
output AZURE_AI_SEARCH_NAME string = foundry.outputs.searchName
output AZURE_AI_SEARCH_ENDPOINT string = foundry.outputs.searchEndpoint
output AZURE_STORAGE_ACCOUNT_NAME string = foundry.outputs.storageName
output AZURE_STORAGE_BLOB_ENDPOINT string = foundry.outputs.storageBlobEndpoint
output AZURE_APPINSIGHTS_NAME string = foundry.outputs.appInsightsName
output AZURE_APPINSIGHTS_CONNECTION_STRING string = foundry.outputs.appInsightsConnectionString
output AZURE_CHAT_MODEL string = chatModel
output AZURE_EMBEDDING_MODEL string = embeddingModel
