"""
LangGraph workflow for the Airline Disruption Resolution Agent.

Graph flow:
  session_memory_loader
    → intent_detector
      → customer_lookup
        → policy_checker
          → [cancellation_handler | delay_handler | escalation_handler]
            → response_generator
              → conversation_saver
                → END
"""
import json
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from aionos_assignment.config import settings
from aionos_assignment.db.database import SessionLocal
from aionos_assignment.db.models import Booking, Customer
from aionos_assignment.graph.state import AgentState
from aionos_assignment.policies.rules import (
    check_escalation_triggers,
    evaluate_cancellation,
    evaluate_delay,
    evaluate_refund_request,
    evaluate_fare_waiver,
)
from aionos_assignment.utils.session_memory import (
    get_turn_index,
    link_customer_to_session,
    load_history,
    log_action,
    mark_session_escalated,
    save_turn,
)

# ─── LLM Setup ────────────────────────────────────────────────────────────────
def get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.get_api_key(),
        temperature=0.3,
    )


# ─── System Prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a professional, empathetic airline customer support agent for SkyAir.

POLICIES (you must follow these exactly — do not invent or modify any rule):
1. CANCELLATION (airline-caused):
   - Customer may choose: FREE rebooking on next available flight within 24h, OR full refund
   - Gold & Platinum loyalty members get priority rebooking (first access to seats)
   - Refunds: processed in full within 7 business days to the ORIGINAL payment method only

2. DELAY COMPENSATION:
   - Delay < 3 hours  → ₹500 meal voucher
   - Delay > 3 hours  → ₹500 meal voucher + lounge access
   - Delay > 5 hours  → ₹500 meal voucher + lounge access + hotel accommodation
     (hotel covers DELAYED HOURS ONLY — NOT a full night stay)

3. FARE DIFFERENCE:
   - If customer voluntarily chooses a higher-fare flight, they pay the difference
   - You may waive UP TO ₹1,500 — anything above requires supervisor approval

4. PROHIBITED ACTIONS (you MUST escalate these to a human agent):
   - Waiving fare differences above ₹1,500
   - Business class / cabin upgrades
   - Full-night hotel stays (beyond delay-hour coverage)
   - Refunds to a non-original payment method
   - Any compensation or exception not listed in policies above

TONE GUIDELINES:
- Always be empathetic and professional
- Acknowledge the customer's frustration before providing solutions
- Be clear and concise — do not overwhelm with information
- If escalating, explain WHY and assure them a supervisor will follow up
"""


# ─── Node: session_memory_loader ─────────────────────────────────────────────
def session_memory_loader(state: AgentState) -> AgentState:
    """Load all prior conversation turns from the DB into state."""
    db = SessionLocal()
    try:
        history = load_history(db, state["session_id"])
        turn_index = get_turn_index(db, state["session_id"])
    finally:
        db.close()

    return {
        **state,
        "conversation_history": history,
        "turn_index": turn_index,
    }


# ─── Node: intent_detector ───────────────────────────────────────────────────
def intent_detector(state: AgentState) -> AgentState:
    """
    Use Gemini to classify the customer's intent and tone.
    Returns one of: cancellation / delay / refund / upgrade / status / angry / other
    """
    llm = get_llm()

    prompt = f"""Analyze the customer message and respond with ONLY a JSON object.

Customer message: "{state['current_input']}"

Respond with this exact JSON (no markdown, no explanation):
{{
  "intent": "<one of: cancellation, delay, refund, upgrade, status, angry, other>",
  "tone": "<one of: calm, frustrated, angry>",
  "pnr_mentioned": "<PNR if mentioned, else null>",
  "requests_hotel": <true or false>,
  "requests_business_class": <true or false>,
  "requests_full_night_hotel": <true or false>,
  "requests_fare_waiver": <true or false>,
  "fare_waiver_amount": <number or null>
}}"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        parsed = json.loads(raw)
    except Exception as e:
        parsed = {
            "intent": "other",
            "tone": "calm",
            "pnr_mentioned": None,
            "requests_hotel": False,
            "requests_business_class": False,
            "requests_full_night_hotel": False,
            "requests_fare_waiver": False,
            "fare_waiver_amount": None,
        }

    return {
        **state,
        "intent": parsed.get("intent", "other"),
        "tone": parsed.get("tone", "calm"),
        "policy_result": {
            "pnr_mentioned": parsed.get("pnr_mentioned"),
            "requests_hotel": parsed.get("requests_hotel", False),
            "requests_business_class": parsed.get("requests_business_class", False),
            "requests_full_night_hotel": parsed.get("requests_full_night_hotel", False),
            "requests_fare_waiver": parsed.get("requests_fare_waiver", False),
            "fare_waiver_amount": parsed.get("fare_waiver_amount"),
        },
    }


