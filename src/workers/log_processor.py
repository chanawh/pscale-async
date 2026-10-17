import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from celery import current_task
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.celery import celery_app
from src.core.config import settings
from src.core.storage import (
    StorageReference,
    backend_from_settings,
    stream_to_text_lines,
)
from src.db.database import Base, SessionLocal
from src.models import Incident, Job, JobStatus, Node, Pattern, Severity, Status

# Setup logging
logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def process_log_file(
    self,
    job_id: str,
    file_path: Optional[str] = None,
    log_lines: Optional[List[str]] = None,
    storage_ref: Optional[Dict[str, str]] = None,
    node_hostname: Optional[str] = None,
    description: Optional[str] = None,
):
    """
    Process a log file or log lines and extract incidents based on patterns.

    The preferred input is ``storage_ref`` — a content reference
    (``{"backend", "bucket", "key"}``) that the worker resolves through the
    configured storage backend. This is the cross-container handoff: the
    worker never assumes the upload exists on its local filesystem.
    ``file_path`` (legacy) and ``log_lines`` (stream/cluster ingest) are
    still accepted.
    """

    # Get database session
    db = SessionLocal()

    try:
        # Update job status to processing
        # Retry logic for race condition in eager mode
        job = None
        retry_count = 0
        max_retries = 3
        while not job and retry_count < max_retries:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    time.sleep(0.1)  # Short delay to allow transaction to propagate
                    db.close()
                    db = SessionLocal()
        
        if not job:
            raise Exception(f"Job {job_id} not found after {max_retries} retries")

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        db.commit()

        # Get log lines — prefer the object-storage content reference (the
        # cross-container handoff); fall back to the legacy inputs.
        if storage_ref is not None:
            ref = StorageReference.from_dict(storage_ref)
            backend = backend_from_settings(settings)
            logger.info(
                f"Processing job {job_id}: streaming object "
                f"{ref.bucket}/{ref.key} via {ref.backend} backend"
            )
            with backend.open_stream(ref) as stream:
                lines = stream_to_text_lines(stream)
        elif file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        elif log_lines:
            lines = log_lines
        else:
            raise Exception("No storage reference, file path, or log lines provided")

        total_lines = len(lines)
        processed_lines = 0
        incidents_created = 0

        # Get or create node
        node = None
        if node_hostname:
            node = db.query(Node).filter(Node.hostname == node_hostname).first()
            if not node:
                node = Node(
                    hostname=node_hostname,
                    node_type="unknown",
                    description=f"Auto-created from log processing: {description or 'No description'}",
                )
                db.add(node)
                db.commit()
                db.refresh(node)

        # Get all active patterns
        patterns = db.query(Pattern).filter(Pattern.is_active == True).all()
        logger.info(f"Processing job {job_id}: Found {len(patterns)} active patterns")
        logger.info(f"Processing job {job_id}: File has {total_lines} lines")

        # Process each line
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # Check against each pattern
            for pattern in patterns:
                try:
                    if re.search(pattern.regex_pattern, line, re.IGNORECASE):
                        # Create incident
                        incident = Incident(
                            title=f"Pattern Match: {pattern.name}",
                            description=pattern.description
                            or f"Log line matched pattern: {pattern.name}",
                            severity=map_severity(pattern.severity_level),
                            status=Status.OPEN,
                            raw_log=line,
                            node_id=node.id if node else None,
                            pattern_id=pattern.id,
                            job_id=job_id,
                        )
                        db.add(incident)
                        incidents_created += 1
                        logger.info(
                            f"Created incident {incidents_created} for pattern '{pattern.name}' on line: {line[:50]}..."
                        )

                except re.error as e:
                    # Log regex error but continue processing
                    logger.error(f"Regex error in pattern {pattern.name}: {e}")
                    continue

            processed_lines += 1

            # Update progress
            if processed_lines % 100 == 0 or processed_lines == total_lines:
                progress = int((processed_lines / total_lines) * 100)
                job.progress = progress

                # Update Celery task state (handle Windows Celery issues)
                try:
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": processed_lines,
                            "total": total_lines,
                            "progress": progress,
                            "incidents_created": incidents_created,
                        },
                    )
                except Exception as celery_error:
                    logger.warning(f"Could not update Celery state: {celery_error}")

                db.commit()

        # Update job status
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100
        job.result_summary = json.dumps(
            {
                "total_lines": total_lines,
                "processed_lines": processed_lines,
                "incidents_created": incidents_created,
                "patterns_matched": len(
                    [
                        p
                        for p in patterns
                        if any(
                            re.search(p.regex_pattern, line, re.IGNORECASE)
                            for line in lines
                        )
                    ]
                ),
            }
        )

        logger.info(
            f"Job {job_id} completed: Created {incidents_created} incidents from {total_lines} lines"
        )

        db.commit()

        # Clean up the legacy local temp file. Objects fetched via a
        # storage reference are intentionally kept: the stored object is the
        # durable upload artifact the job record points at (lifecycle/
        # retention policy is a separate concern).
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        return {
            "status": "completed",
            "job_id": job_id,
            "total_lines": total_lines,
            "processed_lines": processed_lines,
            "incidents_created": incidents_created,
            "result": job.result_summary,
        }

    except Exception as e:
        logger.error(f"Job {job_id} failed: {str(e)}")
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()

        # Clean up the legacy local temp file. Objects fetched via a
        # storage reference are intentionally kept: the stored object is the
        # durable upload artifact the job record points at (lifecycle/
        # retention policy is a separate concern).
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        # Retry with error handling for Windows Celery issues
        try:
            raise self.retry(exc=e, countdown=60, max_retries=3)
        except Exception as retry_error:
            logger.error(f"Job {job_id} failed and could not retry: {str(e)}")
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
            raise

    finally:
        db.close()


