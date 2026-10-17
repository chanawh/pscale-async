#!/bin/bash
echo "Starting Log Intelligence system with Podman..."

cd "$(dirname "$0")/.."

# Check if images exist
if ! podman image exists localhost/log-intelligence-api:latest; then
    echo "Building backend image..."
    ./scripts/build_backend_podman.sh
fi

if ! podman image exists localhost/log-intelligence-worker:latest; then
    echo "Building worker image..."
    ./scripts/build_worker_podman.sh
fi

if ! podman image exists localhost/log-intelligence-frontend:latest; then
    echo "Building frontend image..."
    ./scripts/build_frontend_podman.sh
fi

# Start services
echo "Starting services with Podman Compose..."
podman-compose -f podman-compose.yml up -d

echo "✅ Services started!"
echo
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo
echo "To view logs: podman-compose -f podman-compose.yml logs -f"
echo "To stop: podman-compose -f podman-compose.yml down"
