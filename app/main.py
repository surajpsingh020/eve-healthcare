from fastapi import FastAPI

from app.api.routes import auth, bookings, centres, payments, tests
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="EVE Healthcare Diagnostic Booking API",
    description="REST API for diagnostic test bookings and simulated payments",
    version="1.0.0",
)

API_V1 = "/api/v1"

app.include_router(auth.router, prefix=API_V1)
app.include_router(centres.router, prefix=API_V1)
app.include_router(tests.router, prefix=API_V1)
app.include_router(bookings.router, prefix=API_V1)
app.include_router(payments.router, prefix=API_V1)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
