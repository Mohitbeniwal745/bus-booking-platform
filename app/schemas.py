import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, field_validator


# --- Health & Readiness Schemas ---
class HealthResponse(BaseModel):
    status: str = "healthy"
    timestamp: datetime.datetime
    service: str = "bus-booking-api"
    version: str = "1.0.0"


class ReadinessResponse(BaseModel):
    status: str
    database: str
    timestamp: datetime.datetime


# --- Seat Schemas ---
class SeatResponse(BaseModel):
    id: int
    seat_number: str
    status: str

    class Config:
        from_attributes = True


class SeatMapResponse(BaseModel):
    trip_id: int
    trip_code: str
    total_seats: int
    available_seats_count: int
    booked_seats_count: int
    seats: List[SeatResponse]


# --- Trip Schemas ---
class TripResponse(BaseModel):
    id: int
    trip_code: str
    bus_number: str
    route_name: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    travel_date: datetime.date
    total_seats: int
    stops: List[str]

    class Config:
        from_attributes = True


# --- Booking Schemas ---
class BookingCreateRequest(BaseModel):
    trip_id: int = Field(..., description="ID of the trip to book")
    seat_number: str = Field(..., min_length=2, max_length=5, description="Seat identifier (e.g. 1A, 2B)")
    passenger_name: str = Field(..., min_length=2, max_length=100)
    passenger_email: EmailStr = Field(..., description="Valid email address for ticket PNR delivery")
    passenger_phone: str = Field(..., min_length=8, max_length=15, description="Valid passenger contact number")
    boarding_stop: str = Field(..., min_length=2, max_length=50)
    drop_stop: str = Field(..., min_length=2, max_length=50)
    travel_date: datetime.date = Field(..., description="Date of travel (YYYY-MM-DD)")

    @field_validator("seat_number")
    @classmethod
    def normalize_seat(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("boarding_stop", "drop_stop", "passenger_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class BookingResponse(BaseModel):
    pnr: str
    trip_id: int
    trip_code: str
    seat_number: str
    passenger_name: str
    passenger_email: str
    passenger_phone: str
    boarding_stop: str
    drop_stop: str
    travel_date: datetime.date
    status: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class BookingCancelResponse(BaseModel):
    pnr: str
    status: str
    message: str
    seat_released: str
    cancelled_at: datetime.datetime
