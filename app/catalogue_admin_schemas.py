from decimal import Decimal

from pydantic import BaseModel, Field


class CentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1)


class CentreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1)


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class TestUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class OfferingCreate(BaseModel):
    test_id: int = Field(gt=0)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class OfferingUpdate(BaseModel):
    price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    is_active: bool | None = None