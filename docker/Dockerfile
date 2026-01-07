FROM node:20.19.1-bookworm

RUN apt-get update && \
    apt-get install -y python3-dev && \
    apt-get install -y python3-venv && \
    apt-get install -y xauth && \
    apt-get install -y cron

ENV NODE_ENV=development

# Configure Poetry
# (adapted from https://stackoverflow.com/a/72465422)
ENV POETRY_VERSION=1.8.1
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/opt/.cache

# Install poetry separated from system interpreter
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install pip==23.0.1 setuptools \
    && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION}

# Add `poetry` to PATH
ENV PATH="${PATH}:${POETRY_VENV}/bin"

WORKDIR /app

# Install python dependencies
COPY poetry.lock pyproject.toml ./
RUN poetry install --no-root

# Install node dependencies
COPY package-lock.json package.json ./
RUN npm install

# Install Playwright's system-level dependencies
RUN npx playwright install-deps chromium

# Enable Celery testing in pytest
ENV PYTEST_PLUGINS=celery.contrib.pytest

# Set up cron
COPY docker/cleanup-crontab /etc/cron.d/cleanup-crontab
RUN chmod 0644 /etc/cron.d/cleanup-crontab && \
    crontab /etc/cron.d/cleanup-crontab
RUN touch /var/log/cron.log

COPY . /app
COPY ./docker/docker-entrypoint.sh /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/bin/bash"]
