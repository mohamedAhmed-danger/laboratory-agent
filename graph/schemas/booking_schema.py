from typing import Optional

from pydantic import BaseModel, Field


class BookingData(BaseModel):
    name: Optional[str] = Field(
        None,
        description="Patient full name."
    )

    phone: Optional[str] = Field(
        None,
        description="Patient phone number."
    )

    details: Optional[str] = Field(
        None,
        description="Requested laboratory test(s) exactly as understood from the conversation."
    )

    date: Optional[str] = Field(
        None,
        description="Resolved appointment date/time in ISO format if possible."
    )


class BookingResponse(BaseModel):

    reply: str = Field(
        description="Reply that will be sent to the user."
    )

    summary: str = Field(
        description=(
            "Updated English conversation summary. "
            "Always keep all collected booking information "
            "(patient name, phone, requested tests, appointment date, "
            "confirmation status) so future turns can continue without "
            "asking again."
        )
    )

    booking: BookingData = Field(
        description="Structured booking information extracted from this turn."
    )

    confirmed: bool = Field(
        description=(
            "True only if the user explicitly confirms the booking "
            "(e.g. تمام، ماشي، اه، أيوة، yes, confirm)."
        )
    )

    ready_to_save: bool = Field(
        description=(
            "True only if name, phone, requested tests, and appointment date "
            "are all available from the conversation."
        )
    )