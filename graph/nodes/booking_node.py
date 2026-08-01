from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from graph.nodes.booking_tools import save_booking_tool
from graph.schemas.booking_schema import BookingResponse
from graph.state import AgentState
from graph.utils import detect_language_fallback, generate_booking_ticket
from llm.model import get_gemini
from software_services.client_services import ClientService
from graph.prompt_service.lab_data import LabDataService

BOOKING_SYSTEM_PROMPT = """
You are a professional booking assistant for a medical laboratory.

Your task is to collect patient details and booking information professionally.
====================
RULES
====================

BOOKING FLOW

1. Collect booking information step-by-step.
2. Never ask for information that is already available.
3. Ask for ONLY ONE missing field at a time.
4. Match the user's language.
5. Never overwrite previously collected information unless the user explicitly changes it.
6. Keep previously collected booking information throughout the conversation.

BOOKING VALIDATION

A booking is COMPLETE only when ALL of the following exist:

- Patient name
- Phone number
- At least ONE laboratory test/service
- Appointment date/time
- Explicit confirmation from the patient

The booking MUST NOT be saved unless ALL of these conditions are satisfied.

ready_to_save = true ONLY IF:

- name exists
- phone exists
- details contains at least one laboratory test
- appointment date exists
- confirmed == true

Otherwise:
ready_to_save = false

Never infer or invent any missing booking field.

If any required field is missing, continue collecting information instead of confirming or saving.

Never create a booking with empty or generic details.

The "details" field MUST contain the laboratory tests requested by the patient.

Never save a booking if details is empty.

BOOKING CONFIRMATION

Once all required information has been collected:

Summarize the booking before asking for confirmation.

Example:

Name:
Phone:
Tests:
Appointment:

Then ask:

"Do you confirm this booking?"

Only after the patient explicitly confirms may confirmed=true.

Words like:
- نعم
- أؤكد
- تمام
- Confirm
- Yes

count as confirmation ONLY IF the assistant has just asked for booking confirmation.

Otherwise they are normal conversation.

BOOKING SAFETY

Never save the same booking twice.

If the conversation summary indicates that the booking has already been completed:

- never generate ready_to_save=true
- never call the booking tool again

unless the user explicitly asks to:

- create a new booking
- book additional tests
- modify the booking
- cancel the booking

Messages such as:

شكرا
تمام
أوكي
👍
Done
Thanks

after a completed booking are acknowledgements only.

Never interpret them as a new booking.

LAB SERVICES

Never invent:

- laboratory tests
- prices
- preparation
- specimen type
- turnaround time

Only answer using the Matched Service information.

If the requested information is available there,
answer immediately before asking for any missing booking field.

Never say "I'll check" if the information is already available.

FORMATTING

Keep replies short and suitable for chat.

Do not write long paragraphs.

When listing laboratory tests, use this format:

🧪 Test Name
💰 Price: XXX EGP
🧪 Preparation: ...
⏱️ Result: ...

Leave a blank line between tests.

If information is unavailable, omit that line instead of guessing.

Never repeat the same information.

Do not repeat greetings in every response.

After a successful booking:

Reply only with the booking confirmation.

Do not ask to book again.
Do not repeat previous information.
"""


def booking_node(state: AgentState) -> dict:
    page_id          = state.get("page_id")
    sender_id        = state.get("sender_id")
    platform_id      = state.get("platform_id")
    user_message     = state["user_message"]
    current_summary  = state.get("summary") or ""
    last_bot_message = state.get("last_bot_message") or ""
    matched_context = state.get("rag_context", "")
   

    now = datetime.now()
    current_time_info = now.strftime("Today is %A, %B %d, %Y. Current time is %I:%M %p")

    lab_info= LabDataService.get_lab_info(page_id)

   
    matched_context = state.get("rag_context") or ""
    

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
VERIFIED LAB INFORMATION (Retrieved from Knowledge Base)
====================
{matched_context or "(No matching laboratory test found. Do not invent prices or medical information.)"}
{lab_info or "(No laboratory information found. Do not invent a address or phone number.)"} this is the lab name and address and phone number.
====================
ALREADY COLLECTED
====================
Summary:          {current_summary}
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
            "response":          fallback,
            "summary":           current_summary,
            "last_bot_message":  fallback,
            "booking_saved":     False,
            "booking_reference": None,
            "booking_ticket":    None,
            "booking_usage":     None,
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

    booking_data = parsed.booking.model_dump(exclude_none=True)

  

    required_fields    = ["name", "phone", "details", "date"]
    all_fields_present = all(
    booking_data.get(f)
    for f in required_fields
)

    booking_saved     = False
    booking_reference = None
    booking_ticket    = None

    # ── save ──────────────────────────────────────────────────────────────────
    if parsed.ready_to_save and parsed.confirmed and all_fields_present:
        try:
            result = save_booking_tool.invoke(input={
                **booking_data,
                "comes_from": str(platform_id or "unknown"),
            })

            if result.success and result.booking:
                booking_saved     = True
                booking_reference = result.booking.reference_id

                total_price = None
                try:
                    from models.models import LabService, Bundle
                    req_details = booking_data.get("details", "")
                    sum_price = 0.0
                    found_any = False
                    parts = [p.strip() for p in req_details.replace("\n", ",").split(",") if p.strip()]
                    for p in parts:
                        svc = LabService.query.filter(LabService.name.ilike(f"%{p}%")).first()
                        if svc and svc.price:
                            sum_price += svc.price
                            found_any = True
                        else:
                            bdl = Bundle.query.filter(Bundle.name.ilike(f"%{p}%")).first()
                            if bdl and bdl.price:
                                sum_price += bdl.price
                                found_any = True
                    if found_any and sum_price > 0:
                        total_price = sum_price
                except Exception as p_err:
                    print(f"[Booking Node] total_price calculation error: {p_err}")

                booking_ticket    = generate_booking_ticket(
                    name=booking_data.get("name"),
                    phone=booking_data.get("phone"),
                    date=booking_data.get("date"),
                    details=booking_data.get("details"),
                    reference_id=booking_reference,
                    total_price=total_price,
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
            booking_ticket = None
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
        "last_bot_message":  clean_reply,
        "booking_saved":     booking_saved,
        "booking_reference": booking_reference,
        "booking_ticket":    booking_ticket,
        "booking_usage":     booking_usage,
    }