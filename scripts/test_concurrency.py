import concurrent.futures
import datetime
import requests
import sys

BASE_URL = "http://localhost:8000"
if len(sys.argv) > 1:
    BASE_URL = sys.argv[1]

TRIP_ID = 2  # Bangalore to Hyderabad
TARGET_SEAT = "3A"
TODAY = datetime.date.today().isoformat()

PASSENGERS = [
    {"name": "Alice Concurrent", "email": "alice@example.com", "phone": "+919999000001"},
    {"name": "Bob Concurrent", "email": "bob@example.com", "phone": "+919999000002"},
    {"name": "Charlie Concurrent", "email": "charlie@example.com", "phone": "+919999000003"},
    {"name": "Dave Concurrent", "email": "dave@example.com", "phone": "+919999000004"},
]


def send_booking(passenger):
    payload = {
        "trip_id": TRIP_ID,
        "seat_number": TARGET_SEAT,
        "passenger_name": passenger["name"],
        "passenger_email": passenger["email"],
        "passenger_phone": passenger["phone"],
        "boarding_stop": "Silk Board",
        "drop_stop": "MGBS Hyderabad",
        "travel_date": TODAY,
    }
    try:
        response = requests.post(f"{BASE_URL}/bookings", json=payload, timeout=5)
        return response.status_code, response.json()
    except Exception as e:
        return 500, {"error": str(e)}


def run_concurrency_test():
    print(f"\n==================================================")
    print(f"  CONCURRENCY ACCEPTANCE TEST")
    print(f"  Target: {BASE_URL}/bookings")
    print(f"  Trip ID: {TRIP_ID} | Target Seat: {TARGET_SEAT}")
    print(f"  Simultaneous Threads: {len(PASSENGERS)}")
    print(f"==================================================\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(PASSENGERS)) as executor:
        futures = [executor.submit(send_booking, p) for p in PASSENGERS]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    success_count = 0
    conflict_count = 0
    pnrs = []

    print("[Results per Request]")
    for code, body in results:
        if code == 201:
            success_count += 1
            pnrs.append(body.get("pnr"))
            print(f"  -> HTTP 201 SUCCESS: Booked with PNR {body.get('pnr')} for {body.get('passenger_name')}")
        elif code == 409:
            conflict_count += 1
            print(f"  -> HTTP 409 CONFLICT: Blocked safely with detail: {body.get('detail')}")
        else:
            print(f"  -> HTTP {code}: {body}")

    print("\n--------------------------------------------------")
    print(f"Total Successful Reservations : {success_count} (Expected: 1)")
    print(f"Total Safely Rejected Conflicts: {conflict_count} (Expected: {len(PASSENGERS) - 1})")
    print(f"Generated Unique PNRs          : {pnrs}")
    print("--------------------------------------------------")

    if success_count == 1 and conflict_count == (len(PASSENGERS) - 1):
        print("\n>>> ACCEPTANCE TEST PASSED: Zero duplicate bookings. Safe concurrency isolation verified! <<<\n")
        return 0
    else:
        print("\n>>> ACCEPTANCE TEST FAILED: Concurrency violation detected! <<<\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_concurrency_test())
