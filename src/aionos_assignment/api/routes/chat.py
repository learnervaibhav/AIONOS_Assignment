"""
Chat routes -- main conversation endpoints.

POST /chat/start  -- create a new session
POST /chat        -- send a message, get agent response
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from aionos_assignment.api.schemas import ChatRequest, ChatResponse, ChatStartResponse
from aionos_assignment.db.database import get_db
from aionos_assignment.db.models import Session as SessionModel
from aionos_assignment.graph.workflow import run_agent
from aionos_assignment.utils.session_memory import create_session

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/start", response_model=ChatStartResponse)
def start_session(db: DBSession = Depends(get_db)):
    """Create a new conversation session and return its session_id."""
    session_id = create_session(db)
    return ChatStartResponse(session_id=session_id)


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, db: DBSession = Depends(get_db)):
    """
    Send a user message to the agent and receive a response.
    The session_id must have been created via POST /chat/start.
    """
    # Validate session exists
    session = (
        db.query(SessionModel)
        .filter(SessionModel.session_id == request.session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Call POST /chat/start first.")

    if session.is_closed:
        raise HTTPException(status_code=400, detail="This session has been closed.")

    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    # Run the agent graph
    result = run_agent(
        session_id=request.session_id,
        user_message=request.message.strip(),
    )

    return ChatResponse(
        session_id=result["session_id"],
        response=result["response"],
        action_taken=result.get("action_taken"),
        escalated=result.get("escalated", False),
        intent=result.get("intent"),
        customer_identified=result.get("customer_identified", False),
    )