def map_severity(pattern_severity: str) -> Severity:
    """Map pattern severity level to Incident severity enum"""
    severity_mapping = {
        "LOW": Severity.LOW,
        "MEDIUM": Severity.MEDIUM,
        "HIGH": Severity.HIGH,
        "CRITICAL": Severity.CRITICAL,
    }

    return severity_mapping.get(pattern_severity.upper(), Severity.MEDIUM)


def create_default_patterns(db: Session):
    """Create default patterns for common OneFS log events"""

    default_patterns = [
        {
            "name": "Disk Failure",
            "description": "Critical disk failure detected",
            "regex_pattern": r"(disk|drive).*fail|(error|critical).*disk",
            "category": "hardware",
            "severity_level": "CRITICAL",
        },
        {
            "name": "Network Timeout",
            "description": "Network communication timeout",
            "regex_pattern": r"network.*timeout|connection.*timeout",
            "category": "network",
            "severity_level": "HIGH",
        },
        {
            "name": "High CPU Usage",
            "description": "CPU usage exceeds threshold",
            "regex_pattern": r"cpu.*high|processor.*load",
            "category": "performance",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Memory Pressure",
            "description": "System memory under pressure",
            "regex_pattern": r"memory.*pressure|out.*of.*memory",
            "category": "performance",
            "severity_level": "HIGH",
        },
        {
            "name": "Authentication Failure",
            "description": "User authentication failed",
            "regex_pattern": r"auth.*fail|login.*fail|authentication.*error",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "File System Error",
            "description": "File system operation error",
            "regex_pattern": r"filesystem.*error|fs.*error|inode.*error",
            "category": "filesystem",
            "severity_level": "HIGH",
        },
        # OneFS-specific patterns for /var/log/messages
        {
            "name": "OneFS System Alert",
            "description": "Critical OneFS system alert or daemon failure",
            "regex_pattern": r"isilon_d.*critical|isi.*critical|system.*alert",
            "category": "system",
            "severity_level": "CRITICAL",
        },
        {
            "name": "OneFS Service Failure",
            "description": "OneFS service or daemon failure/restart",
            "regex_pattern": r"isilon_d.*fail|daemon.*restart|service.*stop|isi_.*_d.*error",
            "category": "system",
            "severity_level": "HIGH",
        },
        {
            "name": "Cluster Quorum Issue",
            "description": "OneFS cluster quorum or connectivity problems",
            "regex_pattern": r"cluster.*quorum|node.*disconnect|cluster.*reform|gmp.*fail",
            "category": "cluster",
            "severity_level": "CRITICAL",
        },
        {
            "name": "SMART Disk Failure",
            "description": "SMART disk monitoring failure or prediction",
            "regex_pattern": r"smartd.*fail|smart.*error|disk.*predict.*fail|drive.*fail",
            "category": "hardware",
            "severity_level": "CRITICAL",
        },
        {
            "name": "Storage Pool Degraded",
            "description": "OneFS storage pool degraded or unavailable",
            "regex_pattern": r"pool.*degraded|storage.*pool.*fail|flexpool.*error|diskpool.*unavail",
            "category": "storage",
            "severity_level": "HIGH",
        },
        {
            "name": "File System Capacity",
            "description": "OneFS file system capacity or quota issues",
            "regex_pattern": r"filesystem.*full|quota.*exceed|capacity.*critical|space.*low",
            "category": "filesystem",
            "severity_level": "HIGH",
        },
        {
            "name": "Network Interface Down",
            "description": "Network interface failure or IP address change",
            "regex_pattern": r"interface.*down|iface.*fail|ip.*change|link.*down",
            "category": "network",
            "severity_level": "HIGH",
        },
        {
            "name": "NFS Timeout Error",
            "description": "NFS service timeout or client connection issues",
            "regex_pattern": r"nfs.*timeout|nfs.*error|nfs.*fail|rpc.*timeout",
            "category": "network",
            "severity_level": "MEDIUM",
        },
        {
            "name": "SMB/CIFS Error",
            "description": "SMB or CIFS service errors and connectivity issues",
            "regex_pattern": r"smb.*error|cifs.*fail|samba.*error|winbind.*fail",
            "category": "network",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Kerberos Authentication Failure",
            "description": "Kerberos authentication or ticket issues",
            "regex_pattern": r"kerberos.*fail|krb5.*error|ticket.*expire|auth.*krb",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "LDAP/AD Connectivity",
            "description": "LDAP or Active Directory connection problems",
            "regex_pattern": r"ldap.*timeout|ad.*connect|domain.*controller.*fail|sssd.*error",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Security Audit Deny",
            "description": "Security audit denial or permission issues",
            "regex_pattern": r"audit.*deny|permission.*denied|access.*denied|security.*violation",
            "category": "security",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Hardware Temperature Alert",
            "description": "Hardware temperature or environmental monitoring alerts",
            "regex_pattern": r"temp.*critical|temperature.*high|thermal.*alert|fan.*fail",
            "category": "hardware",
            "severity_level": "HIGH",
        },
        {
            "name": "Power Supply Failure",
            "description": "Power supply or UPS failure alerts",
            "regex_pattern": r"power.*supply.*fail|ups.*fail|psu.*error|power.*loss",
            "category": "hardware",
            "severity_level": "CRITICAL",
        },
        {
            "name": "OneFS Upgrade Event",
            "description": "OneFS software upgrade or patch events",
            "regex_pattern": r"upgrade.*start|upgrade.*complete|patch.*install|isi.*upgrade",
            "category": "system",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Snapshot Delete Error",
            "description": "OneFS snapshot creation or deletion errors",
            "regex_pattern": r"snapshot.*fail|snap.*error|isi.*snapshot.*error",
            "category": "filesystem",
            "severity_level": "MEDIUM",
        },
        {
            "name": "Job Engine Failure",
            "description": "OneFS job engine or backup job failures",
            "regex_pattern": r"job.*engine.*fail|backup.*error|replication.*fail|isi.*job.*error",
            "category": "system",
            "severity_level": "MEDIUM",
        },
    ]

    for pattern_data in default_patterns:
        existing_pattern = (
            db.query(Pattern).filter(Pattern.name == pattern_data["name"]).first()
        )

        if not existing_pattern:
            pattern = Pattern(**pattern_data)
            db.add(pattern)

    db.commit()
