from typing import Literal

from pydantic import BaseModel, Field

class PaymentWebhookRequest(BaseModel):
     event_id: str = Field(min_length=1 , max_length=255)
     payment_id: int = Field(gt = 0)
     status: Literal["SUCCESS", "FAILED"]

class PaymentWebhookResponse(BaseModel):
     event_id: str
     payment_id: int
     status: str
     already_processed: bool

