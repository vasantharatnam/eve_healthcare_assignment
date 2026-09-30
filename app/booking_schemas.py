from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

class BookingCreate(BaseModel):
    offering_id: int
    appointment_at: datetime


    @field_validator("appointment_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
          if value.tzinfo is None or value.utcoffset() is None:
               raise(
                    "appointment_at must include a timezone, such as Z or +05:30"
               )
          return value




class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    offering_id: int
    appointment_at: datetime
    amount: Decimal
    status: str
    created_at: datetime 

