FROM --platform=linux/amd64 python:3.10-slim as builder

WORKDIR /app

ENV POETRY_VERSION=1.7.1

# Install libraries for necessary python package builds
RUN apt-get update && apt-get --no-install-recommends install build-essential python3-dev libpq-dev -y && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --upgrade poetry==${POETRY_VERSION}

# Install ssh
RUN  apt-get -yq update && apt-get -yqq install ssh

# Configure Poetry
ENV POETRY_CACHE_DIR=/tmp/poetry_cache
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_VIRTUALENVS_CREATE=true

# Install dependencies
COPY message-queue/poetry.lock message-queue/pyproject.toml ./
RUN mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts
RUN --mount=type=secret,id=id_ed25519,dst=/root/.ssh/id_ed25519 poetry install --no-cache --no-root -vvv

# RUN poetry install --no-cache --no-root

FROM --platform=linux/amd64 python:3.10-slim as runtime

# Install wget for healthcheck
RUN apt-get update && apt-get install -y wget

RUN apt-get update -y && \
    apt-get install --no-install-recommends libpq5 -y && \
    rm -rf /var/lib/apt/lists/*  # Install libpq for psycopg2

RUN groupadd -r appuser && useradd --no-create-home -g appuser -r appuser
USER appuser


WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

# Copy source code
COPY ./logging.ini ./logging.ini
COPY ./message-queue/message_queue ./message_queue
