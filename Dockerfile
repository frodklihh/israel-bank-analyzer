# Single-stage build for leumi-analyzer
FROM python:3.11-slim

# Install system dependencies for Chrome/Puppeteer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    fonts-liberation \
    libasound2t64 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxshmfence1 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (needed for scraper bridge)
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Node dependencies and Chrome (same OS, no cross-stage issues)
COPY scraper/package*.json ./scraper/
RUN cd scraper && npm ci --omit=dev && \
    npx puppeteer@22.12.1 browsers install chrome@126

# Copy Python project
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set up timezone and Python path
ENV TZ=Asia/Jerusalem
ENV PYTHONPATH=/app

# Default to showing help
ENTRYPOINT ["python", "scripts/fetch.py"]
CMD ["--help"]
