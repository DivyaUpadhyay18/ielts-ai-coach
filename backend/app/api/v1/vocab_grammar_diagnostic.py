"""
Vocabulary & Grammar Diagnostic Module endpoints.

Provides the vocabulary/grammar-specific diagnostic flow:
  - GET  /vocab-grammar/bank      → vocabulary + grammar question bank
  - POST /vocab-grammar/answers   → grade & save a single answer
  - POST /vocab-grammar/attempts/{id}/complete → compute + store results
  - GET  /vocab-grammar/attempts/{id}/report  → fetch the stored report
  - GET  /vocab-grammar/results   → list a user's stored results

Everything is deterministic (NO AI) and owner-scoped.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_vocab_grammar_diagnostic_service
from app.core.exceptions import NotFoundError, ValidationError
from app.models.vocab_grammar_diagnostic import VGAnswerSubmit
from app.services.vocab_grammar_diagnostic_service import VocabGrammarDiagnosticService

router = APIRouter()


@router.get(
    "/bank",
    response_model=dict,
    summary="Get all vocabulary and grammar questions",
)
async def get_bank(
    user_id: str = Depends(get_current_user),
    service: VocabGrammarDiagnosticService = Depends(get_vocab_grammar_diagnostic_service),
):
    """Return all active vocabulary/grammar questions (answer stripped)."""
    return service.get_bank()


@router.post(
    "/answers",
    response_model=dict,
    summary="Submit and grade a vocabulary/grammar answer",
)
async def submit_answer(
    data: VGAnswerSubmit,
    user_id: str = Depends(get_current_user),
    service: VocabGrammarDiagnosticService = Depends(get_vocab_grammar_diagnostic_service),
):
    """Grade and persist a single vocabulary/grammar answer for an attempt."""
    try:
        return service.submit_answer(
            user_id,
            data.attempt_id,
            data.question_id,
            data.answer,
            data.time_taken_seconds,
        )
    except (NotFoundError, ValidationError):
        raise


@router.post(
    "/attempts/{attempt_id}/complete",
    response_model=dict,
    summary="Complete a vocabulary/grammar diagnostic and store results",
)
async def complete_attempt(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: VocabGrammarDiagnosticService = Depends(get_vocab_grammar_diagnostic_service),
):
    """Compute, store, and return the vocabulary/grammar diagnostic report."""
    try:
        return service.complete_attempt(user_id, attempt_id)
    except (NotFoundError, ValidationError):
        raise


@router.get(
    "/attempts/{attempt_id}/report",
    response_model=dict,
    summary="Get the stored vocabulary/grammar diagnostic report",
)
async def get_report(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
    service: VocabGrammarDiagnosticService = Depends(get_vocab_grammar_diagnostic_service),
):
    """Fetch the stored vocabulary/grammar diagnostic report for an attempt."""
    try:
        return service.build_report(user_id, attempt_id)
    except NotFoundError:
        raise


@router.get(
    "/results",
    response_model=dict,
    summary="List a user's stored vocabulary/grammar diagnostic results",
)
async def list_results(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    service: VocabGrammarDiagnosticService = Depends(get_vocab_grammar_diagnostic_service),
):
    """List the current user's stored vocabulary/grammar diagnostic results."""
    return service.list_results(user_id, limit)
