# EVE Healthcare Diagnostic Booking API

A REST API for booking diagnostic tests and processing simulated payments, built with FastAPI and PostgreSQL.

## Overview

This project implements backend functionality for a healthcare diagnostic booking platform:

- Users sign up, log in, and receive JWT tokens.
- Admins manage diagnostic centres, tests, and centre-specific pricing.
- Authenticated users browse available tests, create bookings, and pay.
- A simulated payment endpoint processes payments without a real gateway.
- A webhook endpoint receives payment status callbacks with idempotent processing.

## Features

- **Authentication** — signup, login, JWT-based auth, admin/user roles
- **Diagnostic Centres** — CRUD with admin authorization
- **Diagnostic Tests** — CRUD with admin authorization
- **Centre-Test Offerings** — manage which tests a centre offers at what price
- **Bookings** — create, list, view, cancel with price snapshot and state machine
- **Simulated Payments** — deterministic payment simulation with booking state sync
- **Webhook Processing** — idempotent webhook handling with DB-level uniqueness
- **Pagination** — paginated collection endpoints
- **Structured Logging** — lightweight event logging without sensitive data

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (sync) |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Testing | Pytest + httpx |
| Containerization | Docker + Docker Compose |

## Project Structure

```
app/
├── core/          # Config, security, logging
├── db/            # SQLAlchemy engine and session
├── models/        # Database models (7 tables)
├── schemas/       # Pydantic request/response schemas
├── api/
│   ├── deps.py    # Dependencies (auth, DB session, webhook secret)
│   └── routes/    # Route handlers
└── services/      # Business logic (booking, payment)

alembic/           # Database migrations
tests/             # Pytest test suite
scripts/           # Seed data script
```

## Getting Started

### With Docker (recommended)

```bash
docker compose up --build
```

This starts PostgreSQL and the API server. The API runs on `http://localhost:8000`.

Migrations run automatically on startup. To seed sample data:

```bash
docker compose exec api python -m scripts.seed_data
```

### Local Development

```bash
# Start PostgreSQL (via Docker or locally)
docker compose up -d postgres

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Seed data
python -m scripts.seed_data

# Start server
uvicorn app.main:app --reload
```

## Environment Variables

See `.env.example` for all variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `TEST_DATABASE_URL` | Test database connection string |
| `JWT_SECRET_KEY` | Secret for JWT signing — **change in production** |
| `JWT_ALGORITHM` | JWT algorithm (default: HS256) |
| `JWT_EXPIRATION_MINUTES` | Token expiry in minutes |
| `WEBHOOK_SECRET` | Secret for validating webhook requests |

## Database Design

### Key Design Decisions

**CentreTest relationship** — A diagnostic test doesn't have a universal price. The `centre_tests` table links centres to tests with a centre-specific price. This is a many-to-many relationship with additional data (the price).

**Booking price snapshot** — When a booking is created, the current price from `centre_tests` is copied into the booking's `amount` field. If the centre later changes the price, existing bookings keep the original amount. This is a deliberate design choice for data integrity.

**Payment uniqueness** — The `payments` table has `UNIQUE(booking_id)` to prevent multiple payments for the same booking, and `UNIQUE(provider_payment_id)` for provider-side deduplication.

