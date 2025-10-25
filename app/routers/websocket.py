"""WebSocket endpoint for real-time updates."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Dict, List
import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        # Store connections by project_id
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: int):
        """Connect a WebSocket for a project."""
        await websocket.accept()

        if project_id not in self.active_connections:
            self.active_connections[project_id] = []

        self.active_connections[project_id].append(websocket)
        logger.info(f"WebSocket connected for project {project_id}")

    def disconnect(self, websocket: WebSocket, project_id: int):
        """Disconnect a WebSocket."""
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)

            # Clean up empty lists
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]

        logger.info(f"WebSocket disconnected for project {project_id}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")

    async def broadcast_to_project(self, project_id: int, message: dict):
        """Broadcast a message to all connections for a project."""
        if project_id not in self.active_connections:
            return

        disconnected = []

        for connection in self.active_connections[project_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to project {project_id}: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection, project_id)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/projects/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: int):
    """
    WebSocket endpoint for real-time project updates.
    """
    await manager.connect(websocket, project_id)

    try:
        # Send initial connection message
        await manager.send_personal_message(
            {
                "type": "connected",
                "project_id": project_id,
                "message": "WebSocket connected successfully",
            },
            websocket,
        )

        # Listen for messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle different message types
                action = message.get("action")

                if action == "ping":
                    # Respond to heartbeat
                    await manager.send_personal_message(
                        {"type": "pong", "timestamp": message.get("timestamp")},
                        websocket,
                    )

                elif action == "get_status":
                    # Send current project status
                    # This would query the database for current status
                    await manager.send_personal_message(
                        {
                            "type": "status_update",
                            "project_id": project_id,
                            "message": "Status requested",
                        },
                        websocket,
                    )

                else:
                    # Unknown action
                    await manager.send_personal_message(
                        {
                            "type": "error",
                            "message": f"Unknown action: {action}",
                        },
                        websocket,
                    )

            except json.JSONDecodeError:
                await manager.send_personal_message(
                    {"type": "error", "message": "Invalid JSON"},
                    websocket,
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, project_id)
        logger.info(f"Client disconnected from project {project_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, project_id)


# Helper function to broadcast updates (can be called from other parts of the app)
async def broadcast_update(project_id: int, message: dict):
    """
    Broadcast an update to all connections for a project.
    This can be called from services to push updates.
    """
    await manager.broadcast_to_project(project_id, message)
