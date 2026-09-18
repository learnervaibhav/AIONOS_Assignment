"""
Seed script — pre-loads all customer profiles and bookings from the assignment brief.

Run with:
    python -m aionos_assignment.db.seed
"""
from aionos_assignment.db.database import SessionLocal, init_db
from aionos_assignment.db.models import Booking, Customer


def seed() -> None:
    init_db()
    db = SessionLocal()

    # Skip seeding if data already exists
    if db.query(Customer).count() > 0:
        print("Database already seeded. Skipping.")
        db.close()
        return

    # ── Customers ──────────────────────────────────────
    priya = Customer(
        name="Priya Nair",
        email="priya.nair@example.com",
        phone="+91-98xxxxxxx1",
        loyalty_tier="Gold",
        booking_ref="SK4821X",
        flight_count=6,
        prior_complaints=1,
    )
    arvind = Customer(
        name="Arvind Kulkarni",
        email="arvind.kulkarni@example.com",
        phone="+91-98xxxxxxx2",
        loyalty_tier="Silver",
        booking_ref="TR1190B",
        flight_count=3,
        prior_complaints=0,
    )
    meher = Customer(
        name="Meher Kaur",
        email="meher.kaur@example.com",
        phone="+91-98xxxxxxx3",
        loyalty_tier="Platinum",
        booking_ref="WL7742",
        flight_count=10,
        prior_complaints=1,
    )

    db.add_all([priya, arvind, meher])
    db.flush()  # Populate IDs before creating bookings

    # ── Bookings ───────────────────────────────────────
    bookings = [
        # Priya — outbound (CANCELLED)
        Booking(
            customer_id=priya.id,
            pnr="SK4821X",
            flight_number="SK-204",
            departure="Delhi",
            arrival="Goa",
            travel_date="Wed 23 Sep 2026",
            scheduled_departure="18:40",
            status="cancelled",
            new_departure=None,
        ),
        # Priya — return (unaffected)
        Booking(
            customer_id=priya.id,
            pnr="SK4821X",
            flight_number="Return",
            departure="Goa",
            arrival="Delhi",
            travel_date="Fri 25 Sep 2026",
            scheduled_departure="16:20",
            status="ok",
            new_departure=None,
        ),
        # Arvind — delayed 4h
        Booking(
            customer_id=arvind.id,
            pnr="TR1190B",
            flight_number="SK-118",
            departure="Mumbai",
            arrival="Bengaluru",
            travel_date="Wed 23 Sep 2026",
            scheduled_departure="07:10",
            status="delayed_4h",
            new_departure="11:10",
        ),
        # Meher — delayed 6h
        Booking(
            customer_id=meher.id,
            pnr="WL7742",
            flight_number="SK-305",
            departure="Delhi",
            arrival="Hyderabad",
            travel_date="Wed 23 Sep 2026",
            scheduled_departure="14:00",
            status="delayed_6h",
            new_departure="20:00",
        ),
    ]

    db.add_all(bookings)
    db.commit()
    db.close()

    print("Database seeded successfully:")
    print("   Customers : Priya Nair (Gold), Arvind Kulkarni (Silver), Meher Kaur (Platinum)")
    print("   Bookings  : 4 flights (1 cancelled, 2 delayed, 1 ok)")


if __name__ == "__main__":
    seed()
