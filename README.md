# EVE Diagnostic Booking API

A FastAPI and PostgreSQL backend for diagnostic test bookings and simulated payments.

## Features

- Signup and login with Argon2 password hashing and JWT authentication
- Public APIs to browse diagnostic centres, tests, and centre-specific prices
- Admin-only APIs to create and update centres, tests, and offerings
- Authenticated booking creation and retrieval
- Booking price snapshot at creation time
- Mock successful and failed payments
- Idempotent payment webhook processing using unique event IDs
- PostgreSQL migrations with Alembic
- Integration tests using a separate test database

## Requirements

- Docker
- Docker Compose

## Local setup

Copy the example configuration:

```bash
cp .env.example .env
```

Generate two different secrets:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set them in `.env`:

```dotenv
JWT_SECRET_KEY=first-generated-value
WEBHOOK_SECRET=second-generated-value
```

Keep `.env` private. Docker Compose supplies the API container's `DATABASE_URL` using `db` as the PostgreSQL hostname.

Start the application:

```bash
docker compose up -d --build
```

Apply the database migrations:

```bash
docker compose run --rm api python -m alembic upgrade head
```

Insert sample centres, tests, and offerings:

```bash
docker compose run --rm api python -m app.seed_catalogue
```

Check that the API and database are reachable:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Interactive API documentation: http://localhost:8000/docs

To stop the services without removing the PostgreSQL volume:

```bash
docker compose down
```

## Create an admin account

All accounts created through signup are **non-admin**. There is no public API for a user to grant themselves admin access.

First, create an account:

```bash
curl -i -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"secure-password-123"}'
```

Promote that existing account from the local database container:

```bash
docker compose exec db psql -U eve_user -d eve_booking \
  -c "UPDATE users SET is_admin = TRUE WHERE email = 'admin@example.com';"
```

The command must report `UPDATE 1`. `UPDATE 0` means that no account matches the email; check the signup response and the email used in the SQL command.

You can verify the account:

```bash
docker compose exec db psql -U eve_user -d eve_booking \
  -c "SELECT id, email, is_admin FROM users WHERE email = 'admin@example.com';"
```

Log in as the admin to obtain a JWT for catalogue management requests. Access to the Docker host and database is required to perform the promotion.

## API endpoints

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/health` | Public | Check API and database availability |
| `POST` | `/auth/signup` | Public | Create a user |
| `POST` | `/auth/login` | Public | Obtain a JWT |
| `GET` | `/auth/me` | User | Get the authenticated user |
| `GET` | `/centres` | Public | List centres |
| `GET` | `/centres/{centre_id}/tests` | Public | List active offerings and prices |
| `POST` | `/centres` | Admin | Create a centre |
| `PATCH` | `/centres/{centre_id}` | Admin | Update a centre |
| `POST` | `/tests` | Admin | Create a diagnostic test |
| `PATCH` | `/tests/{test_id}` | Admin | Update a diagnostic test |
| `POST` | `/centres/{centre_id}/tests` | Admin | Add a test offering to a centre |
| `PATCH` | `/offerings/{offering_id}` | Admin | Change offering price or active state |
| `POST` | `/bookings` | User | Create a booking |
| `GET` | `/bookings` | User | List own bookings |
| `GET` | `/bookings/{booking_id}` | User | View own booking |
| `POST` | `/payments/` | User | Simulate a payment for own booking |
| `POST` | `/payments/webhook/` | Webhook secret | Process a simulated provider notification |

“User” endpoints require `Authorization: Bearer <JWT>`. “Admin” endpoints require the same header with a token belonging to an admin account. The webhook uses `X-Webhook-Secret` instead of a user JWT.

## Example flow

### 1. Sign up and log in

```bash
curl -i -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"secure-password-123"}'
```

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"secure-password-123"}'
```

Copy `access_token` from the login response and use it as `YOUR_ACCESS_TOKEN` below.

### 2. Find a test offering

```bash
curl http://localhost:8000/centres
curl http://localhost:8000/centres/1/tests
```

Replace `1` with a centre ID from the first response. The second response contains an `offering_id` to use when booking.

### 3. Create a booking

Choose a future appointment time and include its timezone:

```bash
curl -i -X POST http://localhost:8000/bookings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "offering_id": 1,
    "appointment_at": "REPLACE_WITH_FUTURE_ISO_8601_TIME"
  }'
```

A valid timestamp has a format such as `2026-12-15T10:00:00+05:30`, provided that date is still in the future when the request is sent.

