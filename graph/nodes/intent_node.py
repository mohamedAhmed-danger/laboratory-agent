from langchain_core.messages import HumanMessage, SystemMessage
from graph.state import AgentState
from llm.model import get_gemini
from pydantic import BaseModel, Field

class IntentResponse(BaseModel):
    intent: str = Field(description="The classified intent of the user. Choose from: 'booking', 'complaint', 'inquiry', 'direct'.")

INTENT_SYSTEM_PROMPT = """
You are an intent classification routing model for a medical laboratory assistant.
Analyze the user's message along with the conversation summary to determine their intent.

====================
INTENTS
====================
1. "booking": User wants to book an appointment, schedule a test, or finalize scheduling.
2. "complaint": User is voicing a complaint, expressing dissatisfaction, reporting a bug, or reporting an issue.
3. "inquiry": User is inquiring about medical tests, prescription details, prices of tests, or whether a test is available at the laboratory.
4. "direct": User is greeting, sending generic chit-chat (e.g. "مرحبا", "hello"), or asking general questions about the lab itself (location, hours, contact info).

====================
CRITICAL RULES
====================
- If the user's input continues a previous flow (check 'Summary'), prioritize routing to that flow. E.g. if the user is in the middle of a booking, choose "booking".
- Output ONLY the structured JSON containing the intent.
"""

def intent_node(state: AgentState) -> dict:
    user_message = state["user_message"]
    summary = state.get("summary") or ""
    
    llm = get_gemini()
    structured_llm = llm.with_structured_output(IntentResponse, include_raw=True)
    
    system_prompt = f"""
{INTENT_SYSTEM_PROMPT}

====================
TEMPORAL CONTEXT / MEMORY
====================
Summary of current conversation state: {summary}
"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]
    
    try:
        result = structured_llm.invoke(messages)
        parsed: IntentResponse = result["parsed"]
        raw_response = result["raw"]
        intent = parsed.intent
    except Exception as e:
        print(f"[Intent Node] LLM error: {e}")
        intent = "direct"
        raw_response = None
        
    usage = getattr(raw_response, "usage_metadata", None)
    intent_usage = (
        {
            "input_tokens":  usage.get("input_tokens",  0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens":  usage.get("total_tokens",  0),
        }
        if usage
        else None
    )
    
    return {
        "intent": intent,
        "intent_usage": intent_usage
    }
