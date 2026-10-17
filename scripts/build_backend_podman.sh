#!/bin/bash
echo "Building backend image for Podman..."

cd "$(dirname "$0")/.."

podman build -f docker/Dockerfile.api -t localhost/log-intelligence-api:latest .

echo "✅ Backend image built successfully"
