"""
Seed data for local development.

Usage:
    python -m scripts.seed_data

WARNING: These credentials are for LOCAL DEVELOPMENT ONLY.
Do not use them in production.
"""
import sys
from decimal import Decimal
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User


def seed():
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).first():
            print("Database already has data, skipping seed.")
            return

        # --- Users (LOCAL DEV ONLY credentials) ---
        admin = User(
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            full_name="Admin User",
            is_admin=True,
        )
        regular = User(
            email="user@example.com",
            password_hash=hash_password("user123"),
            full_name="Jane Doe",
            is_admin=False,
        )
        db.add_all([admin, regular])
        db.flush()

        # --- Diagnostic Centres ---
        centres = [
            DiagnosticCentre(name="City Diagnostics", location="MG Road, Bangalore"),
            DiagnosticCentre(name="HealthFirst Labs", location="Sector 18, Noida"),
            DiagnosticCentre(name="MedScan Centre", location="Andheri West, Mumbai"),
        ]
        db.add_all(centres)
        db.flush()

        # --- Diagnostic Tests ---
        tests = [
            DiagnosticTest(name="Complete Blood Count (CBC)", description="Measures different components of blood"),
            DiagnosticTest(name="Lipid Profile", description="Measures cholesterol and triglycerides"),
            DiagnosticTest(name="Thyroid Panel (T3, T4, TSH)", description="Evaluates thyroid function"),
            DiagnosticTest(name="Blood Glucose Fasting", description="Measures fasting blood sugar level"),
            DiagnosticTest(name="Liver Function Test (LFT)", description="Assesses liver health"),
        ]
        db.add_all(tests)
        db.flush()

        # --- Centre-Test offerings with varied pricing ---
        offerings = [
            CentreTest(centre_id=centres[0].id, test_id=tests[0].id, price=Decimal("500.00")),
            CentreTest(centre_id=centres[0].id, test_id=tests[1].id, price=Decimal("800.00")),
            CentreTest(centre_id=centres[0].id, test_id=tests[2].id, price=Decimal("1200.00")),
            CentreTest(centre_id=centres[0].id, test_id=tests[3].id, price=Decimal("200.00")),
            CentreTest(centre_id=centres[1].id, test_id=tests[0].id, price=Decimal("450.00")),
            CentreTest(centre_id=centres[1].id, test_id=tests[1].id, price=Decimal("750.00")),
            CentreTest(centre_id=centres[1].id, test_id=tests[4].id, price=Decimal("900.00")),
            CentreTest(centre_id=centres[2].id, test_id=tests[2].id, price=Decimal("1100.00")),
            CentreTest(centre_id=centres[2].id, test_id=tests[3].id, price=Decimal("180.00")),
            CentreTest(centre_id=centres[2].id, test_id=tests[4].id, price=Decimal("950.00")),
        ]
        db.add_all(offerings)

        db.commit()
        print("Seed data created successfully!")
        print(f"  Admin: admin@example.com / admin123 (LOCAL DEV ONLY)")
        print(f"  User:  user@example.com / user123 (LOCAL DEV ONLY)")
        print(f"  {len(centres)} centres, {len(tests)} tests, {len(offerings)} offerings")

    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
