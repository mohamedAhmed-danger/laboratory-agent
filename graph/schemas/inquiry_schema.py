from typing import Optional
from pydantic import BaseModel, Field

class InquiryLead(BaseModel):
    phone: Optional[str] = Field(None, description="The user's phone number.")
    services: Optional[str] = Field(None, description="The tests or services mentioned by the user (e.g. 'تحليل السكر', 'صورة دم').")

class InquiryResponse(BaseModel):
    reply: str = Field(description="Clean reply to send to the user listing prices or information about the tests.")
    summary: str = Field(description="An updated English summary of the user's conversation, including the user's inquiry and the reply. This summary is for internal use only.")
    lead: InquiryLead = Field(description="Structured inquiry data.")
