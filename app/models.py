import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Date,
    UniqueConstraint,
    Index
)
from sqlalchemy.orm import relationship
from app.database import Base


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    trip_code = Column(String(20), unique=True, nullable=False, index=True)
    bus_number = Column(String(20), nullable=False)
    route_name = Column(String(100), nullable=False)
    origin = Column(String(50), nullable=False)
    destination = Column(String(50), nullable=False)
    departure_time = Column(String(10), nullable=False)  # HH:MM format
    arrival_time = Column(String(10), nullable=False)    # HH:MM format
    travel_date = Column(Date, nullable=False, index=True)
    total_seats = Column(Integer, nullable=False, default=30)
    stops = Column(String(255), nullable=False)  # Comma-separated stops

    seats = relationship("Seat", back_populates="trip", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="trip")


class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_number = Column(String(10), nullable=False)
    # Status: AVAILABLE, BOOKED
    status = Column(String(20), nullable=False, default="AVAILABLE")
    version = Column(Integer, nullable=False, default=1)  # Optimistic concurrency support

    trip = relationship("Trip", back_populates="seats")

    __table_args__ = (
        UniqueConstraint("trip_id", "seat_number", name="uq_trip_seat_number"),
    )


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    pnr = Column(String(12), unique=True, nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    seat_number = Column(String(10), nullable=False)
    passenger_name = Column(String(100), nullable=False)
    passenger_email = Column(String(100), nullable=False)
    passenger_phone = Column(String(20), nullable=False)
    boarding_stop = Column(String(50), nullable=False)
    drop_stop = Column(String(50), nullable=False)
    travel_date = Column(Date, nullable=False)
    # Status: CONFIRMED, CANCELLED
    status = Column(String(20), nullable=False, default="CONFIRMED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    trip = relationship("Trip", back_populates="bookings")

    __table_args__ = (
        Index("ix_booking_trip_seat_status", "trip_id", "seat_number", "status"),
    )
