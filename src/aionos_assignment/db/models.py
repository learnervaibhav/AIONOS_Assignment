"""
SQLAlchemy ORM models for the Airline Disruption Resolution Agent.

Tables:
  - customers     : customer profiles & loyalty tiers
  - bookings      : flight bookings with normalized departure/arrival
  - sessions      : conversation session tracking
  - conversations : full message history per session
  - actions_log   : record of all agent actions taken
"""
import json
from datetime import datetime

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────
# Customer
# ─────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    email = Column(String(200))
    phone = Column(String(30))
    loyalty_tier = Column(String(20), nullable=False)   # Gold / Silver / Platinum
    booking_ref = Column(String(20))                    # Primary booking reference (PNR)
    flight_count = Column(Integer, default=0)           # Flights in last 12 months
    prior_complaints = Column(Integer, default=0)       # Prior complaint count

    bookings = relationship("Booking", back_populates="customer")
    sessions = relationship("Session", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.name} [{self.loyalty_tier}]>"


# ─────────────────────────────────────────────
# Booking
# ─────────────────────────────────────────────
class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    pnr = Column(String(20), nullable=False, index=True)
    flight_number = Column(String(20))                  # e.g. SK-204
    departure = Column(String(100))                     # Departure city (normalized)
    arrival = Column(String(100))                       # Arrival city (normalized)
    travel_date = Column(String(50))                    # e.g. Wed 23 Sep 2026
    scheduled_departure = Column(String(10))            # e.g. 18:40
    status = Column(String(50), default="ok")           # ok / cancelled / delayed_Xh
    new_departure = Column(String(10))                  # Revised time if delayed

    customer = relationship("Customer", back_populates="bookings")

    def get_route(self) -> str:
        """Merge departure + arrival into a display string e.g. 'Delhi → Goa'."""
        return f"{self.departure} → {self.arrival}"

    def get_delay_hours(self) -> int:
        """Parse delay hours from status string e.g. 'delayed_4h' → 4."""
        if self.status.startswith("delayed_"):
            try:
                return int(self.status.split("_")[1].replace("h", ""))
            except (IndexError, ValueError):
                return 0
        return 0

    def __repr__(self) -> str:
        return f"<Booking {self.pnr} | {self.get_route()} | {self.status}>"


# ─────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────
class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    created_at = Column(String(30), default=lambda: datetime.utcnow().isoformat())
    last_active_at = Column(String(30), default=lambda: datetime.utcnow().isoformat())
    is_escalated = Column(Integer, default=0)   # 0 / 1
    is_closed = Column(Integer, default=0)      # 0 / 1

    customer = relationship("Customer", back_populates="sessions")
    conversations = relationship("Conversation", back_populates="session")
    actions = relationship("ActionLog", back_populates="session")

    def __repr__(self) -> str:
        return f"<Session {self.session_id} | escalated={bool(self.is_escalated)}>"


# ─────────────────────────────────────────────
# Conversation (per-turn messages)
# ─────────────────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    turn_index = Column(Integer, default=0)     # Sequential turn within session
    role = Column(String(20), nullable=False)   # user / assistant
    message = Column(Text, nullable=False)
    intent = Column(String(50))                 # Detected intent (nullable)
    timestamp = Column(String(30), default=lambda: datetime.utcnow().isoformat())

    session = relationship("Session", back_populates="conversations")

    def __repr__(self) -> str:
        return f"<Conversation [{self.role}] turn={self.turn_index}>"


# ─────────────────────────────────────────────
# Action Log
# ─────────────────────────────────────────────
class ActionLog(Base):
    __tablename__ = "actions_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.session_id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    action_type = Column(String(50))        # rebook / refund / voucher / lounge / hotel / escalate
    details = Column(Text)                  # JSON string with action specifics
    timestamp = Column(String(30), default=lambda: datetime.utcnow().isoformat())
    status = Column(String(30), default="completed")  # pending / completed / escalated

    session = relationship("Session", back_populates="actions")

    def get_details(self) -> dict:
        """Deserialize JSON details string."""
        try:
            return json.loads(self.details) if self.details else {}
        except json.JSONDecodeError:
            return {}

    def __repr__(self) -> str:
        return f"<ActionLog {self.action_type} | {self.status}>"