**Webhook idempotency** — The `webhook_events` table uses `UNIQUE(provider_event_id)` as the authoritative deduplication mechanism. See [Webhook Idempotency](#webhook-idempotency) for details.

**Money handling** — All monetary values use `NUMERIC(10,2)` in PostgreSQL and `Decimal` in Python. No floating point.

**Timestamps** — All timestamps are timezone-aware (UTC).

### Schema

```
users               1──N  bookings
diagnostic_centres  1──N  bookings
diagnostic_tests    1──N  bookings
diagnostic_centres  1──N  centre_tests  N──1  diagnostic_tests
bookings            1──1  payments
```

### Deletion Rules

- **Centres and tests** referenced by bookings cannot be deleted (returns 409 Conflict). This prevents orphaning historical booking records.
- **Centre-test offerings** can be removed freely — they represent current availability, not historical records.

## Authentication

1. **Signup** — `POST /api/v1/auth/signup` creates a user with bcrypt-hashed password.
2. **Login** — `POST /api/v1/auth/login` returns a JWT token.
3. **Protected routes** — send `Authorization: Bearer <token>` header.
4. **Admin routes** — centre/test management requires `is_admin = true`.

JWT contains only `sub` (user ID) and `exp` (expiration).

## API Endpoints

### Auth
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/signup` | — | Register |
| POST | `/api/v1/auth/login` | — | Login, get JWT |
| GET | `/api/v1/auth/me` | User | Current user info |

### Diagnostic Centres
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/centres` | — | List centres (paginated) |
| GET | `/api/v1/centres/{id}` | — | Centre detail with tests |
| POST | `/api/v1/centres` | Admin | Create centre |
| PATCH | `/api/v1/centres/{id}` | Admin | Update centre |
| DELETE | `/api/v1/centres/{id}` | Admin | Delete centre |
| POST | `/api/v1/centres/{id}/tests` | Admin | Add test offering |
| PATCH | `/api/v1/centres/{id}/tests/{test_id}` | Admin | Update price |
| DELETE | `/api/v1/centres/{id}/tests/{test_id}` | Admin | Remove offering |

### Diagnostic Tests
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/tests` | — | List tests (paginated) |
| GET | `/api/v1/tests/{id}` | — | Test details |
| POST | `/api/v1/tests` | Admin | Create test |
| PATCH | `/api/v1/tests/{id}` | Admin | Update test |
| DELETE | `/api/v1/tests/{id}` | Admin | Delete test |

### Bookings
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/bookings` | User | Create booking |
| GET | `/api/v1/bookings` | User | List own bookings |
| GET | `/api/v1/bookings/{id}` | User | Get own booking |
| POST | `/api/v1/bookings/{id}/cancel` | User | Cancel booking |

### Payments
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/payments` | User | Simulate payment |
| POST | `/api/v1/payments/webhook` | Webhook Secret | Payment callback |

### Health
| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |

### Interactive API Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Booking Flow

```
    ┌─────────┐
    │ PENDING │──── payment SUCCESS ───► CONFIRMED
    └────┬────┘                              │
         │                                   │
         ├── payment FAILED ──► FAILED       ├── cancel ──► CANCELLED
         │                                   │
         └── cancel ──────────► CANCELLED    │
```

**State transitions are explicitly controlled.** Invalid transitions (e.g., FAILED → CONFIRMED) are rejected with 409.

## Payment Flow

```
POST /api/v1/payments
{
    "booking_id": 1,
    "simulate_result": "SUCCESS"   // or "FAILED"
}
```

1. Validates booking exists and belongs to the user.
2. If a payment already exists for this booking, returns the existing payment (deterministic, safe for retries).
3. If booking is PENDING, creates a payment and updates booking status atomically.
4. Payment amount comes from the booking — clients cannot specify it.

## Webhook Idempotency

This is a critical design aspect. Payment providers may deliver the same webhook multiple times.

**How it works:**

1. Webhook arrives with `event_id`, `payment_id`, and `status`.
2. Webhook secret is validated at the API layer.
3. A `webhook_events` row is inserted with `provider_event_id = event_id`.
4. The `UNIQUE(provider_event_id)` constraint is the authoritative guard. If the INSERT fails with an integrity error, the event was already processed → return 200 OK.
5. If the INSERT succeeds, the payment row is locked with `SELECT ... FOR UPDATE`.
6. If the payment is already in a terminal state (SUCCESS/FAILED), the event is recorded but no state change occurs.
7. Otherwise, the payment and booking states are updated in the same transaction.

**Why this matters:**

- The DB constraint handles concurrent duplicate deliveries (not just application-level `if exists` checks).
- `SELECT ... FOR UPDATE` prevents race conditions when updating payment state.
- Terminal state protection prevents contradictory webhooks from corrupting data.

## Running Tests

Tests use a dedicated PostgreSQL test database (`eve_healthcare_test`), not the development database.

```bash
# Make sure PostgreSQL is running
docker compose up -d postgres

# Run tests
pytest tests/ -v
```

The test database is created automatically by the Docker init script. Tables are truncated between tests for isolation.

## Example Requests

### Signup and Login
```bash
# Signup
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com", "password": "secret123", "full_name": "Jane Doe"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com", "password": "secret123"}'
# Response: {"access_token": "eyJ...", "token_type": "bearer"}
```

### Create a Booking
```bash
curl -X POST http://localhost:8000/api/v1/bookings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"centre_id": 1, "test_id": 1, "appointment_at": "2025-12-01T10:00:00Z"}'
```

### Simulate Payment
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id": 1, "simulate_result": "SUCCESS"}'
```

### Send Webhook
```bash
curl -X POST http://localhost:8000/api/v1/payments/webhook \
  -H "X-Webhook-Secret: local-dev-webhook-secret" \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt_123", "event_type": "payment.success", "payment_id": 1, "status": "SUCCESS"}'
```

## Assumptions

- **No real payment gateway** — payments are simulated with a `simulate_result` parameter.
- **No appointment slot inventory** — appointment times are validated to be in the future but there is no slot-capacity management.
- **Price snapshot at booking time** — the price is captured when the booking is created, not when payment occurs.
- **Single payment per booking** — a booking can have at most one payment record.
- **Simple webhook auth** — webhook authentication uses a shared secret header, not cryptographic signing.

## Design Decisions

- **Synchronous SQLAlchemy** — async DB adds complexity without benefit for this scope.
- **No repository pattern** — services query the DB directly. Adding a repository layer would be abstraction for its own sake at this scale.
- **Enum-based state machine** — booking and payment states are Python enums with explicit transition maps. Simple and auditable.
- **Decimal for money** — `NUMERIC(10,2)` in Postgres, `Decimal` in Python. Never float.
- **DELETE protection** — centres/tests with bookings return 409 instead of cascading or soft-deleting. This is the safest default.

## Future Improvements

If this were production:

- Rate limiting on auth endpoints
- Refresh tokens
- Soft-delete for centres/tests
- Real payment provider integration with cryptographic webhook signatures
- Appointment slot capacity management
- Email notifications for booking/payment events
- Request ID tracing for log correlation
- Database connection pooling tuning
- CI/CD pipeline
