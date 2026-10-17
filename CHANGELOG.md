# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-27

### Added
- Initial release of Async Log Intelligence API
- FastAPI-based REST API for log processing
- PostgreSQL database with SQLAlchemy ORM
- Redis and Celery for async job processing
- OneFS-specific pattern matching (23+ patterns)
- SSH tunnel support for OneFS cluster connectivity
- JWT-based authentication
- React frontend with TypeScript
- Docker and Docker Compose setup
- Alembic database migrations
- Comprehensive test suite with pytest
- GitHub Actions CI/CD pipeline
- API documentation with OpenAPI/Swagger
- Real-time job progress tracking via Server-Sent Events
- Database admin interface for SQL queries
- Incident management with severity levels and status tracking
- Node management for cluster nodes
- Pattern management with regex testing

### Features
- Log file upload and streaming endpoints
- Pattern-based incident detection
- Job queue management with progress tracking
- Cluster status monitoring
- Summary analytics and escalation tracking
- OneFS /var/log/messages format detection
- Automatic hostname extraction from logs
- Node type classification (onefs, linux, vmware)
- Multi-container Docker orchestration
- Health check endpoints
- CORS middleware for frontend integration

### Security
- JWT token-based authentication
- Password hashing with bcrypt
- Database connection pooling
- SQL injection protection via SQLAlchemy
- Read-only SQL query enforcement in admin interface

### Infrastructure
- Docker multi-stage builds
- PostgreSQL 15 with health checks
- Redis 7 for message queuing
- Nginx configuration for production
- GitHub Actions workflow for CI/CD
- Trivy security scanning
