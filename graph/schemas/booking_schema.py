from typing import Optional
from pydantic import BaseModel, Field

class BookingLead(BaseModel):
    name: Optional[str] = Field(None, description="The user's explicit name.")
    phone: Optional[str] = Field(None, description="The user's phone number.")
    details: Optional[str] = Field(None, description="The details of the booking (e.g., required tests or services like 'تحليل دم', 'صورة دم كاملة'). "
          "CRITICAL: If the user's phone number, name, or required test is already mentioned in the 'Summary' history, EXTRACT it automatically into the lead. DO NOT ask the user for information they already provided. "
          "EXTRACT it immediately into this field. Do NOT ask for the reason again.")
    date: Optional[str] = Field(
        None, 
        description="The resolved absolute date and time. Use temporal context to turn 'بكرا' or 'السبت' into 'YYYY-MM-DD HH:MM'."
    )

class BookingResponse(BaseModel):
    reply: str = Field(description="Clean reply to send to the user")
    summary: str = Field(description="An updated English summary of the user's overall state. "
            "If a booking exists, condense it into a single status line (e.g., 'User has a confirmed booking for X on Y'). "
            "Do NOT append historical chat logs or repeat identical events. Combine and update the state intelligently.")
    lead: BookingLead = Field(description="Structured booking data ONLY.")
    confirmed: bool = Field(description="True if the user confirms. Accept Egyptian slang like 'تمام', 'تمان', 'ايوه', 'اه', 'ماشي'.")
    ready_to_save: bool = Field(description="True only if all 4 booking fields exist (name, phone, details, date).")
