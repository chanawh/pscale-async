#!/bin/bash
echo "Building worker image for Podman..."

cd "$(dirname "$0")/.."

podman build -f docker/Dockerfile.worker -t localhost/log-intelligence-worker:latest .

echo "✅ Worker image built successfully"
