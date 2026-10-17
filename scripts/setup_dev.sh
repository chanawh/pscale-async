#!/bin/bash

# Development setup script for Async Log Intelligence API

echo "Setting up development environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
pip install -e .[dev]

# Copy environment file
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "Please edit .env with your configuration"
fi

# Start services
echo "Starting PostgreSQL and Redis..."
docker-compose up postgres redis -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Create default patterns
echo "Creating default patterns..."
python -c "
from src.db.database import SessionLocal
from src.workers.log_processor import create_default_patterns
db = SessionLocal()
create_default_patterns(db)
db.close()
print('Default patterns created')
"

echo "Development environment setup complete!"
echo ""
echo "To start the API server:"
echo "  source venv/bin/activate"
echo "  uvicorn src.app.main:app --reload"
echo ""
echo "To start the Celery worker (in another terminal):"
echo "  source venv/bin/activate"
echo "  celery -A src.core.celery worker --loglevel=info"
echo ""
echo "API will be available at: http://localhost:8000"
echo "Swagger docs at: http://localhost:8000/docs"
