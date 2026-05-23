from typing import Dict, Any
from datetime import datetime

def create_heartbeat(agent_id: str = "windows-agent") -> Dict[str, Any]:
    """创建心跳消息"""
    return {
        "agent_id": agent_id,
        "timestamp": datetime.now().isoformat(),
        "status": "alive",
    }
