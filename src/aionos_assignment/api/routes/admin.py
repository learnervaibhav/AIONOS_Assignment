"""
Admin routes -- view customers and all actions (read-only).

GET /customers  -- list all seeded customers
GET /actions    -- list all actions taken across all sessions
"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from aionos_assignment.api.schemas import ActionEntry, BookingResponse, CustomerResponse
from aionos_assignment.db.database import get_db
from aionos_assignment.db.models import ActionLog, Booking, Customer

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/customers", response_model=list[CustomerResponse])
def list_customers(db: DBSession = Depends(get_db)):
    """List all customers in the database."""
    customers = db.query(Customer).all()
    return [
        CustomerResponse(
            id=c.id,
            name=c.name,
            email=c.email or "",
            loyalty_tier=c.loyalty_tier,
            booking_ref=c.booking_ref or "",
            flight_count=c.flight_count,
            prior_complaints=c.prior_complaints,
        )
        for c in customers
    ]


@router.get("/customers/{customer_id}/bookings", response_model=list[BookingResponse])
def list_customer_bookings(customer_id: int, db: DBSession = Depends(get_db)):
    """List all bookings for a specific customer."""
    bookings = db.query(Booking).filter(Booking.customer_id == customer_id).all()
    return [
        BookingResponse(
            id=b.id,
            pnr=b.pnr,
            flight_number=b.flight_number or "",
            departure=b.departure,
            arrival=b.arrival,
            route=b.get_route(),
            travel_date=b.travel_date or "",
            scheduled_departure=b.scheduled_departure or "",
            status=b.status,
            new_departure=b.new_departure,
        )
        for b in bookings
    ]


@router.get("/actions", response_model=list[ActionEntry])
def list_all_actions(db: DBSession = Depends(get_db)):
    """List all agent actions taken across all sessions."""
    actions = db.query(ActionLog).order_by(ActionLog.id.desc()).limit(100).all()
    return [
        ActionEntry(
            action_type=a.action_type,
            details=a.get_details(),
            status=a.status,
            timestamp=a.timestamp,
        )
        for a in actions
    ]
