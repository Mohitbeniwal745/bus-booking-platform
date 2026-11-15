import datetime
from sqlalchemy.orm import Session
from app.models import Trip, Seat
from app.database import SessionLocal, Base, engine
from app.logger import logger


def generate_seat_numbers(total_seats: int = 30):
    seats = []
    rows = (total_seats // 4) + 1
    letters = ["A", "B", "C", "D"]
    count = 0
    for r in range(1, rows + 1):
        for l in letters:
            if count >= total_seats:
                break
            seats.append(f"{r}{l}")
            count += 1
    return seats


def seed_database(db: Session):
    # Check if trips already exist
    existing_trips = db.query(Trip).count()
    if existing_trips > 0:
        logger.info("Database already seeded. Skipping initial seed.")
        return

    logger.info("Seeding initial trips and seats...")
    today = datetime.date.today()

    sample_trips = [
        {
            "trip_code": "EXP-101",
            "bus_number": "KA-01-F-1234",
            "route_name": "Bangalore to Chennai Express",
            "origin": "Bangalore",
            "destination": "Chennai",
            "departure_time": "06:00",
            "arrival_time": "12:00",
            "travel_date": today,
            "total_seats": 28,
            "stops": "Majestic, Electronic City, Hosur, Vellore, Koyambedu",
        },
        {
            "trip_code": "EXP-202",
            "bus_number": "KA-05-AA-9988",
            "route_name": "Bangalore to Hyderabad Royal",
            "origin": "Bangalore",
            "destination": "Hyderabad",
            "departure_time": "21:00",
            "arrival_time": "06:30",
            "travel_date": today,
            "total_seats": 32,
            "stops": "Silk Board, Hebbal, Anantapur, Kurnool, MGBS Hyderabad",
        },
        {
            "trip_code": "EXP-303",
            "bus_number": "MH-12-Q-4321",
            "route_name": "Mumbai to Pune Intercity",
            "origin": "Mumbai",
            "destination": "Pune",
            "departure_time": "08:00",
            "arrival_time": "11:30",
            "travel_date": today + datetime.timedelta(days=1),
            "total_seats": 24,
            "stops": "Dadar, Chembur, Vashi, Lonavala, Wakad, Swargate Pune",
        },
    ]

    for trip_data in sample_trips:
        trip = Trip(
            trip_code=trip_data["trip_code"],
            bus_number=trip_data["bus_number"],
            route_name=trip_data["route_name"],
            origin=trip_data["origin"],
            destination=trip_data["destination"],
            departure_time=trip_data["departure_time"],
            arrival_time=trip_data["arrival_time"],
            travel_date=trip_data["travel_date"],
            total_seats=trip_data["total_seats"],
            stops=trip_data["stops"],
        )
        db.add(trip)
        db.flush()

        seat_numbers = generate_seat_numbers(trip.total_seats)
        for s_num in seat_numbers:
            seat = Seat(
                trip_id=trip.id,
                seat_number=s_num,
                status="AVAILABLE"
            )
            db.add(seat)

    db.commit()
    logger.info("Database seeding successfully completed.")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
