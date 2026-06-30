from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from graph.prompt_service.lab_data import LabDataService
from graph.schemas.inquiry_schema import InquiryResponse
from graph.state import AgentState
from graph.utils import detect_language_fallback
from llm.model import get_gemini
from software_services.client_services import ClientService

INQUIRY_SYSTEM_PROMPT = """
You are a helpful laboratory assistant.
Your task is to answer inquiries about medical tests, prescription details, prices, and test availability.

====================
RULES
====================
1. Review the available services in the laboratory and match the tests requested by the user.
2. For each matched test, provide the name, description, and price if available in the database.
3. If a test is not found in the database services, politely state that it's currently not available.
4. Keep the tone professional and warm.
5. Offer to help them book an appointment if they are ready (tell them they can say "تمام" or "احجزلي").
6. Match the user's language.
"""

def inquiry_node(state: AgentState) -> dict:
    page_id          = state.get("page_id")
    sender_id        = state.get("sender_id")
    platform_id      = state.get("platform_id")
    user_message     = state["user_message"]
    current_summary  = state.get("summary") or ""
    existing_lead    = state.get("inquiry_lead") or {}
    last_bot_message = state.get("last_bot_message") or ""

    lab_info, services = LabDataService.get_all_lab_data(page_id)

    llm            = get_gemini()
    structured_llm = llm.with_structured_output(InquiryResponse, include_raw=True)

    system_prompt = f"""
{INQUIRY_SYSTEM_PROMPT}

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

    try:
        result        = structured_llm.invoke(messages)
        parsed: InquiryResponse = result["parsed"]
        raw_response  = result["raw"]
    except Exception as e:
        print(f"[Inquiry Node] LLM error: {e}")
        fallback = detect_language_fallback(
            user_message,
            arabic="عذرًا، حدث خطأ مؤقت أثناء معالجة الاستفسار. حاول مرة أخرى.",
            default="Sorry, a temporary error occurred while processing your inquiry. Please try again.",
        )
        return {
            "response":         fallback,
            "summary":          current_summary,
            "inquiry_lead":     existing_lead,
            "last_bot_message": fallback,
            "inquiry_saved":    False,
            "inquiry_usage":    None,
        }

    usage = getattr(raw_response, "usage_metadata", None)
    inquiry_usage = (
        {
            "input_tokens":  usage.get("input_tokens",  0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens":  usage.get("total_tokens",  0),
        }
        if usage
        else None
    )

    updated_lead = {
        **existing_lead,
        **parsed.lead.model_dump(exclude_none=True),
    }

    clean_reply = parsed.reply

    try:
        ClientService.update_client_summary_and_last_bot_message(
            sender_id=sender_id,
            page_id=page_id,
            platform_id=platform_id,
            summary=parsed.summary,
            last_bot_message=clean_reply,
        )
    except Exception as e:
        print(f"[Inquiry Node] Persist error: {e}")

    return {
        "response":          clean_reply,
        "summary":           parsed.summary,
        "inquiry_lead":      updated_lead,
        "last_bot_message":  clean_reply,
        "inquiry_saved":     True,
        "inquiry_usage":     inquiry_usage,
    }
