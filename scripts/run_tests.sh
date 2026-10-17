#!/bin/bash

# Test runner script for Async Log Intelligence API

echo "Running tests..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start test dependencies
echo "Starting test dependencies..."
docker-compose up postgres redis -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Run database migrations for test database
echo "Setting up test database..."
if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL environment variable must be set" >&2
  exit 1
fi
createdb -h localhost -U postgres test_log_intelligence 2>/dev/null || true
alembic upgrade head

# Create default patterns
python -c "
from src.db.database import SessionLocal
from src.workers.log_processor import create_default_patterns
db = SessionLocal()
create_default_patterns(db)
db.close()
"

# Run tests
echo "Running test suite..."
pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html

# Cleanup
echo "Cleaning up test database..."
dropdb -h localhost -U postgres test_log_intelligence 2>/dev/null || true

echo "Tests complete!"
echo "Coverage report generated in htmlcov/"
