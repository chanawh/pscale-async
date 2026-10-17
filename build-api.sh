# Build script for log-intelligence-api
# Optimized for Windows + Podman

echo "Building log-intelligence-api with Podman..."

# Clean up any existing containers/images
podman rmi -f localhost/log-intelligence-api:latest 2>/dev/null || true
podman rmi -f localhost/log-intelligence-worker:latest 2>/dev/null || true

# Create a temporary build directory with only necessary files
echo "Preparing build context..."
TEMP_BUILD_DIR=$(mktemp -d)
mkdir -p "$TEMP_BUILD_DIR/src"
mkdir -p "$TEMP_BUILD_DIR/docker"

# Copy only necessary files
cp requirements.txt "$TEMP_BUILD_DIR/"
cp pyproject.toml "$TEMP_BUILD_DIR/"
cp README.md "$TEMP_BUILD_DIR/"
cp LICENSE "$TEMP_BUILD_DIR/" 2>/dev/null || true
cp -r src/* "$TEMP_BUILD_DIR/src/"
cp docker/Dockerfile.api "$TEMP_BUILD_DIR/Dockerfile"

# Build from the temporary directory
echo "Building from optimized context..."
cd "$TEMP_BUILD_DIR"
podman build -t localhost/log-intelligence-api:latest -f Dockerfile .

# Cleanup
cd ..
rm -rf "$TEMP_BUILD_DIR"

echo "Build completed!"
podman images | grep log-intelligence
