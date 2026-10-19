FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Node.js (needed to compile Tailwind CSS)
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install Tailwind dependencies first to take advantage of the layer cache
COPY theme/static_src/package.json theme/static_src/package-lock.json theme/static_src/
RUN cd theme/static_src && npm ci

COPY . .

# Build the production Tailwind CSS into theme/static/css/dist
RUN cd theme/static_src && npm run build

RUN chmod +x start.sh start-dev.sh

EXPOSE 8000

CMD ["./start.sh"]
