from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from graph.nodes.booking_tools import save_booking_tool
from graph.prompt_service.lab_data import LabDataService
from graph.schemas.booking_schema import BookingResponse
from graph.state import AgentState
from graph.utils import detect_language_fallback, generate_booking_pdf
from llm.model import get_gemini
from software_services.client_services import ClientService

BOOKING_SYSTEM_PROMPT = """
You are a professional booking assistant for a medical laboratory.

Your task is to collect patient details and booking information professionally.

====================
REQUIRED FIELDS
====================

- name (Patient Name)
- phone (Phone Number)
- details (The list of medical analyses/tests they want to book, e.g., 'تحليل دم', 'صورة دم كاملة').
- date (Appointment Date)

====================
RULES
====================

1. Never ask for fields already collected.
2. Ask for ONE missing field at a time.
3. Match the user's language.
4. Never invent information.
5. Ask the user for confirmation after collecting all fields and before saving.
6. confirmed=true ONLY if the user clearly confirms.
7. ready_to_save=true ONLY if ALL fields exist.
"""


def booking_node(state: AgentState) -> dict:
    page_id          = state.get("page_id")
    sender_id        = state.get("sender_id")
    platform_id      = state.get("platform_id")
    user_message     = state["user_message"]
    current_summary  = state.get("summary") or ""
    existing_lead    = state.get("booking_lead") or {}
    last_bot_message = state.get("last_bot_message") or ""

    now = datetime.now()
    current_time_info = now.strftime("Today is %A, %B %d, %Y. Current time is %I:%M %p")
    lab_info, services = LabDataService.get_all_lab_data(page_id)

    llm            = get_gemini()
    structured_llm = llm.with_structured_output(BookingResponse, include_raw=True)

    system_prompt = f"""
{BOOKING_SYSTEM_PROMPT}

====================
CRITICAL: CURRENT TEMPORAL CONTEXT
====================
{current_time_info}
Use this to resolve relative dates like "بكرا", "السبت الجاي", etc.

====================
LABORATORY & SERVICES DATA
====================
Laboratory Info: {lab_info}
Available Services: {services}

====================
ALREADY COLLECTED
====================
Summary:          {current_summary}
Lead:             {existing_lead}
Last bot message: {last_bot_message}
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ]

    # ── LLM call ─────────────────────────────────────────────────────────────
    try:
        result        = structured_llm.invoke(messages)
        parsed: BookingResponse = result["parsed"]
        raw_response  = result["raw"]
    except Exception as e:
        print(f"[Booking Node] LLM error: {e}")
        fallback = detect_language_fallback(
            user_message,
            arabic="عذرًا، حدث خطأ مؤقت. حاول مرة أخرى.",
            default="Sorry, a temporary error occurred. Please try again.",
        )
        return {
            "response":         fallback,
            "summary":          current_summary,
            "booking_lead":     existing_lead,
            "last_bot_message": fallback,
            "booking_saved":    False,
            "booking_reference": None,
            "booking_pdf":      None,
            "booking_usage":    None,
        }

    # ── usage ─────────────────────────────────────────────────────────────────
    usage = getattr(raw_response, "usage_metadata", None)
    booking_usage = (
        {
            "input_tokens":  usage.get("input_tokens",  0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens":  usage.get("total_tokens",  0),
        }
        if usage
        else None
    )

    # ── merge lead ────────────────────────────────────────────────────────────
    updated_lead = {
        **existing_lead,
        **parsed.lead.model_dump(exclude_none=True),
    }

    required_fields    = ["name", "phone", "details", "date"]
    all_fields_present = all(updated_lead.get(f) for f in required_fields)

    booking_saved     = False
    booking_reference = None
    booking_pdf       = None

    # ── save ──────────────────────────────────────────────────────────────────
    if parsed.ready_to_save and parsed.confirmed and all_fields_present:
        try:
            result = save_booking_tool.invoke(input={
                **updated_lead,
                "comes_from": str(platform_id or "unknown"),
            })

            if result.success and result.booking:
                booking_saved     = True
                booking_reference = result.booking.reference_id
                booking_pdf       = generate_booking_pdf(
                    name=updated_lead.get("name"),
                    phone=updated_lead.get("phone"),
                    date=updated_lead.get("date"),
                    details=updated_lead.get("details"),
                    reference_id=booking_reference,
                )

                clean_reply = detect_language_fallback(
                    user_message,
                    arabic=(
                        f"تم تأكيد الحجز بنجاح ✅\n"
                        f"رقم الحجز: *{booking_reference}*\n"
                        f"سيتواصل معك فريقنا قريبًا."
                    ),
                    default=(
                        f"Your booking has been confirmed ✅\n"
                        f"Reference: *{booking_reference}*\n"
                        f"Our team will contact you soon."
                    ),
                )
            else:
                raise ValueError(result.message)

        except Exception as e:
            print(f"[Booking Node] Tool error: {e}")
            booking_saved  = False
            booking_pdf    = None
            parsed.summary = current_summary   # rollback summary

            clean_reply = detect_language_fallback(
                user_message,
                arabic="حدث خطأ أثناء حفظ الحجز. حاول مرة أخرى.",
                default="An error occurred while saving your booking. Please try again.",
            )
    else:
        clean_reply = parsed.reply

    # ── persist client state ──────────────────────────────────────────────────
    try:
        ClientService.update_client_summary_and_last_bot_message(
            sender_id=sender_id,
            page_id=page_id,
            platform_id=platform_id,
            summary=parsed.summary,
            last_bot_message=clean_reply,
        )
    except Exception as e:
        print(f"[Booking Node] Persist error: {e}")

    print(
        f"[Booking Node] done | saved={booking_saved} "
        f"| ref={booking_reference} | usage={booking_usage}"
    )

    return {
        "response":          clean_reply,
        "summary":           parsed.summary,
        "booking_lead":      {} if booking_saved else updated_lead,
        "last_bot_message":  clean_reply,
        "booking_saved":     booking_saved,
        "booking_reference": booking_reference,
        "booking_pdf":       booking_pdf,
        "booking_usage":     booking_usage,
    }
