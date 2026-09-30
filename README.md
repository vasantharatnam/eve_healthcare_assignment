
# EVE Diagnostic Booking API

A FastAPI and PostgreSQL backend for browsing diagnostic tests, creating bookings, and simulating payments. Docker Compose runs the API and database; Alembic manages the schema.

## Features

- User signup and login with Argon2 password hashing and JWT authentication
- Public centre and diagnostic test catalogue with centre-specific prices
- Authenticated booking creation and retrieval
- Booking price snapshot at creation
- Mock success and failed payment outcomes
- Idempotent processing of payment webhook event IDs
- Integration tests against a separate PostgreSQL test database

## Requirements

- Docker and Docker Compose

## Start the application

Copy the sample configuration:

```bash
cp .env.example .env
```

Generate **two different secrets**:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the generated values in `.env`:

```dotenv
JWT_SECRET_KEY=first-generated-value
WEBHOOK_SECRET=second-generated-value
```

The `DATABASE_URL` shown in `.env.example` is for connecting from your computer. Inside Docker, Compose supplies an API database URL using `db` as the hostname.

Start the services:

```bash
docker compose up -d --build
```

Apply migrations and insert sample catalogue data:

```bash
docker compose run --rm api python -m alembic upgrade head
docker compose run --rm api python -m app.seed_catalogue
```

Check the API:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Interactive API documentation is available at http://localhost:8000/docs.

To stop the services without deleting database data:

```bash
docker compose down
```

## API flow

### 1. Create an account

```bash
curl -i -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"secure-password-123"}'
```

### 2. Log in

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"secure-password-123"}'
```

Copy `access_token` from the response. Use it as `Authorization: Bearer YOUR_ACCESS_TOKEN` on protected requests.

### 3. Find an offering

```bash
curl http://localhost:8000/centres
curl http://localhost:8000/centres/1/tests
```

Use an actual centre ID from the first response and an `offering_id` from the second. The catalogue endpoints do not require login.

### 4. Create a booking

Choose an appointment time in the future with an explicit timezone:

```bash
curl -i -X POST http://localhost:8000/bookings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "offering_id": 1,
    "appointment_at": "REPLACE_WITH_FUTURE_ISO_8601_TIME"
  }'
```

For example, the timestamp format is `2026-12-15T10:00:00+05:30`; choose a date that is still in the future when you run the request.

The booking starts as `PENDING`. Its `amount` is copied from the offering price at booking time.

List or inspect your bookings:

```bash
curl http://localhost:8000/bookings \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

curl http://localhost:8000/bookings/BOOKING_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Simulate a payment

Replace `BOOKING_ID` with the ID returned by booking creation:

```bash
curl -i -X POST http://localhost:8000/payments/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"booking_id":BOOKING_ID,"outcome":"SUCCESS"}'
```

The API records a `SUCCESS` payment and changes the booking to `CONFIRMED`. To try `FAILED`, create a separate booking and use `"outcome":"FAILED"`; that booking becomes `FAILED`.

This is a **mock** payment. No external provider or real charge is involved. The user supplies the simulated outcome solely for demonstration.

### 6. Simulate a provider webhook

Use the payment ID from step 5 and the `WEBHOOK_SECRET` from `.env`:

```bash
curl -i -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: YOUR_WEBHOOK_SECRET" \
  -d '{"event_id":"evt-demo-001","payment_id":PAYMENT_ID,"status":"SUCCESS"}'
```

Send the **same request** again. The first response has `already_processed: false`; the retry has `already_processed: true`.

An event ID reused with different content, or an outcome contradicting the recorded payment, returns `409`.

## Run tests

The tests use a separate database named `eve_booking_test`. Create it once:

```bash
docker compose up -d db
docker compose exec db psql -U eve_user -d postgres \
  -c "CREATE DATABASE eve_booking_test OWNER eve_user;"
```

Run the tests:

```bash
docker compose build api
docker compose run --rm \
  -e TEST_DATABASE_URL=postgresql+psycopg://eve_user:eve_password@db:5432/eve_booking_test \
  api python -m pytest -q tests
```

The test fixture recreates tables **only in `eve_booking_test`** and rolls back each test's data. Do not set `TEST_DATABASE_URL` to the development database.

## Data model

| Table | Purpose |
|---|---|
| `users` | Accounts and password hashes |
| `centres` | Diagnostic centres |
| `diagnostic_tests` | Test definitions |
| `centre_test_offerings` | Tests offered by each centre and their current prices |
| `bookings` | User appointments, price snapshots, and booking status |
| `payments` | Mock payment attempts and outcomes |
| `webhook_events` | Received provider event IDs and payloads |
| `alembic_version` | Applied migration revision |

## Current behavior and assumptions

- Appointment times must be in the future and include a timezone.
- The API does not manage slot capacity. Multiple users can book the same offering and time.
- A payment can be attempted only while its booking is `PENDING`. Both `CONFIRMED` and `FAILED` bookings are final in this version.
- The mock payment endpoint sets the final outcome immediately. A matching webhook records the notification; it normally does not change that outcome.
- A webhook retry with the same `event_id` and payload is processed once. Different event IDs may be recorded for the same payment if their outcomes agree.
- The webhook uses a shared secret for this exercise. There is no real provider integration, provider signature verification, or external charge.
- Repeating a completed user payment request returns `409`. Client payment idempotency keys and returning the original response on retry are not implemented.

## Possible next improvements

- Model actual appointment slots and capacity.
- Create pending payments and finalize them only after a verified provider result.
- Add client idempotency keys for safe payment-request retries.
- Distinguish failed payment attempts from final booking failure.
- Reconcile conflicting or out-of-order notifications with an authoritative provider status.