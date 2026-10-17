import os
import sys

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
os.environ['CELERY_TASK_ALWAYS_EAGER'] = 'true'

from fastapi.testclient import TestClient
from src.app.main import app

client = TestClient(app)

# Test cluster ingestion
print("Testing cluster log ingestion...")
response = client.post('/api/v1/ingest/cluster', json={
    'log_path': '/var/log/messages',
    'node_hostname': 'Test-9700-1'
}, timeout=60)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Success! Job ID: {data.get('job_id')}")
    print(f"Status: {data.get('status')}")
    print(f"Message: {data.get('message')}")
    if 'result' in data:
        print(f"Incidents created: {data['result'].get('incidents_created', 0)}")
else:
    print(f"Error: {response.text}")
