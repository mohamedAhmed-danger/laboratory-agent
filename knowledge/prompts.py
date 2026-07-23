"""
prompts.py
All prompt templates used by the LLM live here so they can be tuned
without touching pipeline logic.
"""

SYSTEM_PROMPT = """You are a medical knowledge-base assistant for a lab-testing platform.
Given structured input about a Lab Test or Bundle, you generate a JSON object that will be
used to power search and a patient/administrator-facing knowledge base.

You MUST return ONLY a raw JSON object, with no markdown fences and no extra commentary,
matching exactly this shape:

{
  "description": "string, 2-4 sentences, plain language, explains what the test/bundle is and why it's used",
  "aliases": ["string", "..."],
  "keywords": ["string", "..."],
  "search_text": "string, a dense single paragraph combining the name, description, aliases and keywords, optimized for semantic search"
}

Rules:
- "aliases" must contain at least 3 alternative names, abbreviations, or common misspellings.
- "keywords" must contain at least 5 relevant single/short-phrase search terms.
- Do not invent clinical claims that aren't reasonably standard knowledge for this kind of test.
- Never include pricing information inside the description.
"""


def build_generation_prompt(name: str, patient_instructions: str | None,
                             duration: str | None, price: float | None) -> str:
    """Builds the user prompt for the knowledge generation call."""
    return f"""Generate knowledge base content for the following item.

Name: {name}
Patient Instructions: {patient_instructions or "N/A"}
Duration: {duration or "N/A"}
Price: {price if price is not None else "N/A"}

Return only the JSON object described in the system prompt.
"""


def build_regeneration_prompt(name: str, patient_instructions: str | None,
                               duration: str | None, price: float | None,
                               previous_output: dict, admin_feedback: str | None = None) -> str:
    """Used when the admin clicks "Generate Again"."""
    feedback_block = f"\nAdmin feedback on the previous attempt: {admin_feedback}" if admin_feedback else ""
    return f"""Regenerate improved knowledge base content for the following item.
The previous attempt is included below for context — improve on it, don't just repeat it.

Name: {name}
Patient Instructions: {patient_instructions or "N/A"}
Duration: {duration or "N/A"}
Price: {price if price is not None else "N/A"}

Previous attempt:
{previous_output}
{feedback_block}

Return only the JSON object described in the system prompt.
"""