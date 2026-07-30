from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from graph.state import AgentState
from llm.model import get_gemini


class IntentType(str, Enum):
    BOOKING = "booking"
    INQUIRY = "inquiry"
    COMPLAINT = "complaint"
    DIRECT = "direct"


class IntentResponse(BaseModel):

    intent: IntentType = Field(
        description="Detected user intent."
    )

    search_query: list[str] = Field(
        default_factory=list,
        description=(
            "Semantic search terms used for retrieval. "
            "Include standardized medical names, aliases, abbreviations, "
            "common spellings and related keywords. "
            "Return an empty list if no medical entity exists."
        )
    )


INTENT_SYSTEM_PROMPT = """
You are responsible ONLY for routing and search query generation.

You are NOT an assistant.
You are NOT answering the user.

Your job has only two tasks.

---------------------------------------
TASK 1 : Intent Classification
---------------------------------------

Choose ONE intent.

booking
The user wants to book, schedule or continue booking.

inquiry
The user asks about laboratory tests, prices,
availability, preparation,
result duration,
or mentions a laboratory test or medical concern.

complaint
The user reports a problem or complaint.

direct
Greetings,
small talk,
thanks,
lab information,
working hours,
location,
phone numbers,
or anything unrelated to laboratory retrieval.

---------------------------------------
TASK 2 : Search Query Generation
---------------------------------------

If the message contains laboratory tests,
medical abbreviations,
medical entities,
or symptoms,

generate a semantic retrieval query.

The search query should contain:

- official laboratory name
- common English name
- common Arabic name
- abbreviations
- aliases
- common spellings
- search keywords

The purpose is ONLY to improve retrieval quality.

Do NOT answer.

Do NOT recommend tests.

Do NOT invent laboratory tests.

Do NOT generate medical advice.

Only expand entities that you are highly confident about.

If there are no medical entities,

return an empty list.

---------------------------------------
Conversation Continuation
---------------------------------------

If the conversation summary shows the user is
already inside a booking flow,
keep the booking intent even if the latest
message is short like:

"yes"

"okay"

"تمام"

"اكمل"

---------------------------------------
Output
---------------------------------------

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

            "search_query": [],

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

        "search_query": parsed.search_query,

        "intent_usage": intent_usage,
    }