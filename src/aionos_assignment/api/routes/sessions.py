"""
Session routes -- retrieve conversation history and actions.

GET /session/{session_id}          -- full conversation history
GET /session/{session_id}/actions  -- all actions taken in session
DELETE /session/{session_id}       -- close a session
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from aionos_assignment.api.schemas import (
    ActionEntry,
    ConversationTurn,
    SessionActionsResponse,
    SessionHistoryResponse,
)
from aionos_assignment.db.database import get_db
from aionos_assignment.db.models import ActionLog, Conversation, Session as SessionModel

router = APIRouter(prefix="/session", tags=["Session"])


@router.get("/{session_id}", response_model=SessionHistoryResponse)
def get_session_history(session_id: str, db: DBSession = Depends(get_db)):
    """Return full conversation history for the given session."""
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    turns_rows = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.turn_index, Conversation.id)
        .all()
    )

    turns = [
        ConversationTurn(
            role=row.role,
            content=row.message,
            intent=row.intent,
            timestamp=row.timestamp,
            turn_index=row.turn_index,
        )
        for row in turns_rows
    ]

    return SessionHistoryResponse(
        session_id=session_id,
        turns=turns,
        is_escalated=bool(session.is_escalated),
        is_closed=bool(session.is_closed),
    )


@router.get("/{session_id}/actions", response_model=SessionActionsResponse)
def get_session_actions(session_id: str, db: DBSession = Depends(get_db)):
    """Return all actions logged for the given session."""
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    action_rows = (
        db.query(ActionLog)
        .filter(ActionLog.session_id == session_id)
        .order_by(ActionLog.id)
        .all()
    )

    actions = [
        ActionEntry(
            action_type=row.action_type,
            details=row.get_details(),
            status=row.status,
            timestamp=row.timestamp,
        )
        for row in action_rows
    ]

    return SessionActionsResponse(session_id=session_id, actions=actions)


@router.delete("/{session_id}")
def close_session(session_id: str, db: DBSession = Depends(get_db)):
    """Mark a session as closed."""
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.is_closed = 1
    db.commit()
    return {"message": f"Session {session_id} closed."}
