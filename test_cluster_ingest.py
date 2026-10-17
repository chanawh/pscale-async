import os
import sys
import time

# Trust/safety baseline: the API fails fast without a bootstrap admin identity.
# Test-only credentials for local scripts (never used in production).
os.environ.setdefault("ADMIN_USERNAME", "test-admin")
os.environ.setdefault(
    "ADMIN_PASSWORD_HASH",
    "$2b$12$X.m9BbKu7XC9SABo6YiDqOF4lxzqLFkja5AqjBnmL9RuWIc7Ocf8a",  # bcrypt("admin123"), test-only
)

# Set environment
if not os.environ.get('DATABASE_URL'):
    raise RuntimeError('DATABASE_URL environment variable must be set to run this script')
os.environ['ONEFS_MOCK_MODE'] = 'false'
os.environ['CELERY_BROKER_URL'] = 'memory://'
os.environ['CELERY_RESULT_BACKEND'] = 'memory://'

# Recreate database
if os.path.exists('log_intelligence.db'):
    os.remove('log_intelligence.db')
    print("Removed old database")

from src.db.database import create_tables, SessionLocal
create_tables()
print("Database recreated")

from fastapi.testclient import TestClient
from src.app.main import app
from src.models import Job

client = TestClient(app)

# Test cluster ingestion
print("\nTesting cluster log ingestion...")
response = client.post('/api/v1/ingest/cluster', json={
    'log_path': '/var/log/messages',
    'node_hostname': 'Test-9700-1'
})
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Wait for background processing
print("\nWaiting 15 seconds for background processing...")
time.sleep(15)

# Check jobs
db = SessionLocal()
jobs = db.query(Job).all()
print(f"\nFound {len(jobs)} jobs in database:")
for job in jobs:
    print(f"  - {job.id}: {job.status.value if hasattr(job.status, 'value') else job.status}")
    print(f"    File: {job.filename}")
    if job.error_message:
        print(f"    Error: {job.error_message[:100]}")
db.close()
