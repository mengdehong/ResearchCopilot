"""Agent API router — stub endpoints pending P2 completion."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/threads", tags=["agent"])

# TODO(P2): replace stubs with real agent_service integration after P2 completion.
# Endpoints to implement:
# POST /threads/{id}/runs — trigger agent run
# GET /threads/{id}/events — SSE event stream
# POST /threads/{id}/interrupt — HITL response
