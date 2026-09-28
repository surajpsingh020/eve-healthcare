from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=500)


class CentreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = Field(default=None, min_length=1, max_length=500)


class CentreTestCreate(BaseModel):
    test_id: int
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class CentreTestUpdate(BaseModel):
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class CentreTestResponse(BaseModel):
    id: int
    test_id: int
    test_name: str
    price: Decimal

    model_config = {"from_attributes": True}


class CentreResponse(BaseModel):
    id: int
    name: str
    location: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CentreDetailResponse(CentreResponse):
    tests: list[CentreTestResponse] = []
