"""
LangGraph AgentState definition for the Airline Disruption Resolution Agent.
"""
from typing import Any
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # ── Session & Memory ──────────────────────────────
    session_id: str                         # UUID identifying this conversation session
    conversation_history: list[dict]        # All prior turns loaded from DB [{role, content}]
    current_input: str                      # The latest user message
    turn_index: int                         # Current turn number (0-based)

    # ── Customer & Booking ────────────────────────────
    customer: dict | None                   # Customer profile from DB
    booking: dict | None                    # Booking details from DB (primary affected booking)

    # ── Intent & Tone ─────────────────────────────────
    intent: str | None                      # Detected intent: cancellation/delay/refund/status/angry/other
    tone: str | None                        # Detected tone: calm / frustrated / angry

    # ── Policy & Actions ─────────────────────────────
    policy_result: dict | None              # PolicyResult serialized as dict
    action_taken: dict | None              # The action(s) executed by the agent
    needs_escalation: bool                  # True if request exceeds agent authority
    escalation_reason: str | None           # Why escalation is needed

    # ── Output ────────────────────────────────────────
    response: str | None                    # Final response text to return to customer

    # ── Internal flags ────────────────────────────────
    customer_identified: bool               # Whether customer was found in DB
    error: str | None                       # Any error message for debugging
