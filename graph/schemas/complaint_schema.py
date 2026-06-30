from typing import Optional
from pydantic import BaseModel, Field

class ComplaintLead(BaseModel):
    phone: Optional[str] = Field(None, description="The user's phone number.")
    complaint_text: Optional[str] = Field(None, description="Detailed explanation of the user's issue, feedback, or complaint.")

class ComplaintResponse(BaseModel):
    reply: str = Field(description="Clean reply to send to the user")
    summary: str = Field(description="An updated English summary of the user's overall state.")
    lead: ComplaintLead = Field(description="Structured complaint data ONLY.")
    confirmed: bool = Field(description="True if the user confirms sending the complaint.")
    ready_to_save: bool = Field(description="True only if both phone and complaint_text are present.")
