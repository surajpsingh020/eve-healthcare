from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_db
from app.models.booking import Booking
from app.models.test import DiagnosticTest
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.test import TestCreate, TestResponse, TestUpdate

router = APIRouter(prefix="/tests", tags=["Diagnostic Tests"])


@router.get("", response_model=PaginatedResponse[TestResponse], summary="List diagnostic tests")
def list_tests(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total = db.query(DiagnosticTest).count()
    items = (
        db.query(DiagnosticTest)
        .order_by(DiagnosticTest.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{test_id}", response_model=TestResponse, summary="Get a diagnostic test")
def get_test(test_id: int, db: Annotated[Session, Depends(get_db)]):
    test = db.get(DiagnosticTest, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test


@router.post("", response_model=TestResponse, status_code=status.HTTP_201_CREATED, summary="Create a test (admin)")
def create_test(
    body: TestCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    test = DiagnosticTest(name=body.name.strip(), description=body.description)
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.patch("/{test_id}", response_model=TestResponse, summary="Update a test (admin)")
def update_test(
    test_id: int,
    body: TestUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    test = db.get(DiagnosticTest, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    if body.name is not None:
        test.name = body.name.strip()
    if body.description is not None:
        test.description = body.description

    db.commit()
    db.refresh(test)
    return test


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a test (admin)")
def delete_test(
    test_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    test = db.get(DiagnosticTest, test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    has_bookings = db.query(Booking).filter(Booking.test_id == test_id).first()
    if has_bookings:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete test with existing bookings",
        )

    db.delete(test)
    db.commit()
