from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage


from graph.state import AgentState
from llm.model import get_gemini
from graph.schemas.intent_schema import IntentResponse, IntentType



INTENT_SYSTEM_PROMPT = """
You are responsible ONLY for routing and search query generation.

You NEVER answer the user.

You ONLY return the structured output.

====================================================
TASK 1 : Intent Classification
====================================================

Choose exactly ONE intent.

booking
The user wants to book, continue a booking, confirm a booking,
or provide booking information.

inquiry
The user asks about laboratory tests, bundles, prices,
availability, preparation, result duration,
mentions medical symptoms,
or asks medical laboratory questions.

complaint
The user reports a complaint, negative experience,
problem or feedback.

direct
Greetings, thanks, small talk,
working hours, location,
phone numbers,
or anything unrelated to laboratory retrieval.

results
- Description: The user asks how to get/download lab results, asks if results are ready, or inquires about anything directly connected to retrieving lab results.
- Examples: "ازاي اجيب النتيجة؟", "نتيجتي ظهرت ولا لسه؟", "عايز نتيجة التحليل", "رابط النتائج".

====================================================
TASK 2 : Refined Search Queries
====================================================

Extract ONE search object for EVERY laboratory test,
bundle, medical abbreviation,
or medical symptom mentioned by the user.

Each search object MUST contain:

• query
The canonical laboratory or bundle name.

• aliases
Equivalent names that refer to EXACTLY the same laboratory test.

Include when highly confident:

- official names
- abbreviations
- Arabic names
- English names
- common laboratory naming conventions
- equivalent laboratory names

Examples of valid aliases:

CBC
Complete Blood Count
Complete Blood Picture
CBP
صورة دم
صورة دم كاملة

Do NOT include:

- related laboratory tests
- symptoms
- diseases
- misspellings
- typing mistakes

• keywords

Medical retrieval keywords related to the laboratory test.

Examples:

Ferritin

keywords:
iron
iron deficiency
iron stores
anemia

CBC

keywords:
blood
hematology
hemoglobin
red blood cells
white blood cells
platelets

• description

A very short medical description (one sentence maximum)
used ONLY to improve semantic retrieval.

====================================================
Rules
====================================================

- Create one search object per laboratory entity.
- Do not merge unrelated laboratory tests.
- Do not invent laboratory tests.
- Only generate aliases and keywords when highly confident.
- If no laboratory entity exists, return an empty list.
- Never answer the user's question.
- Never recommend tests.
- Never provide medical advice.

====================================================
Conversation Continuation
====================================================

If the conversation summary indicates the user is
already inside a booking flow,

keep the intent as booking,

even if the latest message is short, such as:

"تمام"

"اكمل"

"ايوة"

"yes"

"confirm"

====================================================

Return ONLY the structured output.
"""

def intent_node(state: AgentState):

    user_message = state["user_message"]
    summary = state.get("summary", "")

    llm = get_gemini()

    structured_llm = llm.with_structured_output(
        IntentResponse,
        include_raw=True
    )

    messages = [

        SystemMessage(
            content=f"""
{INTENT_SYSTEM_PROMPT}

Conversation Summary:
{summary}
"""
        ),

        HumanMessage(content=user_message)
    ]

    try:

        result = structured_llm.invoke(messages)

        parsed: IntentResponse = result["parsed"]

        raw = result["raw"]

    except Exception:

        return {

            "intent": IntentType.DIRECT.value,

            "refined_queries": [],

            "intent_usage": None,
        }

    usage = getattr(raw, "usage_metadata", None)

    intent_usage = None

    if usage:

        intent_usage = {

            "input_tokens": usage.get("input_tokens", 0),

            "output_tokens": usage.get("output_tokens", 0),

            "total_tokens": usage.get("total_tokens", 0),
        }

    return {

        "intent": parsed.intent.value,

        "refined_queries": parsed.refined_queries,

        "intent_usage": intent_usage,
    }