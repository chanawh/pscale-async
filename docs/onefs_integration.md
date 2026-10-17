# OneFS Integration Guide

This guide explains how to integrate Dell EMC Isilon OneFS log processing with the Async Log Intelligence API.

## Overview

The Async Log Intelligence API now includes comprehensive support for OneFS `/var/log/messages` format, with specialized patterns for detecting and classifying OneFS-specific events.

## OneFS Log Format

OneFS logs follow the standard syslog format found in `/var/log/messages`:

```
MMM dd HH:mm:ss hostname process[pid]: message
```

Example:
```
Mar 27 10:15:32 node-01 isilon_d[1234]: [CRITICAL] System temperature exceeds threshold: 85C
```

## Supported OneFS Patterns

### Critical System Events

- **OneFS System Alert**: Critical daemon failures and system alerts
- **Cluster Quorum Issue**: Cluster connectivity and quorum problems
- **SMART Disk Failure**: Disk SMART monitoring failures
- **Power Supply Failure**: Power supply and UPS failures

### Storage and File System

- **Storage Pool Degraded**: Storage pool availability and performance issues
- **File System Capacity**: Capacity and quota warnings
- **Snapshot Delete Error**: Snapshot creation/deletion failures

### Network Issues

- **Network Interface Down**: Interface failures and IP changes
- **NFS Timeout Error**: NFS service and client issues
- **SMB/CIFS Error**: SMB/CIFS service problems

### Security and Authentication

- **Kerberos Authentication Failure**: Kerberos ticket and authentication issues
- **LDAP/AD Connectivity**: LDAP and Active Directory connection problems
- **Security Audit Deny**: Permission and access violations

### System Operations

- **OneFS Service Failure**: Service restarts and daemon failures
- **OneFS Upgrade Event**: Software upgrade and patch events
- **Job Engine Failure**: Backup, replication, and job engine issues

## Integration Methods

### Method 1: File Upload

Upload OneFS log files directly to the API:

```bash
curl -X POST "http://localhost:8000/api/v1/ingest" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/var/log/messages" \
  -F "node_hostname=node-01"
```

### Method 2: Stream Processing

Stream log lines in real-time:

```bash
curl -X POST "http://localhost:8000/api/v1/ingest/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "log_lines": [
      "Mar 27 10:15:32 node-01 isilon_d[1234]: [CRITICAL] System temperature exceeds threshold: 85C",
      "Mar 27 10:18:22 node-02 smartd[5678]: SMART failure predicted on device /dev/sda"
    ],
    "node_hostname": "node-01"
  }'
```

### Method 3: Log Forwarding

Set up log forwarding from OneFS nodes to the API:

```bash
# Example using rsyslog forwarding
# Add to /etc/rsyslog.conf on OneFS node:
*.* @your-api-server:8000
```

## Pattern Customization

### Adding Custom Patterns

You can add custom OneFS patterns via the database or API:

```sql
INSERT INTO patterns (name, description, regex_pattern, category, severity_level) 
VALUES (
  'Custom OneFS Alert',
  'Custom alert for specific OneFS event',
  'your_custom_regex_pattern',
  'custom',
  'HIGH'
);
```

### Pattern Categories

- **system**: System-level events and daemon issues
- **cluster**: Cluster connectivity and quorum issues
- **hardware**: Hardware failures and environmental alerts
- **storage**: Storage pool and file system issues
- **network**: Network interface and protocol issues
- **security**: Authentication and permission issues
- **performance**: Performance and resource utilization issues

### Severity Levels

- **CRITICAL**: Immediate attention required (service down, data loss risk)
- **HIGH**: Important issues requiring prompt attention
- **MEDIUM**: Issues that should be addressed soon
- **LOW**: Minor issues for informational purposes

## Node Management

### Automatic Node Creation

When processing logs with a new hostname, the system automatically creates a node record:

```json
{
  "hostname": "node-01",
  "node_type": "unknown",
  "description": "Auto-created from log processing"
}
```

### Node Type Classification

You can update node types for better organization:

```bash
curl -X PUT "http://localhost:8000/api/v1/nodes/1" \
  -H "Content-Type: application/json" \
  -d '{
    "node_type": "onefs",
    "version": "9.5.0.0",
    "description": "Production OneFS node"
  }'
```

## Monitoring and Alerting