The booking starts as `PENDING`. It stores a copy of the offering price, so a later catalogue price change does not alter the booking amount.

View your bookings:

```bash
curl http://localhost:8000/bookings \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

curl http://localhost:8000/bookings/BOOKING_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

A user cannot view another user's booking.

### 4. Simulate a payment

Use the ID of a pending booking:

```bash
curl -i -X POST http://localhost:8000/payments/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{"booking_id":BOOKING_ID,"outcome":"SUCCESS"}'
```

`SUCCESS` changes the booking to `CONFIRMED`; `FAILED` changes it to `FAILED`. To test both outcomes, create separate bookings. A second payment request for a final booking returns `409`.

This endpoint does **not** contact a real payment provider. The request supplies the outcome only to simulate payment processing.

### 5. Simulate a payment webhook

Use the payment ID from the previous step and the secret in `.env`:

```bash
curl -i -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: YOUR_WEBHOOK_SECRET" \
  -d '{"event_id":"evt-demo-001","payment_id":PAYMENT_ID,"status":"SUCCESS"}'
```

Send the same request a second time. The first response has `already_processed: false`; the retry has `already_processed: true`.

Reusing the same event ID with different content returns `409`. A new event that contradicts the recorded payment outcome also returns `409`. The event record and any payment/booking status updates are committed together.

### 6. Manage catalogue data as an admin

Use the JWT obtained by logging in as the admin account.

Create a centre:

```bash
curl -i -X POST http://localhost:8000/centres \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -d '{"name":"EVE Whitefield","address":"Whitefield, Bengaluru"}'
```

Create a diagnostic test:

```bash
curl -i -X POST http://localhost:8000/tests \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -d '{"name":"Vitamin D","description":"Vitamin D test"}'
```

Offer that test at the centre:

```bash
curl -i -X POST http://localhost:8000/centres/CENTRE_ID/tests \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ADMIN_ACCESS_TOKEN" \
  -d '{"test_id":TEST_ID,"price":"700.00"}'
```

A normal logged-in user receives `403` for these management operations; a request without a JWT receives `401`.

## Run the tests

The test suite uses a separate database called `eve_booking_test`. Create it once:

```bash
docker compose up -d db
docker compose exec db psql -U eve_user -d postgres \
  -c "CREATE DATABASE eve_booking_test OWNER eve_user;"
```

If it already exists, do not recreate it. Build the current API image and run pytest:

```bash
docker compose build api
docker compose run --rm \
  -e TEST_DATABASE_URL=postgresql+psycopg://eve_user:eve_password@db:5432/eve_booking_test \
  api python -m pytest -q tests
```

The test fixture recreates tables only in `eve_booking_test`. Never point `TEST_DATABASE_URL` at `eve_booking`.

## Database design

| Table | Purpose |
|---|---|
| `users` | User accounts, password hashes, and admin flag |
| `centres` | Diagnostic centre name and address/location |
| `diagnostic_tests` | Definitions of diagnostic tests |
| `centre_test_offerings` | A centre's available tests, active state, and current prices |
| `bookings` | User, offering, appointment, saved amount, and booking status |
| `payments` | Mock payment attempts and outcomes |
| `webhook_events` | Received provider event IDs and payloads |
| `alembic_version` | Applied database migration revision |

An offering links one centre to one test. The database prevents adding the same test to the same centre twice.

## Assumptions and current limitations

- Appointment timestamps must be in the future and include a timezone.
- An appointment time does not reserve exclusive capacity. Multiple users can book the same offering and time.
- Bookings start `PENDING`. In this version, payment changes them to `CONFIRMED` or `FAILED`; both are final. Cancellation is not implemented.
- The mock payment endpoint sets the final outcome immediately. A matching webhook normally records the notification without changing that outcome.
- Webhook idempotency is based on a unique `event_id`. Different event IDs with the same outcome can be recorded for one payment without repeating its state transition.
- The webhook uses a shared secret for the simulation. It does not verify a real provider signature.
- Repeating a completed user payment request returns `409`; client payment idempotency keys that return the original result are not implemented.

## Improvements with more time

- Add an explicit slot and capacity model with transactional reservations.
- Create `PENDING` payment attempts and finalize them only after a verified provider result.
- Add client idempotency keys and reuse them when making external provider requests.
- Allow a new payment attempt after a failed attempt when product rules permit it.
- Reconcile conflicting or out-of-order provider notifications against authoritative provider state.
- Add concurrent request tests for booking payment locks and webhook delivery.