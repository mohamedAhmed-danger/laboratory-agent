"""
validator.py
Validates generated knowledge before displaying it to the administrator
on the Review Page.

Rules (per spec):
- Description cannot be empty.
- At least 3 aliases.
- At least 5 keywords.
- Search text cannot be empty.
- JSON must follow the schema (enforced by GeneratedKnowledge already,
  but re-checked here defensively since this may receive raw dicts too).
"""

from pydantic import ValidationError

from .schemas import GeneratedKnowledge, ValidationResult

MIN_ALIASES = 3
MIN_KEYWORDS = 5


def validate_knowledge(data: GeneratedKnowledge | dict) -> ValidationResult:
    errors: list[str] = []

    # Schema check first
    if not isinstance(data, GeneratedKnowledge):
        try:
            data = GeneratedKnowledge(**data)
        except ValidationError as e:
            return ValidationResult(is_valid=False, errors=[str(err["msg"]) for err in e.errors()])

    if not data.description or not data.description.strip():
        errors.append("Description cannot be empty.")

    if len(data.aliases) < MIN_ALIASES:
        errors.append(f"At least {MIN_ALIASES} aliases are required (got {len(data.aliases)}).")

    if len(data.keywords) < MIN_KEYWORDS:
        errors.append(f"At least {MIN_KEYWORDS} keywords are required (got {len(data.keywords)}).")

    if not data.search_text or not data.search_text.strip():
        errors.append("Search text cannot be empty.")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)