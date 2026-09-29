# EVE Healthcare Diagnostic Booking API

This is the backend implementation for the EVE Healthcare SDE assignment, focusing on diagnostic test bookings, pricing, and simulated payments with webhook handling.

## Tech Stack

- **Python / FastAPI**: Core API framework
- **PostgreSQL**: Relational database
- **SQLAlchemy 2.x**: Sync ORM
- **Alembic**: Database migrations
- **Pydantic v2**: Request/response validation
- **JWT (python-jose) + passlib (bcrypt)**: Authentication
- **Pytest**: Test suite
- **Docker / Docker Compose**: Containerization and local environment

## Features

- User signup/login
- JWT authentication
- User/admin authorization
- Diagnostic centre management
- Diagnostic test management
- Centre-specific test pricing
- Booking creation
- Booking ownership
- Price snapshot at booking creation
- Booking cancellation/state transitions
- Simulated SUCCESS/FAILED payments
- Payment ownership protection
- Webhook processing
- Webhook secret validation
- Idempotent webhook handling
- Pagination for lists (centres/tests)
- Swagger/OpenAPI documentation

## Project Structure

```
.
├── alembic/           # Database migrations
├── app/               # Core application
│   ├── api/           # API routes and dependencies
│   ├── core/          # Config, security, logging
│   ├── db/            # Database session and base models
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic validation schemas
│   └── services/      # Business logic (booking, payments)
├── scripts/           # DB initialization and seed data scripts
├── tests/             # Pytest automated tests
├── docker-compose.yml # Docker services definition
├── Dockerfile         # API container image
└── requirements.txt   # Python dependencies
```

## Prerequisites

- **Docker**
- **Docker Compose**

*(If running locally without Docker: Python 3.12+ and a local PostgreSQL instance).*

## Environment Setup

1. Clone this repository.
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. The `.env` file is intentionally ignored by Git to prevent secrets from leaking.
4. Note that `.env.example` contains safe development placeholders (e.g., `change-me-in-production`). Never place real production secrets in the repository.

## Running with Docker — Recommended

To spin up the PostgreSQL database and the FastAPI application from a clean clone:

```bash
docker compose up --build -d
```

During container startup, Alembic migrations execute automatically to apply the latest database schema before the API starts accepting traffic.

- **Swagger UI:** `http://localhost:8000/docs`
- **Health Check:** `http://localhost:8000/health`

## Seed Data

To populate the database with initial diagnostic centres, tests, and users (run this while the API container is running):

```bash
docker compose exec api python -m scripts.seed_data
```

This creates the following credentials (**LOCAL DEVELOPMENT ONLY**):
- **Admin**: `admin@example.com` / `admin123`
- **User**: `user@example.com` / `user123`

The script will safely skip seeding if it detects existing data in the `users` table.

## Running Tests

Tests use a dedicated PostgreSQL test database (`eve_healthcare_test`). This is automatically created by the init script in Docker.

To run the complete test suite:

```bash
docker compose exec api pytest tests/ -v
```
*(Or run `pytest tests/ -v` locally using a virtual environment if `.env` is configured correctly).*

**At final verification, 53 tests passed.**

## API Documentation

