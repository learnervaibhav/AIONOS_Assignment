"""
Pydantic request/response schemas for the FastAPI API.
"""
from typing import Any
from pydantic import BaseModel


# ─── Chat ─────────────────────────────────────────────────────────────────────
class ChatStartResponse(BaseModel):
    session_id: str
    message: str = "Session started. How can I help you today?"


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    action_taken: dict | None = None
    escalated: bool = False
    intent: str | None = None
    customer_identified: bool = False


# ─── Session ──────────────────────────────────────────────────────────────────
class ConversationTurn(BaseModel):
    role: str
    content: str
    intent: str | None = None
    timestamp: str | None = None
    turn_index: int = 0


class SessionHistoryResponse(BaseModel):
    session_id: str
    turns: list[ConversationTurn]
    is_escalated: bool = False
    is_closed: bool = False


class ActionEntry(BaseModel):
    action_type: str
    details: dict = {}
    status: str
    timestamp: str


class SessionActionsResponse(BaseModel):
    session_id: str
    actions: list[ActionEntry]


# ─── Admin ────────────────────────────────────────────────────────────────────
class CustomerResponse(BaseModel):
    id: int
    name: str
    email: str | None
    loyalty_tier: str
    booking_ref: str | None
    flight_count: int
    prior_complaints: int


class BookingResponse(BaseModel):
    id: int
    pnr: str
    flight_number: str | None
    departure: str | None
    arrival: str | None
    route: str
    travel_date: str | None
    scheduled_departure: str | None
    status: str
    new_departure: str | None
