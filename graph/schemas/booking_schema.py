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
        description=(
            "Requested laboratory tests/services exactly as understood from "
            "the conversation. Never leave empty when ready_to_save is true."
        )
    )

    date: Optional[str] = Field(
        None,
        description="Resolved appointment date/time in ISO format if possible."
    )


class BookingResponse(BaseModel):

    reply: str = Field(
        description=(
            "Reply that will be sent to the user. "
            "Keep replies short, friendly, and suitable for chat. "
            "Avoid long paragraphs."
        )
    )

    summary: str = Field(
        description=(
            "Persistent English conversation memory.\n\n"

            "Update this memory after every conversation turn while preserving "
            "all previously collected information.\n\n"

            "Never rewrite the memory from scratch.\n"
            "Never remove valid information unless the user explicitly changes it.\n"
            "Always merge new information into the existing memory.\n\n"

            "Always preserve important information including:\n"
            "- Patient name\n"
            "- Phone number\n"
            "- Requested laboratory tests/services\n"
            "- Appointment date and time\n"
            "- Booking progress\n"
            "- Whether the booking has been confirmed\n"
            "- Whether the booking has already been saved\n\n"

            "If the user changes any information, update only that part while "
            "keeping everything else.\n\n"

            "If additional laboratory tests are requested, append them instead "
            "of replacing previous tests unless the user explicitly removes or "
            "changes them.\n\n"

            "If the booking is successfully saved, clearly state that the booking "
            "has been completed, include the booked laboratory tests and appointment "
            "details, and explicitly mention that no new booking should be created "
            "unless the user asks to create a new booking, modify the current one, "
            "or cancel it.\n\n"

            "Write the memory in natural conversational English, not JSON or "
            "key-value format."
        )
    )

    booking: BookingData = Field(
        description=(
            "Structured booking information extracted from the current conversation. "
            "Populate only information that is known."
        )
    )

    confirmed: bool = Field(
        description=(
            "True ONLY if the user explicitly confirms the booking AFTER the assistant "
            "has shown a booking summary and asked for confirmation.\n\n"

            "Messages such as 'تمام', 'أيوة', 'Yes', 'Confirm', or 'OK' count as "
            "confirmation ONLY in response to a booking confirmation request."
        )
    )

    ready_to_save: bool = Field(
        description=(
            "True ONLY if ALL booking requirements are satisfied:\n"
            "- Patient name exists.\n"
            "- Phone number exists.\n"
            "- At least one laboratory test/service exists.\n"
            "- Appointment date/time exists.\n"
            "- confirmed is True.\n\n"

            "Never return ready_to_save=True if any required field is missing.\n"
            "Never allow a booking with empty details.\n"
            "Never generate ready_to_save=True for a booking that has already been "
            "saved unless the user explicitly starts a completely new booking."
        )
    )