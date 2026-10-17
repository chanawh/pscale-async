"""
Mock SSH server for development when no real OneFS cluster is available.
This simulates OneFS cluster responses for testing the dashboard.
"""

import logging
import socket
import threading
import time
from typing import Dict, List

logger = logging.getLogger(__name__)


class MockOneFSServer:
    """Mock OneFS server that simulates cluster responses"""
    
    def __init__(self):
        self.cluster_info = {
            "name": "Mock-Cluster",
            "version": "OneFS 9.5.0.0",
            "nodes": 3,
            "status": "healthy"
        }
        
        self.nodes = [
            {
                "id": "node-01",
                "hostname": "mock-node-01",
                "status": "online",
                "ip": "192.168.1.10"
            },
            {
                "id": "node-02", 
                "hostname": "mock-node-02",
                "status": "online",
                "ip": "192.168.1.11"
            },
            {
                "id": "node-03",
                "hostname": "mock-node-03", 
                "status": "online",
                "ip": "192.168.1.12"
            }
        ]
        
        self.system_metrics = {
            "uptime": "2 days, 14:32",
            "cpu_usage": 25.5,
            "memory_usage": 67.8,
            "disk_usage": 45.2
        }

    def get_mock_response(self, command: str) -> str:
        """Return mock responses for OneFS commands"""
        command = command.strip().lower()
        
        # Mock cluster status commands
        if "isi_status" in command:
            return """Cluster: Mock-Cluster (Online)
Nodes: 3 (3 online)
Version: OneFS 9.5.0.0
Status: Healthy"""
            
        elif "isi_config" in command:
            return """Cluster Name: Mock-Cluster
Node Count: 3
Version: OneFS 9.5.0.0
Protection: +2:1"""
            
        elif "isi_for_array" in command:
            if "-n" in command:
                # Return node list
                return "mock-node-01\nmock-node-02\nmock-node-03"
            else:
                return "Mock-Cluster"
                
        elif "uptime" in command:
            return " 14:32:45 up 2 days, 14:32,  1 user,  load average: 0.15, 0.25, 0.20"
            
        elif "top" in command and "cpu" in command:
            return "25.5"
            
        elif "free" in command and "mem" in command:
            return "Mem: 8192MB used: 5555MB free: 2637MB"
            
        elif "echo" in command:
            return "SSH connection successful"
            
        else:
            # Default response for unknown commands
            return f"Mock response for: {command}"


def create_mock_ssh_responses():
    """Create a mock response handler for SSH commands"""
    mock_server = MockOneFSServer()
    
    def mock_ssh_command(command: str, timeout: int = 10) -> str:
        """Mock SSH command execution"""
        logger.info(f"Mock SSH executing: {command}")
        
        # Simulate network delay
        time.sleep(0.1)
        
        return mock_server.get_mock_response(command)
    
    return mock_ssh_command, mock_server
