import datetime
import random
import string
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import engine, Base, get_db, SessionLocal
from app.models import Trip, Seat, Booking
from app.schemas import (
    HealthResponse,
    ReadinessResponse,
    TripResponse,
    SeatMapResponse,
    SeatResponse,
    BookingCreateRequest,
    BookingResponse,
    BookingCancelResponse,
)
from app.logger import logger, StructuredLoggingMiddleware
from app.seed import seed_database


def generate_pnr() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"PNR-{suffix}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed
    logger.info("Initializing database schema...")
    try:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        seed_database(db)
        db.close()
        logger.info("Application startup sequence completed successfully.")
    except Exception as e:
        logger.error(f"Error during application startup: {e}")
    yield
    # Shutdown
    logger.info("Application shutdown sequence initiated.")


app = FastAPI(
    title="Bus Booking Platform - Domain Service",
    description="Production-style trip, seat reservation, and PNR booking API with concurrency protection.",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Observability Probes ---

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Observability"],
    summary="Liveness Probe"
)
def health_check():
    """Returns 200 OK if the application process is running."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.datetime.utcnow(),
        service="bus-booking-api",
        version="1.0.0",
    )


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    tags=["Observability"],
    summary="Readiness Probe"
)
def readiness_check(db: Session = Depends(get_db)):
    """Verifies live database connectivity. Returns 503 if database is unreachable."""
    try:
        db.execute(text("SELECT 1"))
        return ReadinessResponse(
            status="ready",
            database="connected",
            timestamp=datetime.datetime.utcnow(),
        )
    except Exception as exc:
        logger.error(f"Readiness check failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failure: {str(exc)}"
        )


# --- Domain API Endpoints ---

@app.get(
    "/trips",
    response_model=List[TripResponse],
    tags=["Trips"],
    summary="List available bus trips"
)
def list_trips(
    travel_date: Optional[datetime.date] = Query(None, description="Filter by travel date (YYYY-MM-DD)"),
    origin: Optional[str] = Query(None, description="Filter by origin city"),
    destination: Optional[str] = Query(None, description="Filter by destination city"),
    db: Session = Depends(get_db)
):
    query = db.query(Trip)
    if travel_date:
        query = query.filter(Trip.travel_date == travel_date)
    if origin:
        query = query.filter(Trip.origin.ilike(f"%{origin.strip()}%"))
    if destination:
        query = query.filter(Trip.destination.ilike(f"%{destination.strip()}%"))

    trips = query.all()
    results = []
    for t in trips:
        stops_list = [s.strip() for s in t.stops.split(",") if s.strip()]
        results.append(TripResponse(
            id=t.id,
            trip_code=t.trip_code,
            bus_number=t.bus_number,
            route_name=t.route_name,
            origin=t.origin,
            destination=t.destination,
            departure_time=t.departure_time,
            arrival_time=t.arrival_time,
            travel_date=t.travel_date,
            total_seats=t.total_seats,
            stops=stops_list
        ))
    return results


@app.get(
    "/trips/{trip_id}/seats",
    response_model=SeatMapResponse,
    tags=["Trips"],
    summary="Get seat map and availability for a trip"
)
def get_trip_seats(trip_id: int, db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trip ID {trip_id} not found."
        )

    seats = db.query(Seat).filter(Seat.trip_id == trip_id).order_by(Seat.id).all()
    available_count = sum(1 for s in seats if s.status == "AVAILABLE")
    booked_count = sum(1 for s in seats if s.status == "BOOKED")

    return SeatMapResponse(
        trip_id=trip.id,
        trip_code=trip.trip_code,
        total_seats=trip.total_seats,
        available_seats_count=available_count,
        booked_seats_count=booked_count,
        seats=[SeatResponse.model_validate(s) for s in seats]
    )


@app.post(
    "/bookings",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Bookings"],
    summary="Create seat reservation (Concurrency-Safe)"
)
def create_booking(payload: BookingCreateRequest, db: Session = Depends(get_db)):
    """
    Creates a seat reservation with atomic concurrency locking.
    Prevents duplicate seat allocation using row-level locking (SELECT ... FOR UPDATE).
    """
    # 1. Validate trip exists
    trip = db.query(Trip).filter(Trip.id == payload.trip_id).first()
    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trip with ID {payload.trip_id} does not exist."
        )

    # 2. Validate travel date matches trip travel date
    if payload.travel_date != trip.travel_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Requested travel date {payload.travel_date} does not match trip scheduled date {trip.travel_date}."
        )

    # 3. Validate boarding and drop stops
    valid_stops = [s.strip().lower() for s in trip.stops.split(",")]
    if payload.boarding_stop.lower() not in valid_stops:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Boarding stop '{payload.boarding_stop}' is not a valid stop for this trip route. Valid stops: {trip.stops}"
        )
    if payload.drop_stop.lower() not in valid_stops:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Drop stop '{payload.drop_stop}' is not a valid stop for this trip route. Valid stops: {trip.stops}"
        )

    # 4. Atomic seat reservation with row-level lock
    # In SQLite (during simple tests) with_for_update is a no-op; in PostgreSQL it locks the specific row.
    try:
        seat_query = db.query(Seat).filter(
            Seat.trip_id == payload.trip_id,
            Seat.seat_number == payload.seat_number
        )
        # Apply row-level lock where supported
        try:
            seat = seat_query.with_for_update().first()
        except Exception:
            seat = seat_query.first()

        if not seat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Seat '{payload.seat_number}' does not exist on trip {trip.trip_code}."
            )

        if seat.status != "AVAILABLE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Seat '{payload.seat_number}' is already booked or unavailable on trip {trip.trip_code}."
            )

        # 5. Reserve seat & Create Booking
        seat.status = "BOOKED"
        seat.version += 1
        pnr_code = generate_pnr()

        new_booking = Booking(
            pnr=pnr_code,
            trip_id=trip.id,
            seat_number=payload.seat_number,
            passenger_name=payload.passenger_name,
            passenger_email=payload.passenger_email,
            passenger_phone=payload.passenger_phone,
            boarding_stop=payload.boarding_stop,
            drop_stop=payload.drop_stop,
            travel_date=payload.travel_date,
            status="CONFIRMED",
        )

        db.add(new_booking)
        db.commit()
        db.refresh(new_booking)

        logger.info(
            f"Successfully booked seat {payload.seat_number} for {payload.passenger_name}. Generated PNR: {pnr_code}"
        )

        return BookingResponse(
            pnr=new_booking.pnr,
            trip_id=trip.id,
            trip_code=trip.trip_code,
            seat_number=new_booking.seat_number,
            passenger_name=new_booking.passenger_name,
            passenger_email=new_booking.passenger_email,
            passenger_phone=new_booking.passenger_phone,
            boarding_stop=new_booking.boarding_stop,
            drop_stop=new_booking.drop_stop,
            travel_date=new_booking.travel_date,
            status=new_booking.status,
            created_at=new_booking.created_at,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error(f"Booking transaction error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the reservation."
        )


@app.post(
    "/bookings/{pnr}/cancel",
    response_model=BookingCancelResponse,
    tags=["Bookings"],
    summary="Cancel booking and release reserved seat"
)
def cancel_booking(pnr: str, db: Session = Depends(get_db)):
    clean_pnr = pnr.strip().upper()
    booking = db.query(Booking).filter(Booking.pnr == clean_pnr).first()

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with PNR '{clean_pnr}' not found."
        )

    if booking.status == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Booking '{clean_pnr}' is already cancelled."
        )

    # Release seat
    seat = db.query(Seat).filter(
        Seat.trip_id == booking.trip_id,
        Seat.seat_number == booking.seat_number
    ).first()

    if seat:
        seat.status = "AVAILABLE"

    booking.status = "CANCELLED"
    db.commit()

    logger.info(f"Booking {clean_pnr} cancelled. Released seat {booking.seat_number}.")

    return BookingCancelResponse(
        pnr=booking.pnr,
        status="CANCELLED",
        message="Booking cancelled successfully and seat has been released.",
        seat_released=booking.seat_number,
        cancelled_at=datetime.datetime.utcnow(),
    )


@app.get(
    "/bookings/{pnr}",
    response_model=BookingResponse,
    tags=["Bookings"],
    summary="Lookup booking details by PNR"
)
def get_booking(pnr: str, db: Session = Depends(get_db)):
    clean_pnr = pnr.strip().upper()
    booking = db.query(Booking).filter(Booking.pnr == clean_pnr).first()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with PNR '{clean_pnr}' not found."
        )

    trip = db.query(Trip).filter(Trip.id == booking.trip_id).first()
    return BookingResponse(
        pnr=booking.pnr,
        trip_id=booking.trip_id,
        trip_code=trip.trip_code if trip else "N/A",
        seat_number=booking.seat_number,
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        passenger_phone=booking.passenger_phone,
        boarding_stop=booking.boarding_stop,
        drop_stop=booking.drop_stop,
        travel_date=booking.travel_date,
        status=booking.status,
        created_at=booking.created_at,
    )