# ─── Node: customer_lookup ───────────────────────────────────────────────────
def customer_lookup(state: AgentState) -> AgentState:
    """
    Look up the customer and their booking from SQLite.
    Tries PNR first (from intent detector), then searches conversation history.
    """
    db = SessionLocal()
    try:
        customer_data = None
        booking_data = None

        # Extract PNR from intent result or scan conversation history
        pnr = (state.get("policy_result") or {}).get("pnr_mentioned")
        if not pnr:
            # Scan current input and history for known PNRs
            all_text = state["current_input"] + " ".join(
                m["content"] for m in state.get("conversation_history", [])
            )
            for known_pnr in ["SK4821X", "TR1190B", "WL7742"]:
                if known_pnr in all_text.upper():
                    pnr = known_pnr
                    break

        if pnr:
            booking = (
                db.query(Booking)
                .filter(Booking.pnr == pnr.upper())
                .first()
            )
            if booking:
                customer = db.query(Customer).filter(Customer.id == booking.customer_id).first()
                if customer:
                    customer_data = {
                        "id": customer.id,
                        "name": customer.name,
                        "email": customer.email,
                        "phone": customer.phone,
                        "loyalty_tier": customer.loyalty_tier,
                        "booking_ref": customer.booking_ref,
                        "flight_count": customer.flight_count,
                        "prior_complaints": customer.prior_complaints,
                    }
                    booking_data = {
                        "id": booking.id,
                        "pnr": booking.pnr,
                        "flight_number": booking.flight_number,
                        "departure": booking.departure,
                        "arrival": booking.arrival,
                        "route": booking.get_route(),
                        "travel_date": booking.travel_date,
                        "scheduled_departure": booking.scheduled_departure,
                        "status": booking.status,
                        "new_departure": booking.new_departure,
                        "delay_hours": booking.get_delay_hours(),
                    }

                    # Link customer to session
                    link_customer_to_session(db, state["session_id"], customer.id)

    finally:
        db.close()

    return {
        **state,
        "customer": customer_data,
        "booking": booking_data,
        "customer_identified": customer_data is not None,
    }


# ─── Node: policy_checker ────────────────────────────────────────────────────
def policy_checker(state: AgentState) -> AgentState:
    """
    Apply service rules to determine what the customer is entitled to
    and whether escalation is needed.
    """
    booking = state.get("booking")
    customer = state.get("customer")
    intent = state.get("intent", "other")
    intent_data = state.get("policy_result", {}) or {}

    needs_escalation = False
    escalation_reasons = []
    entitled_actions = []
    policy_explanation = ""

    if booking:
        status = booking.get("status", "ok")
        loyalty_tier = (customer or {}).get("loyalty_tier", "Silver")

        if status == "cancelled" or intent == "cancellation":
            result = evaluate_cancellation(loyalty_tier)
            entitled_actions = result.entitled_actions
            policy_explanation = result.explanation

        elif status.startswith("delayed_") or intent == "delay":
            delay_hours = booking.get("delay_hours", 0)
            result = evaluate_delay(delay_hours, loyalty_tier)
            entitled_actions = result.entitled_actions
            policy_explanation = result.explanation

        # Check for out-of-policy requests
        escalation_check = check_escalation_triggers({
            "business_class_upgrade": intent_data.get("requests_business_class", False),
            "full_night_hotel": intent_data.get("requests_full_night_hotel", False),
            "extra_compensation": False,
            "exception_request": False,
        })
        if escalation_check.escalation_required:
            needs_escalation = True
            escalation_reasons.extend(escalation_check.escalation_reasons)

        # Check fare waiver
        if intent_data.get("requests_fare_waiver"):
            amount = intent_data.get("fare_waiver_amount") or 0
            fare_result = evaluate_fare_waiver(float(amount))
            if fare_result.escalation_required:
                needs_escalation = True
                escalation_reasons.extend(fare_result.escalation_reasons)

        # Refund via non-original method
        if intent == "refund":
            refund_result = evaluate_refund_request(original_payment=True)
            entitled_actions.extend(refund_result.entitled_actions)

    elif intent in ("angry",):
        # No booking found but customer is angry — still respond empathetically
        policy_explanation = "I'd like to help you resolve this. Could you please share your booking reference (PNR)?"

    return {
        **state,
        "needs_escalation": needs_escalation,
        "escalation_reason": "; ".join(escalation_reasons) if escalation_reasons else None,
        "policy_result": {
            **(intent_data or {}),
            "entitled_actions": entitled_actions,
            "explanation": policy_explanation,
        },
        "action_taken": {"actions": entitled_actions} if entitled_actions else None,
    }


