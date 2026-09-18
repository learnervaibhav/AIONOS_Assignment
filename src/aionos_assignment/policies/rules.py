"""
Airline service policy rules — all logic grounded strictly in the assignment brief.

No rule may be invented here. Only the rules from the brief are encoded.
"""
from dataclasses import dataclass, field


@dataclass
class PolicyResult:
    """Outcome of evaluating policy against a booking + customer request."""
    entitled_actions: list[str] = field(default_factory=list)   # What agent CAN do
    escalation_required: bool = False
    escalation_reasons: list[str] = field(default_factory=list)
    explanation: str = ""                                        # Human-readable summary


# ─── Constants ───────────────────────────────────────────────────────────────
FARE_WAIVER_LIMIT = 1500       # ₹ — agent authority ceiling for fare waivers
DELAY_MEAL_VOUCHER = 500       # ₹ — standard meal voucher amount
REFUND_DAYS = 7                # Business days for refund processing

PRIORITY_TIERS = {"Gold", "Platinum"}   # Tiers with priority rebooking


# ─── Cancellation Policy ─────────────────────────────────────────────────────
def evaluate_cancellation(loyalty_tier: str) -> PolicyResult:
    """
    Airline-caused cancellation:
      - Free rebooking on next available flight within 24h, OR
      - Full refund (customer's choice)
      - Gold & Platinum get priority rebooking (first access to seats)
    """
    actions = ["rebook_free", "refund_full"]
    explanation = (
        f"Your flight was cancelled by the airline. You are entitled to:\n"
        f"  1. Free rebooking on the next available flight within 24 hours, OR\n"
        f"  2. A full refund processed within {REFUND_DAYS} business days "
        f"to your original payment method.\n"
    )
    if loyalty_tier in PRIORITY_TIERS:
        explanation += f"  As a {loyalty_tier} member, you have priority access to seats for rebooking.\n"

    return PolicyResult(entitled_actions=actions, explanation=explanation)


# ─── Delay Policy ────────────────────────────────────────────────────────────
def evaluate_delay(delay_hours: int, loyalty_tier: str) -> PolicyResult:
    """
    Delay compensation tiers:
      < 3h  → ₹500 meal voucher
      > 3h  → meal voucher + lounge access
      > 5h  → meal voucher + hotel accommodation (delayed hours only, NOT full night)
    """
    actions: list[str] = []
    explanation_parts: list[str] = []

    if delay_hours < 3:
        actions.append("issue_meal_voucher")
        explanation_parts.append(f"₹{DELAY_MEAL_VOUCHER} meal voucher")
    elif delay_hours <= 5:
        actions.extend(["issue_meal_voucher", "issue_lounge_access"])
        explanation_parts.append(f"₹{DELAY_MEAL_VOUCHER} meal voucher")
        explanation_parts.append("lounge access")
    else:  # > 5h
        actions.extend(["issue_meal_voucher", "issue_lounge_access", "issue_hotel"])
        explanation_parts.append(f"₹{DELAY_MEAL_VOUCHER} meal voucher")
        explanation_parts.append("lounge access")
        explanation_parts.append(
            "hotel accommodation for the duration of the delay "
            "(covers delayed hours only — not a full night stay)"
        )

    compensation_str = ", ".join(explanation_parts)
    explanation = (
        f"Your flight is delayed by {delay_hours} hour(s). "
        f"As per our policy, you are entitled to: {compensation_str}."
    )

    return PolicyResult(entitled_actions=actions, explanation=explanation)


# ─── Refund Policy ───────────────────────────────────────────────────────────
def evaluate_refund_request(original_payment: bool = True) -> PolicyResult:
    """
    Refunds:
      - Airline-caused cancellations: full refund within 7 business days
      - Only to the original payment method — any other method requires escalation
    """
    if not original_payment:
        return PolicyResult(
            escalation_required=True,
            escalation_reasons=["Refund to non-original payment method is not permitted by agent."],
            explanation="I'm sorry, refunds can only be issued to the original payment method. "
                        "I'll need to escalate this to a supervisor.",
        )

    return PolicyResult(
        entitled_actions=["process_refund"],
        explanation=(
            f"Your refund will be processed in full within {REFUND_DAYS} business days "
            "to your original payment method."
        ),
    )


# ─── Fare Difference Policy ───────────────────────────────────────────────────
def evaluate_fare_waiver(waiver_amount: float) -> PolicyResult:
    """
    Fare difference rule:
      - Customer voluntarily choosing higher-fare flight must pay the difference
      - Agent can waive UP TO ₹1,500
      - Beyond ₹1,500 → must escalate to supervisor
    """
    if waiver_amount <= FARE_WAIVER_LIMIT:
        return PolicyResult(
            entitled_actions=["waive_fare_difference"],
            explanation=f"I can waive the fare difference of ₹{waiver_amount:.0f} for you.",
        )

    return PolicyResult(
        escalation_required=True,
        escalation_reasons=[
            f"Fare waiver of ₹{waiver_amount:.0f} exceeds agent authority limit of ₹{FARE_WAIVER_LIMIT}."
        ],
        explanation=(
            f"The fare difference of ₹{waiver_amount:.0f} exceeds what I'm authorized to waive "
            f"(limit: ₹{FARE_WAIVER_LIMIT}). I'll escalate this to a supervisor who can assist you."
        ),
    )


# ─── Escalation Checks ────────────────────────────────────────────────────────
def check_escalation_triggers(request_details: dict) -> PolicyResult:
    """
    Check for any out-of-policy requests that must be escalated.
    Prohibited actions:
      - Business class / cabin upgrade
      - Full-night hotel (not delay-hours hotel)
      - Compensation beyond policy
      - Exceptions not grounded in rules
    """
    reasons: list[str] = []

    if request_details.get("business_class_upgrade"):
        reasons.append("Business class upgrade is not within agent authority.")

    if request_details.get("full_night_hotel"):
        reasons.append(
            "Full-night hotel stay is not covered — policy only covers delayed hours."
        )

    if request_details.get("extra_compensation"):
        reasons.append("Compensation beyond standard policy requires supervisor approval.")

    if request_details.get("exception_request"):
        reasons.append("Exceptions not grounded in airline policy require escalation.")

    if reasons:
        return PolicyResult(
            escalation_required=True,
            escalation_reasons=reasons,
            explanation=(
                "Some of your requests are beyond what I'm authorized to approve:\n"
                + "\n".join(f"  • {r}" for r in reasons)
                + "\nI'm escalating this to a human supervisor who will contact you shortly."
            ),
        )

    return PolicyResult(escalation_required=False)
