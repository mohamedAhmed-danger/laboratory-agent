"""
pipeline.py
Main orchestrator. Coordinates knowledge generation for an EXISTING
Lab/Bundle (duplicate checking happens earlier, at creation time -
see lab_service_services.py / bundle_services.py - not here, since by
the time this runs the entity already exists and would always match
itself).

    Generate Knowledge (LLM) -> Validate -> Review Page
    -> [Admin Approval] -> Update PostgreSQL -> Generate Embedding
    -> Insert into Vector Database -> Done
"""

import logging

from .generator import generate_knowledge, regenerate_knowledge
from .embedding import generate_embedding
from .schemas import (
    ApprovedKnowledge,
    EntityType,
    GeneratedKnowledge,
    KnowledgeGenerationRequest,
    VectorMetadata,
)
from .updater import update_knowledge
from .validator import validate_knowledge
from .vector_store import upsert_vector

logger = logging.getLogger(__name__)


class KnowledgeValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {errors}")


def run_pre_approval_stage(request: KnowledgeGenerationRequest) -> GeneratedKnowledge:
    """
    Runs: Generate Knowledge (LLM) -> Validate.
    Returns the validated GeneratedKnowledge to be shown on the Review Page.
    Raises KnowledgeValidationError if validation fails.
    """
    # Step 1 - Generate Knowledge (LLM)
    generated = generate_knowledge(request)

    # Step 2 - Validate
    validation = validate_knowledge(generated)
    if not validation.is_valid:
        logger.warning("Validation failed for '%s': %s", request.name, validation.errors)
        raise KnowledgeValidationError(validation.errors)

    # Step 3 happens client-side (Review Page) - nothing written yet.
    return generated


def regenerate(
    request: KnowledgeGenerationRequest,
    previous_output: GeneratedKnowledge,
    admin_feedback: str | None = None,
) -> GeneratedKnowledge:
    """Handles the 'Generate Again' button on the Review Page."""
    generated = regenerate_knowledge(request, previous_output, admin_feedback)
    validation = validate_knowledge(generated)
    if not validation.is_valid:
        raise KnowledgeValidationError(validation.errors)
    return generated


def run_post_approval_stage(entity_id: int, entity_type: EntityType, name: str,
                             final_knowledge: GeneratedKnowledge) -> None:
    """
    Runs after the admin clicks "Approve":
        Update PostgreSQL -> Generate Embedding -> Insert into Vector Database
    """
    approved = ApprovedKnowledge(
        entity_id=entity_id,
        entity_type=entity_type,
        **final_knowledge.model_dump(),
    )

    update_knowledge(approved)
    embedding = generate_embedding(name, approved)
    metadata = VectorMetadata(id=entity_id, type=entity_type, name=name)
    upsert_vector(metadata, embedding)

    logger.info("Knowledge pipeline complete for %s id=%s ('%s').", entity_type.value, entity_id, name)