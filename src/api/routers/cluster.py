import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.routers.auth import get_current_user
from src.core.config import settings
from src.onefs.client import OneFSClient

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=Dict[str, Any])
def get_cluster_status():
    """Get real cluster status from OneFS cluster"""
    try:
        client = OneFSClient()
        
        # Test connection first - no demo mode fallback
        try:
            client.test_connection()
            connection_status = "connected"
            logger.info(f"Successfully connected to cluster at {client.cluster_host}:{client.cluster_port}")
        except Exception as e:
            logger.error(f"Cluster connection failed: {str(e)}")
            logger.error(f"Exception type: {type(e).__name__}")
            # Return proper error instead of demo mode
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cluster connection failed: {str(e)}"
            )

        # Get cluster information
        try:
            cluster_info = client.get_cluster_info()
        except Exception as e:
            logger.error(f"Failed to get cluster info: {str(e)}")
            cluster_info = None

        # Get system metrics (basic implementation)
        try:
            # Try to get basic system info via SSH
            uptime_info = client._run_ssh_command("uptime", timeout=10)
            cpu_info = client._run_ssh_command(
                "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'", timeout=10
            )
            mem_info = client._run_ssh_command(
                "free | grep Mem | awk '{print ($3/$2)*100}'", timeout=10
            )

            metrics = {
                "uptime": uptime_info.strip() if uptime_info else "Unknown",
                "cpu_usage": (
                    float(cpu_info.strip().replace("%", ""))
                    if cpu_info and cpu_info.strip().replace("%", "").isdigit()
                    else 0.0
                ),
                "memory_usage": (
                    float(mem_info.strip())
                    if mem_info and mem_info.strip().isdigit()
                    else 0.0
                ),
                "connection_type": "SSH",
            }
        except Exception as e:
            logger.warning(f"Failed to get metrics: {str(e)}")
            metrics = None

        # Get node information (basic implementation)
        try:
            # Get node list from OneFS
            nodes_result = client._run_ssh_command("isi_for_array -n", timeout=15)
            if nodes_result:
                node_lines = [
                    line.strip()
                    for line in nodes_result.strip().split("\n")
                    if line.strip()
                ]
                nodes = []
                for i, node_line in enumerate(node_lines):
                    # Parse basic node info
                    node_status = "online"  # Default assumption
                    try:
                        # Try to get node-specific info
                        node_uptime = client._run_ssh_command(
                            f"isi_for_array -n {i+1} 'uptime'", timeout=10
                        )
                        node_status = "online" if node_uptime else "offline"
                    except:
                        node_status = "offline"

                    nodes.append(
                        {
                            "id": f"node-{i+1:02d}",
                            "hostname": node_line,
                            "status": node_status,
                            "cpu_usage": metrics["cpu_usage"] if metrics else 0.0,
                            "memory_usage": metrics["memory_usage"] if metrics else 0.0,
                            "disk_usage": 0.0,  # Would need additional implementation
                            "last_seen": uptime_info.strip() if uptime_info else "",
                            "version": "Unknown",  # Would need additional implementation
                            "role": f"node{i+1}",
                        }
                    )
            else:
                nodes = []
        except Exception as e:
            logger.warning(f"Failed to get node info: {str(e)}")
            nodes = []

        # Format cluster information
        cluster_data = None
        if cluster_info:
            if isinstance(cluster_info, dict):
                cluster_data = {
                    "hostname": settings.onefs_host or settings.cluster_host,
                    "version": cluster_info.get("version", "Unknown"),
                    "nodes": len(nodes),
                    "status": connection_status,
                }
            else:
                # Parse SSH info
                cluster_data = {
                    "hostname": settings.onefs_host or settings.cluster_host,
                    "version": "Unknown",
                    "nodes": len(nodes),
                    "status": connection_status,
                    "ssh_info": cluster_info,
                }
        else:
            cluster_data = {
                "hostname": settings.onefs_host or settings.cluster_host,
                "version": "Unknown",
                "nodes": len(nodes),
                "status": connection_status,
            }

        return {
            "status": connection_status,
            "cluster": cluster_data,
            "nodes": nodes,
            "metrics": metrics,
            "message": f"Successfully connected to cluster at {settings.onefs_host or settings.cluster_host}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_cluster_status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cluster status: {str(e)}",
        )


@router.get("/nodes", response_model=Dict[str, Any])
def get_cluster_nodes():
    """Get detailed node information from the cluster"""
    try:
        client = OneFSClient()

        # Test connection - no demo mode fallback
        try:
            client.test_connection()
        except Exception as e:
            logger.error(f"Cluster not available: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cluster connection failed: {str(e)}"
            )

        # Get detailed node information
        try:
            # Get comprehensive node status
            node_status = client._run_ssh_command("isi_status", timeout=15)
            node_config = client._run_ssh_command("isi_config", timeout=15)

            return {
                "status": "success",
                "node_status": node_status.strip() if node_status else "Unknown",
                "node_config": node_config.strip() if node_config else "Unknown",
                "cluster_ip": settings.onefs_host or settings.cluster_host,
            }
        except Exception as e:
            logger.error(f"Failed to get detailed node info: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to get node information: {str(e)}"
            )

    except Exception as e:
        logger.error(f"Unexpected error in get_cluster_nodes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get node information: {str(e)}",
        )


@router.get("/test-connection", response_model=Dict[str, Any])
def test_cluster_connection():
    """Test SSH connectivity to the OneFS cluster"""
    try:
        client = OneFSClient()

        # Test SSH connection
        try:
            client.test_connection()
            return {
                "success": True,
                "message": f"Successfully connected to cluster at {settings.cluster_host}:{settings.cluster_port} via SSH",
                "details": {
                    "host": settings.cluster_host,
                    "port": settings.cluster_port,
                    "username": settings.isilon_user,
                    "connection_type": "SSH",
                },
            }
        except Exception as e:
            logger.error(f"SSH connection test failed: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to connect to cluster: {str(e)}",
                "details": {
                    "host": settings.cluster_host,
                    "port": settings.cluster_port,
                    "username": settings.isilon_user,
                    "error": str(e),
                },
            }

    except Exception as e:
        logger.error(f"Unexpected error in test_connection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}",
        )
