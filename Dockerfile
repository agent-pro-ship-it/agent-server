FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000

WORKDIR /app

# Install system dependencies (git, curl, tar, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    tar \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install official Google Antigravity CLI (agy)
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash -s -- --dir /usr/local/bin && \
    chmod +x /usr/local/bin/agy

# Install ttyd web terminal for remote Antigravity access
RUN curl -fsSL https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 -o /usr/local/bin/ttyd && \
    chmod +x /usr/local/bin/ttyd

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
