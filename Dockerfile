FROM mcr.microsoft.com/playwright/python:v1.45.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    tar \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install ttyd web terminal for remote shell access
RUN curl -fsSL https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 -o /usr/local/bin/ttyd && \
    chmod +x /usr/local/bin/ttyd

# Optional Antigravity CLI installation
RUN (curl -fsSL https://antigravity.google/cli/install.sh | bash -s -- --dir /usr/local/bin) || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure Chromium headless shell is ready
RUN playwright install chromium

COPY . .

EXPOSE 10000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
