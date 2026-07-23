
import logging
from .duplicate_checker import check_duplicate
from .generator import generate_knowledge, regenerate_knowledge
from .embedding import generate_embedding
from .schemas import (
    ApprovedKnowledge,
    DuplicateCheckResult,
    EntityType,
    GeneratedKnowledge,
    KnowledgeGenerationRequest,
    VectorMetadata,
)
from .updater import update_knowledge
from .validator import validate_knowledge
from .vector_store import upsert_vector

logger = logging.getLogger(__name__)


class DuplicateFoundError(Exception):
    def __init__(self, result: DuplicateCheckResult):
        self.result = result
        super().__init__(f"Duplicate found: {result.matched_name} (score={result.score})")


class KnowledgeValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {errors}")


def run_pre_approval_stage(request: KnowledgeGenerationRequest) -> GeneratedKnowledge:
    """
    Runs: Duplicate Checker -> Generate Knowledge -> Validate.
    Returns the validated GeneratedKnowledge to be shown on the Review Page.
    Raises DuplicateFoundError or KnowledgeValidationError if either step fails.
    """
    # Step 1 - Duplicate Checker
    dup_result = check_duplicate(request.name, request.entity_type)
    if dup_result.is_duplicate:
        logger.info("Duplicate detected for '%s': %s", request.name, dup_result)
        raise DuplicateFoundError(dup_result)

    # Step 2 - Generate Knowledge (LLM)
    generated = generate_knowledge(request)

    # Step 3 - Validate
    validation = validate_knowledge(generated)
    if not validation.is_valid:
        logger.warning("Validation failed for '%s': %s", request.name, validation.errors)
        raise KnowledgeValidationError(validation.errors)

    # Step 4 happens client-side (Review Page) - nothing written yet.
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
    Runs after the admin clicks "Approve" (possibly having edited the
    description/keywords/aliases/search_text first):

        Update PostgreSQL -> Generate Embedding -> Insert into Vector DB
    """
    approved = ApprovedKnowledge(
        entity_id=entity_id,
        entity_type=entity_type,
        **final_knowledge.model_dump(),
    )

    # Step 5 - PostgreSQL Update
    update_knowledge(approved)

    # Step 6 - Embedding Generation
    embedding = generate_embedding(name, approved)

    # Step 7 - Vector Database Update
    metadata = VectorMetadata(id=entity_id, type=entity_type, name=name)
    upsert_vector(metadata, embedding)

    logger.info("Knowledge pipeline complete for %s id=%s ('%s').", entity_type.value, entity_id, name)