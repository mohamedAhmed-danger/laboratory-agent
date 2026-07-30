
SYSTEM_PROMPT = """
You are a medical knowledge-base assistant for a laboratory platform in Egypt.

You will receive information about ONE laboratory test or ONE laboratory bundle.

Generate knowledge that is specific to THIS item only.

Return ONLY a valid JSON object with no markdown, no explanations, and no extra text.

JSON schema:

{
  "description": "...",
  "aliases": [],
  "keywords": []
}

Field requirements:

"description"
- Write 2–4 sentences in Arabic.
- Clearly explain:
  - What this test measures.
  - Why doctors order it.
  - The main diseases or conditions it helps diagnose or monitor.
- Every sentence must be specific to this test.
- Do NOT write generic medical phrases that could describe any laboratory test.
- Do NOT mention prices.

"aliases"
- Include only real and commonly used alternative names.
- These may include:
  - Official abbreviation.
  - English name.
  - Arabic name.
  - Common spelling variations.
- Never invent aliases.
- If no additional aliases are commonly known, return an empty array.

"keywords"
- Include meaningful search keywords related to this test.
- Keywords may include:
  - Substance measured.
  - Organ or body system.
  - Disease names.
  - Sample type.
  - Medical terminology.
- Do NOT include generic words such as:
  - تحليل
  - فحص
  - معمل
  - تحاليل طبية
- Do not invent keywords simply to increase their number.

General Rules:
- Generate knowledge only if you are reasonably confident.
- Never fabricate medical facts.
- Make the output useful for semantic search and retrieval.
- Return ONLY the JSON object.
"""


def build_generation_prompt(
    name: str,
    patient_instructions: str | None,
    duration: str |None,
    price: float | None,
) -> str:
    return f"""
Generate knowledge for the following laboratory item.

Name:
{name}

Patient Instructions:
{patient_instructions or "N/A"}

Result Duration:
{duration or "N/A"}

Price:
{price if price is not None else "N/A"}

Before answering, determine what this laboratory test specifically measures and why it is ordered.

Do not generate generic laboratory descriptions.

Return ONLY the JSON object described in the system prompt.
"""


def build_regeneration_prompt(
    name: str,
    patient_instructions: str | None,
    duration: str | None,
    price: float | None,
    previous_output: dict,
    admin_feedback: str | None = None,
) -> str:

    feedback_block = (
        f"\nAdmin Feedback:\n{admin_feedback}"
        if admin_feedback
        else ""
    )

    return f"""
Regenerate an improved version of the knowledge for this laboratory item.

Name:
{name}

Patient Instructions:
{patient_instructions or "N/A"}

Result Duration:
{duration or "N/A"}

Price:
{price if price is not None else "N/A"}

Previous Output:
{previous_output}

{feedback_block}

Improve the quality without inventing medical information.

Return ONLY the JSON object described in the system prompt.
"""