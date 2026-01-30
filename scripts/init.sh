#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Etymology Explorer: Project Init ==="
echo ""

# Check prerequisites
check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        echo "ERROR: $1 is required but not installed."
        exit 1
    fi
}

echo "Checking prerequisites..."
check_cmd docker
check_cmd git

# Verify Docker is running
if ! docker info &>/dev/null; then
    echo "ERROR: Docker is not running. Start Docker Desktop and try again."
    exit 1
fi

echo "  docker: OK"
echo "  git: OK"
echo ""

# Create directory structure
echo "Creating directory structure..."
mkdir -p data/raw
mkdir -p backend/app/routers
mkdir -p backend/etl
mkdir -p frontend/public/{js,css}
mkdir -p scripts
echo "  Done."
echo ""

# Set up .gitignore
if [ ! -f .gitignore ]; then
    echo "Creating .gitignore..."
    cat > .gitignore <<'EOF'
data/
.env
__pycache__/
*.pyc
.DS_Store
node_modules/
EOF
    echo "  Done."
else
    echo ".gitignore already exists, skipping."
fi
echo ""

# Set up .env
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
    else
        cat > .env <<'EOF'
MONGO_URI=mongodb://mongodb:27017/etymology
EOF
        cp .env .env.example
    fi
    echo "  Done."
else
    echo ".env already exists, skipping."
fi
echo ""

# Build Docker images
echo "Building Docker images..."
docker compose build
echo "  Done."
echo ""

echo "=== Init complete ==="
echo ""
echo "Next steps:"
echo "  docker compose up -d    # Start services"
echo "  open http://localhost:8080  # View the app"
echo ""
