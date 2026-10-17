"""Database admin router for SQL queries and schema introspection."""

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.api.routers.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["database-admin"],
    dependencies=[Depends(get_current_user)],
)


class QueryRequest(BaseModel):
    """SQL query request"""

    query: str = Field(..., description="SQL SELECT query to execute")
    limit: int = Field(default=1000, ge=1, le=5000, description="Max rows to return")


class QueryResponse(BaseModel):
    """SQL query response"""

    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    query: str


class TableInfo(BaseModel):
    """Table schema information"""

    name: str
    columns: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]
    foreign_keys: List[Dict[str, Any]]
    row_count: Optional[int] = None


class SchemaResponse(BaseModel):
    """Database schema response"""

    tables: List[TableInfo]


class QuickQuery(BaseModel):
    """Quick query definition"""

    name: str
    description: str
    query: str


# Read-only safety check - only allow SELECT queries
READ_ONLY_PATTERN = re.compile(r"^\s*SELECT\s+", re.IGNORECASE)
FORBIDDEN_PATTERNS = [
    re.compile(r"\bDROP\b", re.IGNORECASE),
    re.compile(r"\bDELETE\b", re.IGNORECASE),
    re.compile(r"\bINSERT\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\b", re.IGNORECASE),
    re.compile(r"\bALTER\b", re.IGNORECASE),
    re.compile(r"\bCREATE\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
    re.compile(r"\bGRANT\b", re.IGNORECASE),
    re.compile(r"\bREVOKE\b", re.IGNORECASE),
]


def is_safe_query(query: str) -> tuple[bool, Optional[str]]:
    """
    Check if query is safe to execute (read-only SELECT).
    Returns (is_safe, error_message).
    """
    # Check if it's a SELECT query
    if not READ_ONLY_PATTERN.match(query):
        return False, "Only SELECT queries are allowed"

    # Check for forbidden patterns
    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(query):
            return False, f"Query contains forbidden operation"

    return True, None


@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest, db: Session = Depends(get_db)):
    """
    Execute a read-only SQL query and return results.
    Only SELECT queries are allowed for safety.
    """
    import time

    # Safety check
    is_safe, error_msg = is_safe_query(request.query)
    if not is_safe:
        raise HTTPException(status_code=400, detail=error_msg)

    start_time = time.time()

    try:
        # Execute query with row limit
        limited_query = f"SELECT * FROM ({request.query.strip().rstrip(';')}) AS subquery LIMIT {request.limit}"
        result = db.execute(text(limited_query))

        # Get column names
        columns = list(result.keys())

        # Fetch rows as dictionaries
        rows = []
        for row in result:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convert non-serializable types
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                row_dict[col] = value
            rows.append(row_dict)

        execution_time = (time.time() - start_time) * 1000

        return QueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=round(execution_time, 2),
            query=request.query,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query error: {str(e)}")


@router.get("/tables", response_model=List[Dict[str, Any]])
async def list_tables(db: Session = Depends(get_db)):
    """List all database tables with basic info."""
    inspector = inspect(db.bind)
    tables = []

    for table_name in inspector.get_table_names():
        # Get column count
        columns = inspector.get_columns(table_name)

        # Try to get row count
        try:
            result = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            row_count = result.scalar()
        except:
            row_count = None

        tables.append(
            {"name": table_name, "column_count": len(columns), "row_count": row_count}
        )

    return tables


@router.get("/schema/{table_name}", response_model=TableInfo)
async def get_table_schema(table_name: str, db: Session = Depends(get_db)):
    """Get detailed schema for a specific table."""
    inspector = inspect(db.bind)

    # Check if table exists
    if table_name not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    # Get columns
    columns = inspector.get_columns(table_name)
    column_list = [
        {
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col.get("nullable", True),
            "default": str(col.get("default")) if col.get("default") else None,
            "primary_key": False,  # Will be updated below
        }
        for col in columns
    ]

    # Get primary key
    pk = inspector.get_pk_constraint(table_name)
    pk_columns = pk.get("constrained_columns", []) if pk else []
    for col in column_list:
        if col["name"] in pk_columns:
            col["primary_key"] = True

    # Get indexes
    indexes = inspector.get_indexes(table_name)
    index_list = [
        {
            "name": idx["name"],
            "columns": idx["column_names"],
            "unique": idx.get("unique", False),
        }
        for idx in indexes
    ]

    # Get foreign keys
    fks = inspector.get_foreign_keys(table_name)
    fk_list = [
        {
            "name": fk["name"],
            "constrained_columns": fk["constrained_columns"],
            "referred_table": fk["referred_table"],
            "referred_columns": fk["referred_columns"],
        }
        for fk in fks
    ]

    # Get row count
    try:
        result = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        row_count = result.scalar()
    except:
        row_count = None

    return TableInfo(
        name=table_name,
        columns=column_list,
        indexes=index_list,
        foreign_keys=fk_list,
        row_count=row_count,
    )


