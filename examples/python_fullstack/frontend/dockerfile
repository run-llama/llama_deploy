# This Dockerfile is used to deploy a simple single-container Reflex app instance.
FROM python:3.10-slim

# Copy local context to `/app` inside container (see .dockerignore)
WORKDIR /app
COPY . .

# Install app requirements and reflex in the container
# Deploy templates and prepare app
# Download all npm dependencies and compile frontend
RUN apt-get clean && apt-get update \
    && apt-get --no-install-recommends install zip unzip curl -y \
    && pip install -r requirements.txt \
    && reflex export --frontend-only --no-zip

# Needed until Reflex properly passes SIGTERM on backend.
STOPSIGNAL SIGKILL

# Always apply migrations before starting the backend.
CMD [ -d alembic ] && reflex db migrate; reflex run --env prod
