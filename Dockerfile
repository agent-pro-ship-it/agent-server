FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    procps \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Install ttyd web terminal for remote shell access
RUN curl -fsSL https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 -o /usr/local/bin/ttyd && \
    chmod +x /usr/local/bin/ttyd

# Install GitHub CLI (gh) for autonomous Codespaces orchestration
RUN curl -fsSL https://github.com/cli/cli/releases/download/v2.58.0/gh_2.58.0_linux_amd64.tar.gz | tar -xz -C /tmp && \
    mv /tmp/gh_2.58.0_linux_amd64/bin/gh /usr/local/bin/gh && \
    chmod +x /usr/local/bin/gh && \
    rm -rf /tmp/gh_2.58.0_linux_amd64

# Install Google Antigravity language_server core engine and agy / agentapi CLIs
RUN curl -fsSL https://storage.googleapis.com/antigravity-public/insiders/1.0.20261005110209/unsigned/language_server-linux-x64 -o /usr/local/bin/language_server && \
    chmod +x /usr/local/bin/language_server && \
    ln -sf /usr/local/bin/language_server /usr/local/bin/agy && \
    printf '#!/bin/sh\nexec /usr/local/bin/language_server agentapi "$@"\n' > /usr/local/bin/agentapi && \
    chmod +x /usr/local/bin/agentapi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install headless chromium and its exact dependencies via playwright
RUN playwright install --with-deps --only-shell chromium

COPY . .

EXPOSE 10000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
