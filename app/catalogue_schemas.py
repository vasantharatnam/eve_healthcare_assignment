from decimal import Decimal

from pydantic import BaseModel


class CentreResponse(BaseModel):
    id: int
    name: str
    address: str


class OfferingResponse(BaseModel):
    offering_id: int
    test_id: int
    test_name: str
    description: str | None
    price: Decimal