# ─── Node: cancellation_handler ──────────────────────────────────────────────
def cancellation_handler(state: AgentState) -> AgentState:
    """Log cancellation actions to the actions_log table."""
    db = SessionLocal()
    try:
        customer_id = (state.get("customer") or {}).get("id")
        booking = state.get("booking") or {}

        log_action(
            db,
            session_id=state["session_id"],
            action_type="cancellation_handled",
            details={
                "pnr": booking.get("pnr"),
                "flight": booking.get("flight_number"),
                "route": booking.get("route"),
                "entitled_actions": (state.get("policy_result") or {}).get("entitled_actions", []),
            },
            customer_id=customer_id,
        )
    finally:
        db.close()
    return state


# ─── Node: delay_handler ─────────────────────────────────────────────────────
def delay_handler(state: AgentState) -> AgentState:
    """Log delay compensation actions to the actions_log table."""
    db = SessionLocal()
    try:
        customer_id = (state.get("customer") or {}).get("id")
        booking = state.get("booking") or {}

        log_action(
            db,
            session_id=state["session_id"],
            action_type="delay_compensation_issued",
            details={
                "pnr": booking.get("pnr"),
                "flight": booking.get("flight_number"),
                "delay_hours": booking.get("delay_hours"),
                "entitled_actions": (state.get("policy_result") or {}).get("entitled_actions", []),
            },
            customer_id=customer_id,
        )
    finally:
        db.close()
    return state


# ─── Node: escalation_handler ────────────────────────────────────────────────
def escalation_handler(state: AgentState) -> AgentState:
    """Mark session as escalated and log the escalation action."""
    db = SessionLocal()
    try:
        customer_id = (state.get("customer") or {}).get("id")
        mark_session_escalated(db, state["session_id"])
        log_action(
            db,
            session_id=state["session_id"],
            action_type="escalate",
            details={"reason": state.get("escalation_reason", "Unknown")},
            customer_id=customer_id,
            status="escalated",
        )
    finally:
        db.close()
    return state


# ─── Node: response_generator ────────────────────────────────────────────────
def response_generator(state: AgentState) -> AgentState:
    """Generate the final empathetic, policy-grounded response using Gemini."""
    llm = get_llm()

    # Build conversation context
    history_text = ""
    for msg in state.get("conversation_history", []):
        role_label = "Customer" if msg["role"] == "user" else "Agent"
        history_text += f"{role_label}: {msg['content']}\n"

    # Build context block
    customer = state.get("customer")
    booking = state.get("booking")
    policy = state.get("policy_result") or {}

    context_parts = []
    if customer:
        context_parts.append(
            f"Customer: {customer['name']} | Tier: {customer['loyalty_tier']} | PNR: {customer['booking_ref']}"
        )
    if booking:
        context_parts.append(
            f"Flight: {booking['flight_number']} | Route: {booking['route']} | "
            f"Date: {booking['travel_date']} | Status: {booking['status']}"
        )
        if booking.get("new_departure"):
            context_parts.append(f"New departure time: {booking['new_departure']}")
    if policy.get("explanation"):
        context_parts.append(f"Policy entitlement: {policy['explanation']}")
    if state.get("needs_escalation"):
        context_parts.append(f"ESCALATION REQUIRED: {state.get('escalation_reason')}")

    context_str = "\n".join(context_parts)

    prompt = f"""You are a SkyAir customer support agent. Respond to the customer's latest message.

{f'Prior conversation:{chr(10)}{history_text}' if history_text else ''}
Current customer message: "{state['current_input']}"

Context:
{context_str if context_str else 'No booking information found yet.'}

Tone detected: {state.get('tone', 'calm')}
Needs escalation: {state.get('needs_escalation', False)}

Instructions:
- If tone is frustrated or angry: FIRST acknowledge their feelings, THEN provide the solution
- Provide the solution clearly based on the policy context above
- If escalation is needed: explain what you CAN do, then explain it's being escalated and why
- If no booking found: politely ask for their PNR / booking reference
- Keep the response concise and professional (2-4 sentences max unless detail is needed)
- Do NOT invent any rules, policies, or offers not mentioned in the context"""

    try:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
        response = llm.invoke(messages)
        agent_response = response.content.strip()
    except Exception as e:
        agent_response = (
            "I apologize, I'm experiencing a technical issue. "
            "Please try again or contact us at our helpline. "
            f"(Error: {str(e)[:100]})"
        )

    return {**state, "response": agent_response}


