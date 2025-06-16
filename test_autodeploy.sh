#!/bin/bash

set -ex  # Exit on error, print commands

# =============================================================================
# CONFIGURATION - EDIT THESE VALUES
# =============================================================================

# Required: GitHub repo URL to autodeploy
REPO_URL="https://github.com/adrianlyjak/workspace-test"

# Optional: GitHub Personal Access Token (leave empty for public repos)
if [ -z "$GITHUB_PAT" ]; then
    echo "GITHUB_PAT is not set"
    exit 1
fi

# Container settings
CONTAINER_NAME="llama-deploy-autodeploy-test"
IMAGE_NAME="llamaindex/llama-deploy:local-autodeploy"

# Ports
APISERVER_PORT="8080"
PROMETHEUS_PORT="8002"

# Deployment settings
WORK_DIR="/data"
DEPLOYMENT_FILE_PATH="deployment.yaml"
DEPLOYMENT_NAME=""  # Leave empty to use default from deployment file

# Other settings
PROMETHEUS_ENABLED="false"
BUILD_IMAGE="true"  # Set to "false" if image already exists
TIMEOUT="60"        # Seconds to wait for startup

# =============================================================================
# SCRIPT - DON'T EDIT BELOW UNLESS YOU KNOW WHAT YOU'RE DOING
# =============================================================================

echo "🚀 Starting autodeploy test..."
echo "Repository: $REPO_URL"
echo "Container: $CONTAINER_NAME"
echo "Image: $IMAGE_NAME"
echo "Port: $APISERVER_PORT"

# Cleanup any existing container
echo "🧹 Cleaning up existing container..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Build image if requested
if [[ "$BUILD_IMAGE" == "true" ]]; then
    echo "🔨 Building Docker image from repo root..."
    # Build from repo root since we're copying local sources
    docker buildx bake -f docker/docker-bake.hcl autodeploy
fi

# Check if image exists
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "❌ Docker image $IMAGE_NAME not found!"
    echo "Set BUILD_IMAGE=true at the top of this script or build it manually:"
    echo "cd docker && docker buildx bake autodeploy"
    exit 1
fi

# Prepare environment variables for the container
ENV_ARGS=()
ENV_ARGS+=(-e "REPO_URL=$REPO_URL")
ENV_ARGS+=(-e "WORK_DIR=$WORK_DIR")
ENV_ARGS+=(-e "DEPLOYMENT_FILE_PATH=$DEPLOYMENT_FILE_PATH")
ENV_ARGS+=(-e "LLAMA_DEPLOY_APISERVER_HOST=0.0.0.0")
ENV_ARGS+=(-e "LLAMA_DEPLOY_APISERVER_PORT=$APISERVER_PORT")
ENV_ARGS+=(-e "LLAMA_DEPLOY_APISERVER_PROMETHEUS_ENABLED=$PROMETHEUS_ENABLED")
ENV_ARGS+=(-e "LLAMA_DEPLOY_APISERVER_PROMETHEUS_PORT=$PROMETHEUS_PORT")

# Add optional environment variables
if [[ -n "$GITHUB_PAT" ]]; then
    ENV_ARGS+=(-e "GITHUB_PAT=$GITHUB_PAT")
    echo "🔑 Using GitHub PAT for authentication"
fi

if [[ -n "$DEPLOYMENT_NAME" ]]; then
    ENV_ARGS+=(-e "DEPLOYMENT_NAME=$DEPLOYMENT_NAME")
    echo "📝 Deployment name override: $DEPLOYMENT_NAME"
fi

# Start the container interactively
echo "🚢 Starting container interactively..."
echo "📍 Service will be available at: http://localhost:$APISERVER_PORT"
echo "🛑 Press Ctrl+C to stop"
echo ""

docker run -it --rm \
    --name "$CONTAINER_NAME" \
    -p "$APISERVER_PORT:$APISERVER_PORT" \
    -p "$PROMETHEUS_PORT:$PROMETHEUS_PORT" \
    "${ENV_ARGS[@]}" \
    "$IMAGE_NAME"
