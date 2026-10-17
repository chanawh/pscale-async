# Async Log Intelligence API

[![CI](https://github.com/chana13/async-log-intelligence-api/workflows/CI/badge.svg)](https://github.com/chana13/async-log-intelligence-api/actions)
[![Coverage](https://codecov.io/gh/chana13/async-log-intelligence-api/branch/main/graph/badge.svg)](https://codecov.io/gh/chana13/async-log-intelligence-api)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-00a393.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://react.dev)

> **Enterprise-grade log processing system for Dell EMC Isilon OneFS clusters with real-time incident detection, async job queues, and modern React dashboard**

[🚀 Demo](#quick-start) • [📖 Docs](#api-documentation) • [🏗️ Architecture](#architecture) • [💻 Installation](#installation)
- [🐳 Docker/Podman Setup](#dockerpodman-setup)
- [⚡ Fast Builds](#fast-builds)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [API Documentation](#api-documentation)
- [Frontend](#frontend)
- [Pattern Matching](#pattern-matching)
- [Testing](#testing)
- [Deployment](#deployment)
- [Performance](#performance)
- [Contributing](#contributing)

---

## 🎯 Overview

The **Async Log Intelligence API** is a production-ready REST API service designed specifically for **Dell EMC Isilon OneFS** log processing. It ingests log files from OneFS clusters, analyzes them using 23+ specialized regex patterns, and automatically creates incidents for critical issues like disk failures, cluster quorum problems, and authentication errors.

### What Makes It Special

- **🚀 Asynchronous Processing**: Celery workers handle large log files (2GB+) without blocking the API
- **🔍 OneFS-Specific Patterns**: 23 built-in patterns covering hardware, network, security, and cluster issues
- **🔐 Secure SSH Integration**: Direct connectivity to OneFS clusters via SSH tunnels
- **📊 Real-Time Dashboard**: React + TypeScript frontend with live job progress tracking
- **🐳 Production-Ready**: Docker Compose setup with nginx, PostgreSQL, and Redis

### Target Users

- Site Reliability Engineers (SREs) managing OneFS clusters
- Storage administrators monitoring Dell EMC Isilon systems
- DevOps teams building log analysis pipelines
- Security teams tracking authentication failures

---

## ✨ Key Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Log Ingestion** | Upload files via HTTP or stream log lines directly |
| **Pattern Matching** | 23+ OneFS-specific regex patterns for incident detection |
| **Incident Management** | CRUD operations with severity levels (LOW→CRITICAL) |
| **Job Tracking** | Real-time progress via Server-Sent Events (SSE) |
| **Node Management** | Track cluster nodes with automatic hostname extraction |
| **Database Admin** | Execute read-only SQL queries via API |
| **JWT Authentication** | Secure token-based auth with refresh tokens |

### Pattern Categories

- **🔴 Critical**: Disk failures, power supply failures, cluster quorum issues
- **🟠 High**: Storage pool degraded, NFS timeouts, Kerberos errors
- **🟡 Medium**: Network issues, LDAP timeouts, backup failures
- **🟢 Low**: General warnings, information logs

---

## 🏗️ Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                          │
│                    (React + TypeScript)                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Nginx (Reverse Proxy)                   │
│              Rate Limiting • SSL Termination • Caching          │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐    ┌──────────────────────────────┐
│   FastAPI REST API      │    │      React SPA (Vite)        │
│   • Log Ingestion       │    │      • Dashboard             │
│   • Job Management      │    │      • Incident Management   │
│   • Pattern CRUD        │    │      • Real-time Progress    │
│   • Database Admin      │    │      • Pattern Testing       │
└─────────────────────────┘    └──────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Message Queue (Redis)                        │
│              Celery Broker • Result Backend • Caching           │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Celery Workers                               │
│   • Process Log Files        • Pattern Matching                │
│   • Create Incidents          • Update Job Status              │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                         │
│   incidents • nodes • patterns • jobs • incident_activities   │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OneFS Cluster                               │
│   SSH Tunnel • /var/log/messages • Platform API               │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Log Ingestion**: User uploads file → API validates → Creates job → Queues to Celery
2. **Processing**: Celery worker reads file → Matches patterns → Creates incidents → Updates job progress
3. **Real-time Updates**: SSE endpoint streams job progress to frontend
4. **Incident Management**: Users view/filter incidents, update status, track activity

---

## 🛠️ Technology Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Framework** | FastAPI | 0.104+ | High-performance async API |
| **Database** | PostgreSQL | 15+ | Primary data store |
| **ORM** | SQLAlchemy | 2.0+ | Database modeling |
| **Migrations** | Alembic | 1.12+ | Schema versioning |
| **Task Queue** | Celery + Redis | 5.3+ | Async job processing |
| **Auth** | PyJWT + Passlib | 3.3+ | JWT token authentication |
| **SSH** | Paramiko | 3.3+ | OneFS cluster connectivity |
| **Testing** | pytest + testcontainers | 7.4+ | Unit/integration tests |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| **Framework** | React | 18.2+ | UI components |
| **Language** | TypeScript | 5.0+ | Type-safe development |
| **Build Tool** | Vite | 4.4+ | Fast dev server & bundling |
| **State** | React Query | 4.32+ | Server state management |
| **Routing** | React Router | 6.15+ | Client-side routing |
| **Styling** | Tailwind CSS | 3.3+ | Utility-first CSS |
| **Icons** | Lucide React | 0.279+ | Icon library |
| **Charts** | Recharts | 2.8+ | Data visualization |
| **Forms** | React Hook Form | 7.45+ | Form handling |
| **Notifications** | React Hot Toast | 2.4+ | Toast notifications |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Reverse Proxy** | Nginx | Load balancing, SSL, caching |
| **Containerization** | Docker + Compose | Multi-service orchestration |
| **CI/CD** | GitHub Actions | Automated testing & linting |
| **Code Quality** | black, isort, flake8, mypy | Formatting & type checking |
| **Security** | Trivy | Container vulnerability scanning |

---

## 📁 Project Structure

```
async-log-intelligence-api/
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI pipeline
├── .windsurf/
│   └── workflows/
│       └── jobs.md               # Windsurf workflow definitions
├── alembic/
│   ├── versions/                 # Database migration scripts
│   ├── env.py                   # Alembic environment config
│   └── script.py.mako           # Migration template
├── docker/
│   ├── Dockerfile.api           # API service container
│   └── Dockerfile.worker        # Celery worker container
├── docs/
│   └── onefs_integration.md     # OneFS integration guide
├── examples/
│   └── onefs_sample.txt       # Sample OneFS log file
├── frontend/
│   ├── src/
│   │   ├── components/          # 16 React components
│   │   │   ├── ActivityTimeline.tsx    # Incident activity display
│   │   │   ├── EmptyState.tsx          # Empty state placeholder
│   │   │   ├── ErrorBoundary.tsx       # Error catching
│   │   │   ├── EscalateModal.tsx       # Incident escalation UI
│   │   │   ├── FallbackDashboard.tsx   # Dashboard error fallback
│   │   │   ├── FileUpload.tsx          # Drag-and-drop file upload
│   │   │   ├── Layout.tsx              # App shell with navigation
│   │   │   ├── LoadingSpinner.tsx        # Loading indicator
│   │   │   ├── ProgressBar.tsx           # Job progress bar
│   │   │   ├── ProtectedRoute.tsx       # Auth route guard
│   │   │   ├── RawLog.tsx               # Log content display
│   │   │   ├── SearchInput.tsx          # Search with filters
│   │   │   ├── StatusBadge.tsx          # Status indicators
│   │   │   └── WorkDetailsModal.tsx     # Job details modal
│   │   ├── hooks/               # 2 custom React hooks
│   │   │   ├── useAuth.ts           # JWT authentication
│   │   │   └── useJobEvents.ts      # SSE job progress
│   │   ├── pages/               # 9 page components
│   │   │   ├── ClusterStatus.tsx    # OneFS cluster monitoring
│   │   │   ├── Dashboard.tsx        # Analytics dashboard
│   │   │   ├── DatabaseAdmin.tsx    # SQL query interface
│   │   │   ├── Incidents.tsx        # Incident management
│   │   │   ├── Jobs.tsx             # Job queue monitoring
│   │   │   ├── LogIngestion.tsx     # Log upload interface
│   │   │   ├── Login.tsx            # Authentication page
│   │   │   ├── Nodes.tsx            # Node management
│   │   │   └── Patterns.tsx         # Pattern CRUD + testing
│   │   ├── services/            # API service layer
│   │   ├── types/               # TypeScript type definitions
│   │   ├── App.tsx              # Main app component with routing
│   │   ├── main.tsx             # App entry point
│   │   └── index.css            # Tailwind + custom styles
│   ├── index.html               # HTML template
│   ├── nginx.conf               # Frontend nginx config
│   ├── package.json             # Node dependencies
│   ├── postcss.config.js        # PostCSS configuration
│   ├── tailwind.config.js       # Tailwind theme config
│   ├── tsconfig.json            # TypeScript compiler options
│   └── vite.config.ts           # Vite build configuration
├── nginx/
│   └── nginx.conf               # Production nginx configuration
├── scripts/
│   ├── run_tests.sh             # Test execution script
│   └── setup_dev.sh             # Development setup script
├── src/
│   ├── api/
│   │   ├── routers/             # 8 API router modules
│   │   │   ├── admin.py        # Database admin (SQL queries)
│   │   │   ├── auth.py         # JWT authentication endpoints
│   │   │   ├── cluster.py      # OneFS cluster status
│   │   │   ├── incidents.py    # Incident CRUD operations
│   │   │   ├── ingest.py       # Log ingestion endpoints
│   │   │   ├── jobs.py         # Job management + SSE
│   │   │   ├── nodes.py        # Node CRUD operations
│   │   │   └── patterns.py     # Pattern CRUD + regex testing
│   │   └── __init__.py
│   ├── app/
│   │   ├── main.py              # FastAPI app factory
│   │   └── __init__.py
│   ├── core/
│   │   ├── celery.py            # Celery app configuration
│   │   ├── config.py            # Pydantic settings
│   │   └── __init__.py
│   ├── db/
│   │   ├── database.py          # SQLAlchemy engine & session
│   │   └── __init__.py
│   ├── models/                  # 5 SQLAlchemy models
│   │   ├── __init__.py          # Model exports
│   │   ├── activity.py          # IncidentActivity model
│   │   ├── incident.py          # Incident model + enums
│   │   ├── job.py               # Job model + JobStatus enum
│   │   ├── node.py              # Node model
│   │   └── pattern.py           # Pattern model
│   ├── onefs/
│   │   └── client.py            # OneFS SSH/API client
│   └── workers/
│       ├── __init__.py
│       └── log_processor.py     # Celery task + 23 patterns
├── tests/
│   ├── integration/             # Integration tests
│   │   ├── __init__.py
│   │   ├── test_database.py     # Database connectivity
│   │   └── test_ingestion.py    # Log ingestion tests
│   ├── unit/                    # Unit tests
│   │   ├── __init__.py
│   │   ├── test_models.py       # Model unit tests
│   │   ├── test_patterns.py     # Pattern matching tests
│   │   └── test_workers.py      # Worker function tests
│   ├── __init__.py
│   ├── conftest.py              # pytest fixtures
│   ├── test_api.py              # API endpoint tests
│   └── test_onefs_integration.py # OneFS-specific tests
├── .env.example                 # Environment variable template
├── .gitignore                   # Git ignore patterns
├── .pre-commit-config.yaml      # Pre-commit hooks config
├── alembic.ini                  # Alembic configuration
├── CHANGELOG.md                 # Version history
├── docker-compose.full-stack.yml # Full production compose
├── docker-compose.yml           # Development compose
├── LICENSE                      # MIT License
├── pyproject.toml               # Python project metadata
├── README.md                    # This file
└── requirements.txt             # Python dependencies

```

**Total Files**: 50+ Python modules, 25+ React components, 20+ config files

---

## 🗄️ Database Schema

### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    jobs     │       │  incidents  │       │   nodes     │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ PK id       │◄──────│ FK job_id   │       │ PK id       │
│ filename    │       │ PK id       │       │ hostname    │
│ file_size   │       │ title       │       │ ip_address  │
│ status      │       │ severity    │       │ node_type   │
│ progress    │       │ status      │       │ version     │
│ created_at  │       │ raw_log     │       │ created_at  │
└─────────────┘       │ node_id ────┼──────►│             │
                      │ pattern_id ─┼┐      └─────────────┘
                      │ created_at  ││
                      └─────────────┘│
                             ▲       │
                             │       │
                      ┌──────┴───────┴─┐
                      │    patterns    │
                      ├────────────────┤
                      │ PK id          │
                      │ name           │
                      │ regex_pattern  │
                      │ category       │
                      │ severity_level │
                      │ is_active      │
                      │ created_at     │
                      └────────────────┘

┌─────────────────────────┐
│   incident_activities   │
├─────────────────────────┤
│ PK id                   │
│ FK incident_id          │
│ user_id                 │
│ action_type             │
│ description             │
│ details                 │
│ created_at              │
└─────────────────────────┘
```

### Table Descriptions

#### `jobs`
Tracks async log processing jobs.
- **id** (string, PK): UUID job identifier
- **filename** (string): Original uploaded filename
- **file_size** (integer): Size in bytes
- **status** (enum): PENDING | PROCESSING | COMPLETED | FAILED
- **progress** (integer): 0-100 percentage
- **result_summary** (text): JSON summary of results
- **error_message** (text): Error details if failed
- **started_at**, **completed_at**, **created_at** (datetime)

#### `incidents`
Stores detected issues from log processing.
- **id** (integer, PK): Auto-increment ID
- **title** (string): Incident title (pattern name match)
- **description** (text): Detailed description
- **severity** (enum): LOW | MEDIUM | HIGH | CRITICAL
- **status** (enum): OPEN | IN_PROGRESS | RESOLVED | ESCALATED
- **raw_log** (text): The actual log line that triggered the incident
- **node_id** (FK): Source node reference
- **pattern_id** (FK): Matched pattern reference
- **job_id** (FK): Processing job reference
- **processed_at**, **created_at**, **updated_at** (datetime)

#### `nodes`
Represents source systems (OneFS nodes, Linux servers, etc.).
- **id** (integer, PK): Auto-increment ID
- **hostname** (string, unique): Node hostname
- **ip_address** (string): IP address
- **node_type** (string): onefs | linux | vmware | unknown
- **version** (string): System version
- **description** (text): Optional description
- **created_at**, **updated_at** (datetime)

#### `patterns`
Regex patterns for log analysis.
- **id** (integer, PK): Auto-increment ID
- **name** (string, unique): Pattern name
- **description** (text): What the pattern detects
- **regex_pattern** (text): The actual regex
- **category** (string): hardware | network | security | etc.
- **severity_level** (string): LOW | MEDIUM | HIGH | CRITICAL
- **is_active** (boolean): Enabled/disabled flag
- **created_at**, **updated_at** (datetime)

#### `incident_activities`
Audit trail of incident actions.
- **id** (integer, PK): Auto-increment ID
- **incident_id** (FK): Related incident
- **user_id** (string): User who performed action
- **action_type** (enum): START_WORK | ESCALATE | RESOLVE | COMMENT | ASSIGN
- **description** (text): Action description
- **details** (text): JSON additional data
- **created_at** (datetime)

### Indexes

- `jobs`: id, status
- `nodes`: id, hostname (unique)
- `patterns`: id, name (unique), category, is_active, severity_level
- `incidents`: id, severity, status, node_id, pattern_id, job_id, title

---

## 📡 API Documentation

### Authentication

All endpoints (except `/`, `/health`, `/login`, `/docs`) require JWT authentication via Bearer token header:

```
Authorization: Bearer <access_token>
```

### Endpoint Categories

#### 🔐 Authentication (`/api/v1/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/login` | Authenticate and get JWT tokens |
| POST | `/refresh` | Refresh access token |
| GET | `/me` | Get current user info |
| POST | `/logout` | Logout (client-side token removal) |

**Login Request:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Login Response:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer",
  "refresh_token": "eyJhbG...",
  "expires_in": 3600
}
```

#### 📤 Log Ingestion (`/api/v1/ingest`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest` | Upload log file (multipart/form-data) |
| POST | `/ingest/stream` | Submit log lines directly (JSON) |
| POST | `/ingest/cluster` | Fetch logs from OneFS cluster via SSH |
| GET | `/ingest/cluster/status` | Check OneFS cluster connectivity |

**File Upload:**
```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/var/log/messages" \
  -F "node_hostname=node-01"
```

**Stream Logs:**
```json
POST /api/v1/ingest/stream
{
  "log_lines": [
    "Mar 27 10:15:32 node-01 isilon_d[1234]: [CRITICAL] System failure",
    "Mar 27 10:16:45 node-01 kernel: [ Hardware Error ] CPU temperature"
  ],
  "node_hostname": "node-01",
  "description": "OneFS cluster logs"
}
```

#### 🚨 Incidents (`/api/v1/incidents`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/incidents` | List incidents (with filtering) |
| GET | `/incidents/{id}` | Get specific incident |
| PUT | `/incidents/{id}/status` | Update incident status |
| GET | `/incidents/{id}/activities` | Get incident history |

**Query Parameters for List:**
- `severity`: LOW, MEDIUM, HIGH, CRITICAL
- `status`: OPEN, IN_PROGRESS, RESOLVED, ESCALATED
- `node_id`: Filter by source node
- `pattern_id`: Filter by pattern
- `search`: Text search in title/description
- `skip`, `limit`: Pagination

#### 💼 Jobs (`/api/v1/jobs`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{id}` | Get job details |
| DELETE | `/jobs/{id}` | Delete completed/failed job |
| POST | `/jobs/{id}/cancel` | Cancel running job |
| GET | `/jobs/{id}/progress` | SSE stream for real-time progress |

**Job Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "messages.log",
  "file_size": 1048576,
  "status": "COMPLETED",
  "progress": 100,
  "result_summary": {
    "total_lines": 10000,
    "processed_lines": 10000,
    "incidents_created": 15,
    "patterns_matched": 5
  },
  "created_at": "2024-03-27T10:00:00",
  "started_at": "2024-03-27T10:00:05",
  "completed_at": "2024-03-27T10:01:30"
}
```

#### 🎯 Patterns (`/api/v1/patterns`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/patterns` | List patterns (with filtering) |
| GET | `/patterns/{id}` | Get pattern details |
| POST | `/patterns` | Create new pattern |
| PUT | `/patterns/{id}` | Update pattern |
| PUT | `/patterns/{id}/toggle` | Enable/disable pattern |
| DELETE | `/patterns/{id}` | Delete pattern (if no incidents) |
| GET | `/patterns/categories` | List unique categories |
| POST | `/patterns/test` | Test regex against log line |

**Pattern Testing:**
```json
POST /api/v1/patterns/test
{
  "regex_pattern": "disk.*fail",
  "test_line": "Disk failure detected on /dev/sda"
}
```

**Response:**
```json
{
  "matches": true,
  "matched_text": "Disk failure detected",
  "groups": []
}
```

#### 🖥️ Nodes (`/api/v1/nodes`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/nodes` | List all nodes |
| GET | `/nodes/{id}` | Get node details |
| GET | `/nodes/{id}/incidents` | Get incidents for node |
| POST | `/nodes` | Create node (manual) |
| PUT | `/nodes/{id}` | Update node |
| DELETE | `/nodes/{id}` | Delete node (if no incidents) |
| GET | `/nodes/types/list` | List unique node types |

#### 🔧 Cluster (`/api/v1/cluster`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cluster/status` | Get OneFS cluster status |
| GET | `/cluster/nodes` | Get detailed node information |
| GET | `/cluster/test-connection` | Test SSH connectivity |

#### 🛠️ Database Admin (`/api/v1/admin`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/query` | Execute read-only SQL query |
| GET | `/admin/tables` | List all tables with row counts |
| GET | `/admin/schema` | Get full database schema |
| GET | `/admin/schema/{table}` | Get specific table schema |
| GET | `/admin/quick-queries` | Get predefined useful queries |

**Query Request (READ-ONLY):**
```json
{
  "query": "SELECT * FROM incidents WHERE severity = 'CRITICAL' LIMIT 10",
  "limit": 1000
}
```

#### 📊 Analytics (`/api/v1/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/summary` | Get incident summary (24h window) |
| GET | `/escalations` | Get high-priority open incidents |

---

## 🎨 Frontend

### Page Overview

| Page | Route | Description | Key Features |
|------|-------|-------------|--------------|
| **Login** | `/login` | Authentication | JWT login, form validation |
| **Dashboard** | `/` | Analytics overview | Charts, stats, recent incidents |
| **Incidents** | `/incidents` | Incident management | Filter, search, update status |
| **Jobs** | `/jobs` | Job queue | Real-time progress, cancel jobs |
| **Patterns** | `/patterns` | Pattern CRUD | Regex testing, toggle active |
| **Nodes** | `/nodes` | Node management | View node incidents |
| **Cluster** | `/cluster` | OneFS monitoring | Cluster status, SSH test |
| **Database** | `/database` | SQL interface | Query editor, quick queries |
| **Ingest** | `/ingest` | Log upload | Drag-drop, stream input |

### Component Library

| Component | Purpose |
|-----------|---------|
| `Layout.tsx` | App shell with navigation, header, footer |
| `FileUpload.tsx` | Drag-and-drop file upload with progress |
| `ProgressBar.tsx` | Animated progress indicator |
| `StatusBadge.tsx` | Severity/status colored badges |
| `ActivityTimeline.tsx` | Incident activity history |
| `SearchInput.tsx` | Search with debounce |
| `EscalateModal.tsx` | Incident escalation dialog |
| `ErrorBoundary.tsx` | React error catching |
| `ProtectedRoute.tsx` | Authentication route guard |

### State Management

- **React Query**: Server state (incidents, jobs, patterns)
- **localStorage**: JWT tokens (access_token, refresh_token)
- **SSE**: Real-time job progress updates

---

## 🔍 Pattern Matching

### Built-in Patterns (23 Total)

#### Critical Severity

| Pattern | Regex | Description |
|---------|-------|-------------|
| **Disk Failure** | `(disk\|drive).*fail\|(error\|critical).*disk` | Physical disk failures |
| **SMART Disk Failure** | `smartd.*fail\|smart.*error\|disk.*predict.*fail` | SMART predictive failures |
| **Power Supply Failure** | `power.*supply.*fail\|psu.*fail\|ups.*fail` | Power issues |
| **OneFS System Alert** | `isilon_d.*critical\|isi.*critical\|system.*alert` | OneFS daemon alerts |
| **Cluster Quorum Issue** | `cluster.*quorum\|node.*disconnect\|gmp.*fail` | Cluster membership problems |

#### High Severity

| Pattern | Description |
|---------|-------------|
| **Storage Pool Degraded** | Pool status changes to degraded |
| **NFS Timeout** | NFS request timeouts |
| **CIFS Connection Failed** | SMB/CIFS authentication failures |
| **Kerberos Error** | Kerberos ticket/AD issues |
| **LDAP Connection Timeout** | Directory service connectivity |
| **S3 API Error** | Object storage API failures |
| **Job Engine Failure** | Backup/snapshot job failures |
| **Memory Pressure** | High memory utilization |
| **Snapshot Error** | Snapshot creation/deletion issues |
| **Replication Error** | SyncIQ replication failures |

#### Medium Severity

| Pattern | Description |
|---------|-------------|
| **Network Interface Error** | NIC/link issues |
| **Authentication Failure** | Failed login attempts |
| **Permission Denied** | Filesystem access denied |
| **Protocol Error** | Protocol-specific errors |
| **Audit Event** | Security audit events |
| **License Warning** | License expiration warnings |
| **Fan Failure** | Cooling system issues |
| **Temperature Warning** | Thermal warnings |

### Adding Custom Patterns

```python
# Via API
POST /api/v1/patterns
{
  "name": "Custom Pattern",
  "description": "Detects custom application errors",
  "regex_pattern": "myapp.*error|custom.*fail",
  "category": "application",
  "severity_level": "HIGH"
}
```

---

## 🧪 Testing

### Test Structure

```
tests/
├── unit/                    # Fast unit tests
│   ├── test_models.py       # Model creation, enums, relationships
│   ├── test_patterns.py     # Regex matching, pattern behavior
│   └── test_workers.py      # Severity mapping, job summaries
├── integration/             # Integration tests with containers
│   ├── test_database.py     # PostgreSQL connectivity
│   └── test_ingestion.py    # End-to-end log processing
├── test_api.py              # API endpoint tests
└── test_onefs_integration.py # OneFS-specific pattern tests
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/unit/test_patterns.py -v

# Integration tests only
pytest tests/integration/ -v
```

### Test Coverage Areas

- **Models**: Creation, relationships, enums, constraints
- **Patterns**: Regex matching, default patterns, severity levels
- **Workers**: Severity mapping, job summaries, progress calculation
- **API**: All endpoints, authentication, filtering, pagination
- **OneFS**: Pattern matching, log processing, node creation

### CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`):

1. **Setup**: Python 3.11, PostgreSQL 15, Redis 7
2. **Install**: Dependencies from `requirements.txt`
3. **Database**: Run Alembic migrations, create default patterns
4. **Test**: Run unit and integration tests
5. **Coverage**: Upload to Codecov
6. **Lint**: black, isort, flake8, mypy
7. **Docker**: Build and test API/worker images
8. **Security**: Trivy vulnerability scan

---

## � Docker/Podman Setup

### Windows with Podman (Recommended)

```bash
# 1. Install Podman for Windows
# Download from: https://podman.io/docs/installation/windows

# 2. Build optimized images (fast builds)
./build-api.bat      # Builds API image in ~2 minutes
./build-worker.bat   # Builds worker image in ~2 minutes

# 3. Start services
podman-compose -f podman-compose.yml up -d

# 4. Access services
# API: http://localhost:8000
# Frontend: http://localhost:3000
# Docs: http://localhost:8000/docs
```

### Linux/macOS with Docker

```bash
# 1. Clone repository
git clone https://github.com/chana13/async-log-intelligence-api.git
cd async-log-intelligence-api

# 2. Build and start
docker-compose up -d

# 3. Access services
# API: http://localhost:8000
# Frontend: http://localhost:3000
```

### Build Optimization

The project includes optimized build scripts that:

- **Exclude unnecessary files** (frontend, tests, docs) from build context
- **Use proper layer caching** (dependencies first, then source code)
- **Minimize system dependencies** with cleanup
- **Build in ~2 minutes** instead of 10+ minutes

---

## ⚡ Fast Builds

### Troubleshooting Slow Builds

If builds are taking too long:

1. **Use the optimized build scripts**:
   ```bash
   ./build-api.bat      # Windows
   ./build-api.sh       # Linux/macOS
   ```

2. **Check .dockerignore** - ensures only necessary files are copied
3. **Verify layer caching** - dependencies should be cached between builds
4. **Use --no-cache only when needed** - for dependency changes

### Build Context Size

The optimized build reduces context from ~500MB to ~50MB by excluding:
- `frontend/` (React app - 400MB+ with node_modules)
- `tests/` (test files)
- `docs/` (documentation)
- `.git/` (git history)
- IDE files, cache files, logs

### Manual Build (if scripts fail)

```bash
# Create minimal build context
mkdir build-context
cp -r src build-context/
cp requirements.txt pyproject.toml build-context/
cp docker/Dockerfile.api build-context/

# Build from context directory
cd build-context
podman build -t localhost/log-intelligence-api:latest -f Dockerfile .
```

---

## �🚀 Deployment

### Quick Start (Docker Compose)

```bash
# 1. Clone repository
git clone https://github.com/chana13/async-log-intelligence-api.git
cd async-log-intelligence-api

# 2. Configure environment
cp .env.example .env
# Edit .env with your OneFS cluster details

# 3. Build and start
podman-compose up -d  # or docker-compose

# 4. Access
# API: http://localhost:8000
# Frontend: http://localhost:5173
# Docs: http://localhost:8000/docs
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | FastAPI REST API |
| Frontend | 5173 | React dev server (Vite) |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Message queue |
| Nginx | 80 | Production reverse proxy |

### Production Deployment

```bash
# Production with nginx
docker-compose -f docker-compose.full-stack.yml up -d

# Scale workers
docker-compose up -d --scale worker=4
```

### Environment Variables

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/log_intelligence

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here

# OneFS Cluster
CLUSTER_HOST=<your-cluster-ip>  # e.g. export CLUSTER_HOST=203.0.113.10
CLUSTER_PORT=50019
ISILON_USER=root
ISILON_PASS=password
SSH_KEY_PATH=/root/.ssh/id_ed25519

# API
API_HOST=0.0.0.0
API_PORT=8000
MAX_FILE_SIZE_MB=2048
```

---

## 📈 Performance

### Benchmarks

| Metric | Value |
|--------|-------|
| **File Size Limit** | 2GB per upload |
| **Processing Speed** | ~10,000 lines/second (depends on patterns) |
| **Concurrent Jobs** | Unlimited (limited by Celery workers) |
| **Database** | PostgreSQL connection pooling (default 10) |
| **API Rate Limiting** | 10 req/s (nginx), 5 req/min login |

### Scalability

- **Horizontal**: Scale Celery workers independently
- **Database**: Use read replicas for analytics queries
- **Caching**: Redis caching for pattern lookups
- **File Storage**: Temporary file cleanup after processing

### Optimization Tips

1. **Increase workers**: `docker-compose up -d --scale worker=4`
2. **Database indexes**: Already optimized (see schema section)
3. **Pattern efficiency**: Avoid expensive regex (backtracking)
4. **File chunking**: Large files processed in chunks

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# 1. Clone repo
git clone https://github.com/chana13/async-log-intelligence-api.git

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup pre-commit hooks
pre-commit install

# 5. Run tests
pytest

# 6. Start development server
uvicorn src.app.main:app --reload
```

### Code Quality

- **black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **pytest**: Testing

All checks run automatically via pre-commit hooks and CI.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **FastAPI** for the amazing web framework
- **Celery** for reliable task processing
- **SQLAlchemy** for powerful ORM capabilities
- **React Query** for elegant server state management
- **Tailwind CSS** for rapid UI development

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/chana13/async-log-intelligence-api/issues)
- **Discussions**: [GitHub Discussions](https://github.com/chana13/async-log-intelligence-api/discussions)
- **Email**: chana.miller@example.com

---

**Built with ❤️ for the OneFS community**

*Async Log Intelligence API - Making OneFS log processing intelligent and automated*
