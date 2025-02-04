FROM llamaindex/llama-deploy:main

# This will be passed at build time
ARG SOURCE_DIR=""

# Copy the application code (for example, your workflow)
COPY ${SOURCE_DIR} /app/code
WORKDIR  /app/code

# Deploy automatically what's in /app/code when the container starts
ENV LLAMA_DEPLOY_APISERVER_RC_PATH=/app/code
COPY deployment.yml /app/code

# Cloud Run requires the container to listen to port 8080
ENV LLAMA_DEPLOY_APISERVER_HOST=0.0.0.0
ENV LLAMA_DEPLOY_APISERVER_PORT=8080
EXPOSE 8080

# In Cloud Run localhost resolves to the public URI on port 80,
# let's override the default and point explicitly to the internal
# host and port
ENV LLAMA_DEPLOY_API_SERVER_URL="http://127.0.0.1:8080"
