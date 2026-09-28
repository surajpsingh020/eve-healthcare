from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user, get_db
from app.models.booking import Booking
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User
from app.schemas.centre import (
    CentreCreate,
    CentreDetailResponse,
    CentreResponse,
    CentreTestCreate,
    CentreTestResponse,
    CentreTestUpdate,
    CentreUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/centres", tags=["Diagnostic Centres"])


@router.get("", response_model=PaginatedResponse[CentreResponse], summary="List diagnostic centres")
def list_centres(
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total = db.query(DiagnosticCentre).count()
    items = (
        db.query(DiagnosticCentre)
        .order_by(DiagnosticCentre.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{centre_id}", response_model=CentreDetailResponse, summary="Get centre details with test offerings")
def get_centre(centre_id: int, db: Annotated[Session, Depends(get_db)]):
    centre = db.get(DiagnosticCentre, centre_id)
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    tests = [
        CentreTestResponse(id=ct.id, test_id=ct.test_id, test_name=ct.test.name, price=ct.price)
        for ct in centre.test_offerings
    ]
    return CentreDetailResponse(
        id=centre.id,
        name=centre.name,
        location=centre.location,
        created_at=centre.created_at,
        updated_at=centre.updated_at,
        tests=tests,
    )


@router.post("", response_model=CentreResponse, status_code=status.HTTP_201_CREATED, summary="Create a centre (admin)")
def create_centre(
    body: CentreCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    centre = DiagnosticCentre(name=body.name.strip(), location=body.location.strip())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.patch("/{centre_id}", response_model=CentreResponse, summary="Update a centre (admin)")
def update_centre(
    centre_id: int,
    body: CentreUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    centre = db.get(DiagnosticCentre, centre_id)
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    if body.name is not None:
        centre.name = body.name.strip()
    if body.location is not None:
        centre.location = body.location.strip()

    db.commit()
    db.refresh(centre)
    return centre


@router.delete("/{centre_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a centre (admin)")
def delete_centre(
    centre_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    centre = db.get(DiagnosticCentre, centre_id)
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    # Prevent deleting centres that have historical bookings
    has_bookings = db.query(Booking).filter(Booking.centre_id == centre_id).first()
    if has_bookings:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete centre with existing bookings",
        )

    # Remove associated centre-test offerings first
    db.query(CentreTest).filter(CentreTest.centre_id == centre_id).delete()
    db.delete(centre)
    db.commit()


# --- Centre-Test offerings ---


@router.post(
    "/{centre_id}/tests",
    response_model=CentreTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a test offering to a centre (admin)",
)
def add_centre_test(
    centre_id: int,
    body: CentreTestCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    centre = db.get(DiagnosticCentre, centre_id)
    if not centre:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")

    test = db.get(DiagnosticTest, body.test_id)
    if not test:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")

    existing = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == body.test_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This test is already offered by this centre",
        )

    ct = CentreTest(centre_id=centre_id, test_id=body.test_id, price=body.price)
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return CentreTestResponse(id=ct.id, test_id=ct.test_id, test_name=test.name, price=ct.price)


@router.patch(
    "/{centre_id}/tests/{test_id}",
    response_model=CentreTestResponse,
    summary="Update test offering price (admin)",
)
def update_centre_test(
    centre_id: int,
    test_id: int,
    body: CentreTestUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    ct = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id)
        .first()
    )
    if not ct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre-test offering not found")

    ct.price = body.price
    db.commit()
    db.refresh(ct)
    return CentreTestResponse(id=ct.id, test_id=ct.test_id, test_name=ct.test.name, price=ct.price)


@router.delete(
    "/{centre_id}/tests/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a test offering from a centre (admin)",
)
def delete_centre_test(
    centre_id: int,
    test_id: int,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_admin_user)],
):
    ct = (
        db.query(CentreTest)
        .filter(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id)
        .first()
    )
    if not ct:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre-test offering not found")

    db.delete(ct)
    db.commit()
