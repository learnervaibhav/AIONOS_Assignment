"""
Session memory utilities — load/save conversation history from/to SQLite.
"""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from aionos_assignment.db.models import ActionLog, Conversation, Session


def create_session(db: DBSession) -> str:
    """Create a new session row and return its UUID session_id."""
    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        created_at=datetime.utcnow().isoformat(),
        last_active_at=datetime.utcnow().isoformat(),
    )
    db.add(session)
    db.commit()
    return session_id


def load_history(db: DBSession, session_id: str) -> list[dict]:
    """
    Load all conversation turns for a session, ordered by turn_index.
    Returns a list of {role, content} dicts suitable for passing to Gemini.
    """
    rows = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .order_by(Conversation.turn_index)
        .all()
    )
    return [{"role": row.role, "content": row.message} for row in rows]


def get_turn_index(db: DBSession, session_id: str) -> int:
    """Return the next turn index (count of assistant messages so far)."""
    count = (
        db.query(Conversation)
        .filter(
            Conversation.session_id == session_id,
            Conversation.role == "assistant",
        )
        .count()
    )
    return count


def save_turn(
    db: DBSession,
    session_id: str,
    turn_index: int,
    user_message: str,
    assistant_message: str,
    customer_id: int | None = None,
    intent: str | None = None,
) -> None:
    """Persist a user + assistant message pair to the conversations table."""
    user_turn = Conversation(
        session_id=session_id,
        customer_id=customer_id,
        turn_index=turn_index,
        role="user",
        message=user_message,
        intent=intent,
        timestamp=datetime.utcnow().isoformat(),
    )
    assistant_turn = Conversation(
        session_id=session_id,
        customer_id=customer_id,
        turn_index=turn_index,
        role="assistant",
        message=assistant_message,
        intent=None,
        timestamp=datetime.utcnow().isoformat(),
    )
    db.add_all([user_turn, assistant_turn])

    # Update session last_active_at
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if session:
        session.last_active_at = datetime.utcnow().isoformat()

    db.commit()


def mark_session_escalated(db: DBSession, session_id: str) -> None:
    """Mark the session as escalated."""
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if session:
        session.is_escalated = 1
        session.last_active_at = datetime.utcnow().isoformat()
        db.commit()


def log_action(
    db: DBSession,
    session_id: str,
    action_type: str,
    details: dict,
    customer_id: int | None = None,
    status: str = "completed",
) -> None:
    """Log an agent action to the actions_log table."""
    import json

    action = ActionLog(
        session_id=session_id,
        customer_id=customer_id,
        action_type=action_type,
        details=json.dumps(details),
        timestamp=datetime.utcnow().isoformat(),
        status=status,
    )
    db.add(action)
    db.commit()


def link_customer_to_session(db: DBSession, session_id: str, customer_id: int) -> None:
    """Once customer is identified, link them to the session."""
    session = db.query(Session).filter(Session.session_id == session_id).first()
    if session and session.customer_id is None:
        session.customer_id = customer_id
        db.commit()
