from langchain_core.tools import tool

from graph.utils import get_platform_name
from software_services.booking_services import BookingService, BookingResult

@tool
def save_booking_tool(
    name: str,
    phone: str,
    date: str,
    details: str,
    comes_from: str = "unknown",
) -> BookingResult:
    """
    Save a confirmed appointment booking to the database.

    Returns a BookingResult.
    """
    platform_name = get_platform_name(comes_from)

    return BookingService.create_booking(
        name=name,
        phone_number=phone,
        date=date,
        details=details,
        comes_from=platform_name,
    )