Interactive Swagger/OpenAPI documentation is available at:
[http://localhost:8000/docs](http://localhost:8000/docs)

**Authentication Workflow:**
1. Call `POST /api/v1/auth/login` with your email and password.
2. Copy the resulting `access_token`.
3. Click the global "Authorize 🔒" button in Swagger.
4. Paste the raw JWT token (do not prepend "Bearer ", Swagger handles this automatically).
5. Swagger will now send `Authorization: Bearer <token>` on all protected requests.

## Core API Flow

1. **Signup/Login** (`/api/v1/auth/signup` -> `/api/v1/auth/login`)
2. **Browse centres/tests** (`/api/v1/centres`, `/api/v1/tests`)
3. **Create booking** (`POST /api/v1/bookings`) - Booking is created as PENDING.
4. **Simulate payment** (`POST /api/v1/payments`) - Simulates SUCCESS or FAILED.
5. **Booking updates** - Booking immediately becomes CONFIRMED or FAILED.
6. **Webhook** (`POST /api/v1/payments/webhook`) - Simulates payment provider callbacks. Processing is idempotent and protected against contradictory state updates.

## Key Assumptions & Design Decisions

1. **Authentication**
   - JWT Bearer authentication is used.
   - Admin-only catalogue-management operations are protected separately from normal-user operations.

2. **Booking ownership**
   - Users may only access, cancel, or pay for their own bookings. The API strictly enforces `booking.user_id == current_user.id`.

3. **Centre-specific pricing**
   - A diagnostic test can have different prices at different centres.
   - The centre/test junction table (`CentreTest`) stores the applicable price.

4. **Price snapshot**
   - The booking record stores the price precisely at booking time.
   - Later catalogue price changes do not alter historical booking amounts.

5. **Money**
   - Monetary values use `Decimal` in Python and PostgreSQL `NUMERIC(10, 2)` rather than floating point to prevent precision loss.

6. **Appointment timestamps**
   - Naive appointment datetimes (e.g. `2026-09-30T10:00:00`) are safely treated as UTC by the API logic.
   - Past appointments are strictly rejected with a `400 Bad Request`.

7. **Payment simulation**
   - No external payment provider is integrated.
   - The `POST /api/v1/payments` API intentionally simulates SUCCESS or FAILED outcomes directly.
   - A booking has at most one payment record under the current design.

8. **Booking/payment states**
   - States are explicitly governed by Python enums.
   - Terminal state protections exist to prevent invalid transitions (e.g., a `FAILED` booking cannot become `CONFIRMED`, a `CANCELLED` booking cannot be paid).

9. **Webhook idempotency**
   - `provider_event_id` uniqueness is strictly enforced at the database level (`UNIQUE` constraint).
   - Repeated webhook delivery catches the resulting `IntegrityError` and safely ignores the duplicate without double-processing.
   - Terminal payment states (SUCCESS/FAILED) are protected from contradictory webhook updates, skipping logic execution if a payment is already finalized.

10. **Webhook authentication**
    - A shared webhook secret (`X-Webhook-Secret`) is used for this assignment simulation instead of complex cryptographic signatures.

11. **Database**
    - PostgreSQL is the intended database.
    - Alembic handles schema migrations robustly.

12. **Deletion/history**
    - Attempting to delete a diagnostic centre or test that is already referenced by historical bookings returns a `409 Conflict`. We avoid hard-deletions or cascades that would orphan booking history.
    - Centre-test offerings (the pricing relationships) can be deleted, as they represent current availability rather than historical records.

13. **Scope**
    - This is intentionally a compact assignment implementation prioritizing code quality, correctness, tests, and clean architecture over over-engineering. No caching layers (Redis), event buses (Kafka), or microservices are included.

## Error Handling / Important HTTP Responses

The API uses standardized HTTP status codes:
- **400** — Invalid business input (e.g., past appointments, test not offered at centre)
- **401** — Missing, invalid, or expired authentication (or incorrect webhook secret)
- **403** — Insufficient permission (e.g., non-admin) / resource ownership violation
- **404** — Resource not found
- **409** — Invalid state transition (e.g., cancelling a confirmed booking) or referential conflict
- **422** — Request validation failure (Pydantic schema errors)

## Security Notes

- Passwords are cryptographically hashed using `bcrypt` (via `passlib`).
- API authentication is secured by JSON Web Tokens (JWT).
- Admin routes strictly enforce `is_admin = True`.
- Booking and payment endpoints strictly validate data ownership (`user_id`).
- Secrets and configurations are loaded from `.env` which is ignored by version control.
- The webhook endpoint intercepts requests to validate the `X-Webhook-Secret` before touching business logic.