### Querying OneFS Incidents

Get all OneFS-related incidents:

```bash
curl "http://localhost:8000/api/v1/incidents?node_hostname=node-01"
```

Filter by severity:

```bash
curl "http://localhost:8000/api/v1/incidents?severity=CRITICAL"
```

Filter by category:

```bash
curl "http://localhost:8000/api/v1/incidents?category=hardware"
```

### Incident Summary

Get summary statistics for OneFS nodes:

```bash
curl "http://localhost:8000/api/v1/summary?window_hours=24&node_hostname=node-01"
```

## Real-time Monitoring

### Webhook Integration

Set up webhooks for real-time incident notifications:

```json
{
  "webhook_url": "https://your-monitoring-system.com/webhook",
  "filters": {
    "severity": ["CRITICAL", "HIGH"],
    "categories": ["hardware", "cluster"]
  }
}
```

### Dashboard Integration

Use the API endpoints to build monitoring dashboards:

- Incident counts by severity and category
- Node health status overview
- Recent critical alerts
- Historical trend analysis

## Troubleshooting

### Common Issues

1. **Pattern Not Matching**
   - Check regex syntax
   - Verify log format matches expected pattern
   - Test patterns with sample log lines

2. **No Incidents Created**
   - Verify patterns are active (`is_active = true`)
   - Check log file encoding
   - Review job status for processing errors

3. **Performance Issues**
   - Use streaming for large files
   - Monitor Celery worker queue
   - Consider batch processing for historical data

### Debugging Tools

Check job processing status:

```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

Review pattern matches:

```sql
SELECT 
  p.name,
  p.regex_pattern,
  COUNT(i.id) as incident_count
FROM patterns p
LEFT JOIN incidents i ON p.id = i.pattern_id
WHERE p.is_active = true
GROUP BY p.id, p.name, p.regex_pattern;
```

## Best Practices

### Log Collection

1. **Regular Collection**: Set up scheduled log collection from OneFS nodes
2. **Real-time Processing**: Use streaming for critical alerts
3. **Log Rotation**: Implement proper log rotation to manage disk space
4. **Consistent Naming**: Use consistent hostname conventions

### Pattern Management

1. **Regular Updates**: Review and update patterns based on new OneFS versions
2. **Testing**: Test new patterns with sample log data before production
3. **Documentation**: Document custom patterns and their purposes
4. **Version Control**: Track pattern changes over time

### Performance Optimization

1. **Batch Processing**: Process historical data in batches
2. **Queue Management**: Monitor Celery queue sizes and worker performance
3. **Database Maintenance**: Regular database maintenance and indexing
4. **Resource Monitoring**: Monitor CPU, memory, and disk usage

## Example Workflows

### Daily Log Processing

```bash
#!/bin/bash
# Process yesterday's logs from all OneFS nodes

DATE=$(date -d "yesterday" +%Y-%m-%d)
NODES=("node-01" "node-02" "node-03")

for node in "${NODES[@]}"; do
    scp "${node}:/var/log/messages.${DATE}" "/tmp/${node}_messages.${DATE}"
    
    curl -X POST "http://localhost:8000/api/v1/ingest" \
      -H "Content-Type: multipart/form-data" \
      -F "file=@/tmp/${node}_messages.${DATE}" \
      -F "node_hostname=${node}" \
      -F "description=Daily log processing for ${DATE}"
done
```

### Real-time Alert Monitoring

```python
import requests
import time

def monitor_critical_alerts():
    while True:
        response = requests.get(
            "http://localhost:8000/api/v1/incidents",
            params={
                "severity": "CRITICAL",
                "status": "OPEN",
                "limit": 10
            }
        )
        
        incidents = response.json()["incidents"]
        
        for incident in incidents:
            if incident["severity"] == "CRITICAL":
                send_alert(incident)
        
        time.sleep(60)  # Check every minute

def send_alert(incident):
    """Send alert to monitoring system"""
    print(f"CRITICAL ALERT: {incident['title']} - {incident['description']}")
    # Integration with your alerting system

if __name__ == "__main__":
    monitor_critical_alerts()
```

## Support

For additional support with OneFS integration:

1. Review the API documentation at `/docs` endpoint
2. Check the test suite for usage examples
3. Monitor system logs for processing errors
4. Contact your system administrator for cluster-specific configurations