@router.get("/schema", response_model=SchemaResponse)
async def get_full_schema(db: Session = Depends(get_db)):
    """Get complete database schema for all tables."""
    inspector = inspect(db.bind)
    tables = []

    for table_name in inspector.get_table_names():
        # Reuse the single table schema logic
        columns = inspector.get_columns(table_name)
        column_list = [
            {
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": False,
            }
            for col in columns
        ]

        pk = inspector.get_pk_constraint(table_name)
        pk_columns = pk.get("constrained_columns", []) if pk else []
        for col in column_list:
            if col["name"] in pk_columns:
                col["primary_key"] = True

        try:
            result = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            row_count = result.scalar()
        except:
            row_count = None

        tables.append(
            TableInfo(
                name=table_name,
                columns=column_list,
                indexes=[],
                foreign_keys=[],
                row_count=row_count,
            )
        )

    return SchemaResponse(tables=tables)


@router.get("/quick-queries", response_model=List[QuickQuery])
async def get_quick_queries():
    """Get list of predefined useful queries from README.md."""
    queries = [
        QuickQuery(
            name="Recent Incidents",
            description="Latest 10 incidents with node and pattern details",
            query="""SELECT i.id, i.title, i.severity, i.status, i.created_at,
       n.hostname, p.name as pattern_name
FROM incidents i
JOIN nodes n ON i.node_id = n.id
JOIN patterns p ON i.pattern_id = p.id
ORDER BY i.created_at DESC
LIMIT 10""",
        ),
        QuickQuery(
            name="Pattern Match Counts",
            description="Count incidents per pattern",
            query="""SELECT p.name, p.category, p.severity_level,
       COUNT(i.id) as incident_count
FROM patterns p
LEFT JOIN incidents i ON p.id = i.pattern_id
WHERE p.is_active = true
GROUP BY p.id, p.name, p.category, p.severity_level
ORDER BY incident_count DESC""",
        ),
        QuickQuery(
            name="Job Statistics",
            description="Summary of job processing status",
            query="""SELECT 
    status,
    COUNT(*) as count,
    AVG(CASE WHEN progress > 0 THEN progress END) as avg_progress
FROM jobs
GROUP BY status
ORDER BY count DESC""",
        ),
        QuickQuery(
            name="Node Overview",
            description="All nodes with incident counts",
            query="""SELECT 
    n.id, n.hostname, n.node_type, n.ip_address,
    COUNT(i.id) as incident_count,
    MAX(i.created_at) as last_incident
FROM nodes n
LEFT JOIN incidents i ON n.id = i.node_id
GROUP BY n.id, n.hostname, n.node_type, n.ip_address
ORDER BY incident_count DESC""",
        ),
        QuickQuery(
            name="Critical Open Incidents",
            description="All CRITICAL severity incidents still open",
            query="""SELECT i.id, i.title, i.description, i.created_at,
       n.hostname, p.name as pattern
FROM incidents i
JOIN nodes n ON i.node_id = n.id
JOIN patterns p ON i.pattern_id = p.id
WHERE i.severity = 'CRITICAL' AND i.status = 'OPEN'
ORDER BY i.created_at DESC""",
        ),
        QuickQuery(
            name="Table Row Counts",
            description="Row counts for all main tables",
            query="""SELECT 
    'incidents' as table_name, COUNT(*) as row_count FROM incidents
UNION ALL
SELECT 'nodes', COUNT(*) FROM nodes
UNION ALL
SELECT 'patterns', COUNT(*) FROM patterns
UNION ALL
SELECT 'jobs', COUNT(*) FROM jobs
UNION ALL
SELECT 'incident_activities', COUNT(*) FROM incident_activities
ORDER BY row_count DESC""",
        ),
    ]
    return queries
