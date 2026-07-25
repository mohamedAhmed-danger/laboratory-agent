"""
prompts.py
All prompt templates used by the LLM live here so they can be tuned
without touching pipeline logic.
"""

SYSTEM_PROMPT = """You are a medical knowledge-base assistant for a lab-testing platform in Egypt.
Given structured input about ONE specific Lab Test or Bundle, generate JSON that is UNIQUE and
SPECIFIC to this exact test — never generic filler that could apply to any test.

You MUST return ONLY a raw JSON object, with no markdown fences and no extra commentary,
matching exactly this shape:

{
  "description": "2-4 sentences in Arabic. MUST name the specific substance, component, organ,
     or cell type this test measures or examines, and the specific clinical reason doctors
     order THIS test (e.g. diagnosing diabetes, monitoring kidney function, detecting anemia,
     screening for infection). FORBIDDEN: generic phrases that could apply to any test, such as
     'يساعد في التشخيص الطبي وتقييم الوظائف الحيوية للمريض' (helps in medical diagnosis and
     evaluating the patient's vital functions) without saying WHAT is actually measured.",
  "aliases": ["at least 3 DISTINCT alternative names: the official abbreviation, the common
     patient-facing name, the English name if relevant, or a common variant spelling.
     Never repeat the same word twice inside one alias (e.g. 'تحليل تحليل X' is invalid —
     write 'تحليل X' once)."],
  "keywords": ["at least 5 specific search terms: the substance/component measured, the body
     system involved, the condition(s) it screens for, the sample type. Avoid generic filler
     words like 'تحاليل طبية' or 'فحص طبي' that don't distinguish this test from any other."]
}

Rules:
- Every field must be specific enough that someone reading only the JSON could tell which test
  it describes, without seeing the name.
- Do not invent clinical claims that aren't reasonably standard knowledge for this kind of test.
- Never include pricing information inside the description.
"""


def build_generation_prompt(name: str, patient_instructions: str | None,
                             duration: str | None, price: float | None) -> str:
    """Builds the user prompt for the knowledge generation call."""
    return f"""Generate knowledge base content for this exact test — be specific to it,
not to lab tests in general.

Name: {name}
Patient Instructions: {patient_instructions or "N/A"}
Duration: {duration or "N/A"}
Price: {price if price is not None else "N/A"}

Before answering, silently identify: what specific substance, organ, or component does THIS
test measure, and what specific condition(s) does it screen for or help diagnose? Base the
description on that — do not write anything that could be copy-pasted onto a different test.

Return only the JSON object described in the system prompt.
"""


def build_regeneration_prompt(name: str, patient_instructions: str | None,
                               duration: str | None, price: float | None,
                               previous_output: dict, admin_feedback: str | None = None) -> str:
    """Used when the admin clicks "Generate Again"."""
    feedback_block = f"\nAdmin feedback on the previous attempt: {admin_feedback}" if admin_feedback else ""
    return f"""Regenerate improved knowledge base content for the following item.
The previous attempt is included below for context — it may have been too generic.
Make this version more specific to this exact test, not lab tests in general.

Name: {name}
Patient Instructions: {patient_instructions or "N/A"}
Duration: {duration or "N/A"}
Price: {price if price is not None else "N/A"}

Previous attempt:
{previous_output}
{feedback_block}

Return only the JSON object described in the system prompt.
"""