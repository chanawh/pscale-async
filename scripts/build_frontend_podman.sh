#!/bin/bash
echo "Building frontend image for Podman..."

cd "$(dirname "$0")/.."

cat > frontend/Dockerfile << 'DOCKERFILE'
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
DOCKERFILE

podman build -f frontend/Dockerfile -t localhost/log-intelligence-frontend:latest ./frontend

echo "✅ Frontend image built successfully"
