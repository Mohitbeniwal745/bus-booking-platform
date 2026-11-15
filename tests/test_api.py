import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.seed import seed_database

# In-memory SQLite for high-speed deterministic tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    seed_database(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "bus-booking-api"


def test_readiness_check():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_list_trips():
    response = client.get("/trips")
    assert response.status_code == 200
    trips = response.json()
    assert len(trips) >= 3
    assert trips[0]["trip_code"] == "EXP-101"
    assert "Majestic" in trips[0]["stops"]


def test_get_trip_seats():
    response = client.get("/trips/1/seats")
    assert response.status_code == 200
    data = response.json()
    assert data["trip_id"] == 1
    assert data["total_seats"] == 28
    assert data["available_seats_count"] == 28
    assert data["booked_seats_count"] == 0
    assert len(data["seats"]) == 28


def test_successful_booking():
    today = datetime.date.today().isoformat()
    payload = {
        "trip_id": 1,
        "seat_number": "1A",
        "passenger_name": "John Doe",
        "passenger_email": "john.doe@example.com",
        "passenger_phone": "+919876543210",
        "boarding_stop": "Majestic",
        "drop_stop": "Koyambedu",
        "travel_date": today,
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["seat_number"] == "1A"
    assert data["status"] == "CONFIRMED"
    assert data["pnr"].startswith("PNR-")


def test_prevent_duplicate_seat_booking():
    """Acceptance test: Conflicting seat booking must fail safely and not duplicate PNR."""
    today = datetime.date.today().isoformat()
    payload = {
        "trip_id": 1,
        "seat_number": "1A",  # Already booked in previous test
        "passenger_name": "Jane Smith",
        "passenger_email": "jane.smith@example.com",
        "passenger_phone": "+919123456789",
        "boarding_stop": "Hosur",
        "drop_stop": "Vellore",
        "travel_date": today,
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 409
    assert "already booked or unavailable" in response.json()["detail"]


def test_invalid_stop_validation():
    today = datetime.date.today().isoformat()
    payload = {
        "trip_id": 1,
        "seat_number": "1B",
        "passenger_name": "Alice Wonderland",
        "passenger_email": "alice@example.com",
        "passenger_phone": "+919988776655",
        "boarding_stop": "NonExistentStop",
        "drop_stop": "Koyambedu",
        "travel_date": today,
    }
    response = client.post("/bookings", json=payload)
    assert response.status_code == 400
    assert "not a valid stop" in response.json()["detail"]


def test_cancel_booking():
    # 1. Book seat 2A
    today = datetime.date.today().isoformat()
    payload = {
        "trip_id": 1,
        "seat_number": "2A",
        "passenger_name": "Robert Brown",
        "passenger_email": "robert@example.com",
        "passenger_phone": "+919555444333",
        "boarding_stop": "Majestic",
        "drop_stop": "Koyambedu",
        "travel_date": today,
    }
    book_res = client.post("/bookings", json=payload)
    assert book_res.status_code == 201
    pnr = book_res.json()["pnr"]

    # 2. Cancel booking
    cancel_res = client.post(f"/bookings/{pnr}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"
    assert cancel_res.json()["seat_released"] == "2A"

    # 3. Verify seat is released and can be booked again
    rebook_res = client.post("/bookings", json=payload)
    assert rebook_res.status_code == 201
    assert rebook_res.json()["seat_number"] == "2A"
