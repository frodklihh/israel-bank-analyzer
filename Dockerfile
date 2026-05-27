# Multi-stage build for leumi-analyzer
# Stage 1: Node.js for israeli-bank-scrapers bridge
FROM node:24-alpine AS scraper-build

WORKDIR /app/scraper
COPY scraper/package*.json ./
RUN npm ci --only=production && \
    npx puppeteer@latest browsers install chrome@126

# Stage 2: Python + everything
FROM python:3.11-slim

# Install system dependencies for Puppeteer/Chrome and other tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js in Python container (needed for scraper bridge)
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python project
COPY . .

# Copy Node modules from stage 1
COPY --from=scraper-build /app/scraper/node_modules ./scraper/node_modules
COPY --from=scraper-build /root/.cache/puppeteer /root/.cache/puppeteer

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set up timezone (Israel)
ENV TZ=Asia/Jerusalem

# Default to showing help
ENTRYPOINT ["python", "scripts/fetch.py"]
CMD ["--help"]
