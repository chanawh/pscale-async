# Contributing to Async Log Intelligence API

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## 🤝 Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to:

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Accept differing viewpoints and experiences

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Docker & Docker Compose
- Git

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/async-log-intelligence-api.git
   cd async-log-intelligence-api
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Setup environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

6. **Start the database services**
   ```bash
   docker-compose up -d postgres redis
   ```

7. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

8. **Start the development server**
   ```bash
   uvicorn src.app.main:app --reload
   ```

9. **Start the frontend (in another terminal)**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## 🛠️ How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/YOUR_USERNAME/async-log-intelligence-api/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Relevant logs or screenshots

### Suggesting Enhancements

1. Check existing issues and discussions
2. Create a new issue with:
   - Clear use case
   - Proposed solution
   - Alternative solutions considered
   - Additional context

### Contributing Code

#### Branch Naming

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

#### Commit Messages

Follow conventional commits format:

```
type(scope): subject

body (optional)

footer (optional)
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/dependency changes

Examples:
```
feat(patterns): add OneFS license expiration pattern

fix(api): handle large file uploads over 2GB

docs(readme): add deployment instructions
```

## 📝 Coding Standards

### Python

- **Formatter**: [black](https://black.readthedocs.io/) (line length 88)
- **Import Sorting**: [isort](https://pycqa.github.io/isort/)
- **Linter**: [flake8](https://flake8.pycqa.org/)
- **Type Checking**: [mypy](http://mypy-lang.org/)

Configuration in `pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
```

#### Python Style Guidelines

1. **Type Hints**: Use type hints for function signatures
   ```python
   def process_log(job_id: str, file_path: str) -> dict[str, Any]:
       ...
   ```

2. **Docstrings**: Use Google-style docstrings
   ```python
   def create_incident(title: str, severity: Severity) -> Incident:
       """Create a new incident.
       
       Args:
           title: Incident title
           severity: Severity level
           
       Returns:
           Created incident object
       """
   ```

3. **Imports**: Group imports (stdlib, third-party, local)
   ```python
   # Standard library
   import os
   from datetime import datetime
   
   # Third party
   from fastapi import APIRouter
   from sqlalchemy.orm import Session
   
   # Local
   from src.models import Incident
   from src.db.database import get_db
   ```

### TypeScript/React

- **Formatter**: Prettier (configured in project)
- **Linter**: ESLint
- **Type Checking**: TypeScript strict mode

#### Frontend Guidelines

1. **Component Structure**:
   ```typescript
   // Named exports for components
   export function ComponentName() { }
   
   // Type interfaces in same file
   interface Props { }
   ```

2. **Hooks**: Use custom hooks for reusable logic
   ```typescript
   // hooks/useAuth.ts
   export function useAuth() {
     // Authentication logic
   }
   ```

3. **API Calls**: Use React Query for server state
   ```typescript
   const { data, isLoading } = useQuery({
     queryKey: ['incidents'],
     queryFn: fetchIncidents,
   })
   ```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_patterns.py -v

# Run integration tests
pytest tests/integration/ -v
```

### Writing Tests

#### Unit Tests

```python
# tests/unit/test_example.py
import pytest
from src.models import Incident, Severity

class TestIncidentModel:
    def test_incident_creation(self, test_db_session):
        """Test creating an incident."""
        incident = Incident(
            title="Test Incident",
            severity=Severity.CRITICAL,
            status=Status.OPEN,
            raw_log="Test log line"
        )
        test_db_session.add(incident)
        test_db_session.commit()
        
        assert incident.id is not None
        assert incident.severity == Severity.CRITICAL
```

#### API Tests

```python
# tests/test_api.py
def test_get_incidents(client):
    """Test getting incidents endpoint."""
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
```

### Test Coverage

Aim for:
- **80%+** overall coverage
- **100%** for critical paths (pattern matching, auth)
- All new features must include tests

## 📤 Pull Request Process

1. **Create a branch** from `main`
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make your changes** following coding standards

3. **Run tests and linting**
   ```bash
   pytest
   pre-commit run --all-files
   ```

4. **Update documentation** if needed

5. **Commit and push**
   ```bash
   git commit -m "feat: add new feature"
   git push origin feature/my-feature
   ```

6. **Create Pull Request** with:
   - Clear title and description
   - Link to related issue
   - Screenshots (for UI changes)
   - Test results

7. **Code Review**
   - Address reviewer feedback
   - Keep discussions constructive
   - Mark conversations as resolved

8. **Merge**
   - Squash and merge after approval
   - Delete feature branch after merge

## 🏷️ Release Process

1. Update `CHANGELOG.md` with new version
2. Bump version in `pyproject.toml`
3. Create Git tag: `git tag -a v0.2.0 -m "Version 0.2.0"`
4. Push tag: `git push origin v0.2.0`
5. GitHub Actions will build and release

## ❓ Questions?

- Open a [Discussion](https://github.com/YOUR_USERNAME/async-log-intelligence-api/discussions)
- Join our community chat (if available)
- Email: your-email@example.com

## 🙏 Thank You!

Every contribution helps make this project better. We appreciate your time and effort!

---

**Happy Contributing! 🚀**
