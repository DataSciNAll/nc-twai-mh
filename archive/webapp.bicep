@description('Azure region for resources')
param location string = 'swedencentral'

@description('Resource tags')
param tags object = {}

@description('Web App name')
param webAppName string

@description('App Service Plan name')
param appServicePlanName string

@description('Azure OpenAI endpoint')
param azureOpenAIEndpoint string

@description('AI Services account name for role assignment')
param aiServicesName string

@description('Chat model deployment name')
param chatModel string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string

// Reference to AI Services for role assignment
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

// App Service Plan (Linux)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
    capacity: 1
  }
  properties: {
    reserved: true // Required for Linux
  }
}

// Web App with System Assigned Managed Identity
resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: webAppName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appCommandLine: 'startup.sh'
      appSettings: [
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: azureOpenAIEndpoint
        }
        {
          name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
          value: chatModel
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
      ]
    }
  }
}

// Diagnostic settings for the Web App
resource webAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${webAppName}-diagnostics'
  scope: webApp
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServiceAppLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Role Definition for Cognitive Services OpenAI User
resource cognitiveServicesOpenAIUser 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
}

// Grant Web App managed identity access to Azure OpenAI
resource webAppOpenAIAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: aiServices
  name: guid(aiServices.id, webApp.id, cognitiveServicesOpenAIUser.id)
  properties: {
    principalId: webApp.identity.principalId
    roleDefinitionId: cognitiveServicesOpenAIUser.id
    principalType: 'ServicePrincipal'
  }
}

output webAppName string = webApp.name
output webAppHostName string = webApp.properties.defaultHostName
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output webAppPrincipalId string = webApp.identity.principalId
