#!/usr/bin/env bash
# ==============================================================
# AutoDiag – Azure provisioning script
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh [resource-group] [location]
#
# Prerequisites:
#   - Azure CLI installed and logged in  (az login)
#   - Docker installed (for container build + push)
# ==============================================================

set -euo pipefail

RESOURCE_GROUP="${1:-autodiag-rg}"
LOCATION="${2:-eastus}"
BASE_NAME="autodiag"
STORAGE_ACCOUNT="${BASE_NAME}store"

echo "==> 1/6  Creating resource group '$RESOURCE_GROUP' in '$LOCATION'…"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> 2/6  Deploying storage infrastructure (infra/main.bicep)…"
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$(dirname "$0")/infra/main.bicep" \
  --parameters baseName="$BASE_NAME" \
  --output none

echo "==> 3/6  Retrieving Storage Account connection string…"
CONN_STRING=$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --query connectionString \
  --output tsv)

echo ""
echo "✅  Infrastructure is ready."
echo ""
echo "─────────────────────────────────────────────────────────────"
echo "Set the following environment variables before running the app"
echo "─────────────────────────────────────────────────────────────"
echo ""
echo "  export AZURE_STORAGE_CONNECTION_STRING=\"$CONN_STRING\""
echo "  export JWT_SECRET=\"\$(openssl rand -hex 32)\""
echo ""
echo "Optional (AI inference):"
echo "  export AI_INFERENCE_ENDPOINT=\"<your-endpoint-url>\""
echo "  export AI_INFERENCE_TOKEN=\"<your-token>\""
echo ""
echo "─────────────────────────────────────────────────────────────"
echo ""

# ── Optional: build & push Docker image, deploy to Container Apps ─
echo "==> 4/6  (Optional) Build and push Docker image"
echo "  Skip this step if you are running the app locally."
read -r -p "  Build and deploy to Azure Container Apps? [y/N] " DEPLOY_ACA
if [[ "${DEPLOY_ACA,,}" != "y" ]]; then
  echo "  Skipping Container Apps deployment."
  echo ""
  echo "To run locally:"
  echo "  cp .env.example .env && \$EDITOR .env"
  echo "  uvicorn app.main:app --reload"
  exit 0
fi

read -r -p "  Container registry (e.g. myregistry.azurecr.io): " REGISTRY
IMAGE="${REGISTRY}/${BASE_NAME}-backend:latest"

echo "==> 5/6  Building and pushing image '$IMAGE'…"
docker build -t "$IMAGE" .
docker push "$IMAGE"

echo "==> 6/6  Deploying Container App (infra/containerapp.bicep)…"
JWT_SECRET=$(openssl rand -hex 32)
echo "  Generated JWT_SECRET: $JWT_SECRET"
echo "  (Save this value – it cannot be retrieved later.)"

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$(dirname "$0")/infra/containerapp.bicep" \
  --parameters \
      baseName="$BASE_NAME" \
      containerImage="$IMAGE" \
      azureStorageConnectionString="$CONN_STRING" \
      jwtSecret="$JWT_SECRET"

BACKEND_URL=$(az containerapp show \
  --name "${BASE_NAME}-backend" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.configuration.ingress.fqdn \
  --output tsv)

echo ""
echo "✅  Deployment complete."
echo "   Backend URL: https://$BACKEND_URL"