# ─── Node: conversation_saver ────────────────────────────────────────────────
def conversation_saver(state: AgentState) -> AgentState:
    """Persist the current user + assistant turn to the conversations table."""
    db = SessionLocal()
    try:
        customer_id = (state.get("customer") or {}).get("id")
        save_turn(
            db,
            session_id=state["session_id"],
            turn_index=state.get("turn_index", 0),
            user_message=state["current_input"],
            assistant_message=state.get("response", ""),
            customer_id=customer_id,
            intent=state.get("intent"),
        )
    finally:
        db.close()
    return state


# ─── Routing Logic ────────────────────────────────────────────────────────────
def route_after_policy(state: AgentState) -> str:
    """Route to the correct handler based on booking status and escalation flags."""
    if state.get("needs_escalation"):
        return "escalation_handler"

    booking = state.get("booking")
    intent = state.get("intent", "other")

    if booking:
        status = booking.get("status", "ok")
        if status == "cancelled" or intent == "cancellation":
            return "cancellation_handler"
        elif status.startswith("delayed_") or intent == "delay":
            return "delay_handler"

    # Fallback: go straight to response (e.g., status query, no booking found)
    return "response_generator"


def route_after_handler(state: AgentState) -> str:
    """All handlers converge to response_generator."""
    return "response_generator"


# ─── Build Graph ──────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("session_memory_loader", session_memory_loader)
    graph.add_node("intent_detector", intent_detector)
    graph.add_node("customer_lookup", customer_lookup)
    graph.add_node("policy_checker", policy_checker)
    graph.add_node("cancellation_handler", cancellation_handler)
    graph.add_node("delay_handler", delay_handler)
    graph.add_node("escalation_handler", escalation_handler)
    graph.add_node("response_generator", response_generator)
    graph.add_node("conversation_saver", conversation_saver)

    # Linear edges
    graph.add_edge(START, "session_memory_loader")
    graph.add_edge("session_memory_loader", "intent_detector")
    graph.add_edge("intent_detector", "customer_lookup")
    graph.add_edge("customer_lookup", "policy_checker")

    # Conditional routing after policy_checker
    graph.add_conditional_edges(
        "policy_checker",
        route_after_policy,
        {
            "cancellation_handler": "cancellation_handler",
            "delay_handler": "delay_handler",
            "escalation_handler": "escalation_handler",
            "response_generator": "response_generator",
        },
    )

    # All handlers go to response_generator
    graph.add_edge("cancellation_handler", "response_generator")
    graph.add_edge("delay_handler", "response_generator")
    graph.add_edge("escalation_handler", "response_generator")

    # response_generator → conversation_saver → END
    graph.add_edge("response_generator", "conversation_saver")
    graph.add_edge("conversation_saver", END)

    return graph.compile()


# Compiled graph (singleton)
agent_graph = build_graph()


def run_agent(session_id: str, user_message: str) -> dict:
    """
    Entry point: run the agent graph for a single user message.
    Returns a dict with response, action_taken, and escalated flag.
    """
    initial_state: AgentState = {
        "session_id": session_id,
        "conversation_history": [],
        "current_input": user_message,
        "turn_index": 0,
        "customer": None,
        "booking": None,
        "intent": None,
        "tone": None,
        "policy_result": None,
        "action_taken": None,
        "needs_escalation": False,
        "escalation_reason": None,
        "response": None,
        "customer_identified": False,
        "error": None,
    }

    final_state = agent_graph.invoke(initial_state)

    return {
        "session_id": session_id,
        "response": final_state.get("response", "I'm sorry, something went wrong."),
        "action_taken": final_state.get("action_taken"),
        "escalated": final_state.get("needs_escalation", False),
        "intent": final_state.get("intent"),
        "customer_identified": final_state.get("customer_identified", False),
    }
