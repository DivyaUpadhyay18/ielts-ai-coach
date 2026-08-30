"""
Speaking Audio Processing Pipeline service.

Runs whenever a speaking response is submitted:

  1. Store the recording securely        → validated + uploaded to Supabase Storage
                                          (user-scoped path) before this service runs
  2. Create a speaking evaluation record → one ``speaking_evaluations`` row
  3. Prepare the audio for transcription → download + validate bytes from storage
  4. Send the audio to the STT provider  → OpenAI Whisper (or mock) via
                                          :class:`SpeechToTextService`
  5. Store the transcript                → evaluation row updated to 'completed'
  6. Preserve the original recording     → ``audio_url`` is never modified/deleted
  7. Handle failures gracefully          → retries with backoff, then 'failed'
                                          status with a retryable error message

Tracked fields: audio_duration_seconds, file_size_bytes, transcript,
processing status, created_at / updated_at.

Transcription runs asynchronously via FastAPI ``BackgroundTasks`` when a
background_tasks instance is supplied (see the API layer).
"""
import asyncio
import logging
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.session import DatabaseSession
from app.repositories.speaking_audio_repo import (
    SpeakingAudioRepository,
    SpeakingAudioStorageRepository,
)
from app.repositories.speaking_test_repo import SpeakingTestRepository
from app.services.ai_service import (
    AIService,
    _compute_confidence,
    _round_band,
)
from app.services.speech_to_text_service import (
    SpeechToTextService,
    TranscriptionError,
    _extension_from_filename,
)

from app.services.speaking_mission_service import SpeakingMissionService

logger = logging.getLogger(__name__)

# Statuses that do not need re-processing (idempotent submit).
_FINAL_OR_ACTIVE_STATUSES = ("queued", "preparing", "transcribing", "completed")

# The four official IELTS Speaking criteria (AI scoring contract).
SPEAKING_CRITERIA_KEYS = (
    "fluency_coherence",
    "lexical_resource",
    "grammatical_range_accuracy",
    "pronunciation",
)

# Heuristic "filler" tokens that signal reduced fluency.
_FILLERS = ("um", "uh", "er", "ah", "like", "you know", "i mean", "basically")


class SpeakingAudioPipelineService:
    """Business logic for the speaking audio processing pipeline."""

    def __init__(
        self,
        db: DatabaseSession,
        stt_service: SpeechToTextService | None = None,
        ai_service: AIService | None = None,
    ) -> None:
        self.db = db
        self.repo = SpeakingAudioRepository(db)
        self.storage = SpeakingAudioStorageRepository(db)
        self.response_repo = SpeakingTestRepository(db)
        self.stt = stt_service or SpeechToTextService()
        self.ai_service = ai_service if ai_service is not None else AIService()
        self.mission_service = SpeakingMissionService(db)

    # ------------------------------------------------------------------
    # Submission
    # ------------------------------------------------------------------
    def submit_response(
        self,
        user_id: str,
        response_id: str,
        session_id: str,
        audio_url: str,
        duration_seconds: int = 0,
        background_tasks: Any | None = None,
    ) -> dict[str, Any]:
        """
        Submit a response's recording to the processing pipeline.

        Steps 1-3 run synchronously so the caller immediately knows whether
        the recording was accepted; steps 4-5 (transcription) run in the
        background when ``background_tasks`` is provided.
        """
        # --- 1. Validate ownership --------------------------------------
        response = self.response_repo.get_response(response_id, user_id)
        if not response:
            raise NotFoundError("Speaking test response not found")
        if str(response.get("session_id")) != str(session_id):
            raise NotFoundError("Speaking test response not found in this session")

        if not audio_url:
            raise ValidationError("No recording has been uploaded for this response")

        # --- 2. Idempotency: reuse an existing evaluation ----------------
        existing = self.repo.get_evaluation_by_response(response_id, user_id)
        if existing:
            if existing.get("status") in _FINAL_OR_ACTIVE_STATUSES:
                # Already queued/processing/completed — nothing to duplicate.
                return self._to_response(existing)
            # 'failed' → reset for a retry without re-uploading.
            evaluation = self.repo.update_evaluation(existing["id"], user_id, {
                "status": "queued",
                "error_message": "",
                "last_processed_at": datetime.utcnow().isoformat(),
            })
        else:
            evaluation = self._create_evaluation(
                user_id, response, session_id, audio_url, duration_seconds
            )

        # --- 3. Enqueue asynchronous transcription -----------------------
        if background_tasks is not None:
            background_tasks.add_task(self.run_transcription, evaluation["id"])
        return self._to_response(evaluation)

    def _create_evaluation(
        self,
        user_id: str,
        response: dict[str, Any],
        session_id: str,
        audio_url: str,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Prepare the audio (download + validate) and create the record."""
        if not self.storage.parse_public_url(audio_url):
            raise ValidationError("Recording URL is not a valid stored audio object")

        # 3. Prepare the audio for transcription — verify accessibility now.
        try:
            audio_bytes = self.storage.download_audio(audio_url)
        except NotFoundError as exc:
            raise ValidationError(f"Recording could not be retrieved: {exc}")

        file_size = len(audio_bytes)
        max_bytes = int(settings.STT_MAX_FILE_SIZE_MB or 25) * 1024 * 1024
        if file_size > max_bytes:
            raise ValidationError(
                f"Recording exceeds the {settings.STT_MAX_FILE_SIZE_MB} MB "
                "processing limit"
            )

        return self.repo.create_evaluation({
            "user_id": user_id,
            "response_id": response.get("id"),
            "session_id": session_id,
            "part": response.get("part") or "part_1",
            "audio_url": audio_url,  # original recording — preserved as-is
            "audio_duration_seconds": max(0, int(duration_seconds or 0)),
            "file_size_bytes": file_size,
            "provider": f"{self.stt.provider}:{self.stt.model}",
            "model": self.stt.model,
            "status": "queued",
        })

    # ------------------------------------------------------------------
    # Asynchronous transcription
    # ------------------------------------------------------------------
    async def run_transcription(self, evaluation_id: str) -> dict[str, Any]:
        """
        Process a queued evaluation: prepare the audio, transcribe it, and
        store the transcript. On failure it retries with backoff and finally
        marks the evaluation 'failed' (the original recording is preserved).
        """
        evaluation = self.repo.get_evaluation_unscoped(evaluation_id)
        if not evaluation:
            logger.warning("speaking evaluation %s not found for processing", evaluation_id)
            return {}
        if evaluation.get("status") == "completed":
            return self._to_response(evaluation)

        existing_retry_count = int(evaluation.get("retry_count") or 0)
        audio_url = evaluation.get("audio_url") or ""
        if not audio_url:
            return self._mark_failed(evaluation_id, existing_retry_count,
                                      "Recording URL is missing")

        attempts = 1 + self.stt.retry_attempts
        last_error: Exception | None = None
        filename = audio_url.rsplit("/", 1)[-1]

        for attempt in range(1, attempts + 1):
            try:
                self._set_worker_status(evaluation_id, "preparing")
                audio_bytes = self.storage.download_audio(audio_url)
                self._set_worker_status(evaluation_id, "transcribing")
                result = await self.stt.transcribe(audio_bytes, filename=filename)
                now = datetime.utcnow().isoformat()
                updated = self.repo.update_evaluation_unscoped(evaluation_id, {
                    "status": "completed",
                    "transcript": result.get("transcript") or "",
                    "audio_duration_seconds": int(
                        result.get("duration_seconds")
                        or evaluation.get("audio_duration_seconds")
                        or 0
                    ),
                    "error_message": "",
                    "last_processed_at": now,
                    "processed_at": now,
                })
                logger.info("speaking evaluation %s transcribed (attempt %d)", evaluation_id, attempt)
                return self._to_response(updated)
            except TranscriptionError as exc:
                last_error = exc
                logger.warning(
                    "speaking evaluation %s transcribe attempt %d/%d failed: %s",
                    evaluation_id, attempt, attempts, exc,
                )
                if not exc.retryable:
                    break
                if attempt < attempts:
                    await asyncio.sleep(min(2 ** attempt, 8))
            except Exception as exc:  # pragma: no cover - defensive
                last_error = exc
                logger.exception(
                    "speaking evaluation %s unexpected error on attempt %d/%d",
                    evaluation_id, attempt, attempts,
                )
                if attempt < attempts:
                    await asyncio.sleep(min(2 ** attempt, 8))

        return self._mark_failed(
            evaluation_id,
            existing_retry_count,
            str(last_error) if last_error else "Transcription failed",
        )

    def _mark_failed(self, evaluation_id: str, existing_retry_count: int,
                     message: str) -> dict[str, Any]:
        """Mark an evaluation failed, preserving the original recording."""
        now = datetime.utcnow().isoformat()
        failed = self.repo.update_evaluation_unscoped(evaluation_id, {
            "status": "failed",
            "error_message": message[:2000],
            "retry_count": existing_retry_count + self.stt.retry_attempts,
            "last_processed_at": now,
        })
        logger.info("speaking evaluation %s marked failed", evaluation_id)
        return self._to_response(failed)

    def _set_worker_status(self, evaluation_id: str, status: str) -> None:
        """Best-effort status update from the background worker."""
        try:
            self.repo.update_evaluation_unscoped(evaluation_id, {
                "status": status,
                "last_processed_at": datetime.utcnow().isoformat(),
            })
        except NotFoundError:
            logger.warning("cannot update missing evaluation %s", evaluation_id)

    # ------------------------------------------------------------------
    # Retry + queries (owner-scoped)
    # ------------------------------------------------------------------
    def retry_evaluation(
        self,
        user_id: str,
        evaluation_id: str,
        background_tasks: Any | None = None,
    ) -> dict[str, Any]:
        """
        Re-enqueue a failed evaluation for transcription without re-uploading.
        """
        evaluation = self.repo.get_evaluation(evaluation_id, user_id)
        if not evaluation:
            raise NotFoundError("Speaking evaluation not found")
        if evaluation.get("status") != "failed":
            raise ValidationError("Only failed evaluations can be retried")

        updated = self.repo.update_evaluation(evaluation_id, user_id, {
            "status": "queued",
            "error_message": "",
            "last_processed_at": datetime.utcnow().isoformat(),
        })
        if background_tasks is not None:
            background_tasks.add_task(self.run_transcription, evaluation_id)
        return self._to_response(updated)

    def get_evaluation(self, user_id: str, evaluation_id: str) -> dict[str, Any]:
        """Fetch a single evaluation (owner-scoped)."""
        evaluation = self.repo.get_evaluation(evaluation_id, user_id)
        if not evaluation:
            raise NotFoundError("Speaking evaluation not found")
        return self._to_response(evaluation)

    def get_evaluation_by_response(self, user_id: str, response_id: str) -> dict[str, Any]:
        """Fetch the evaluation for a specific response (owner-scoped)."""
        evaluation = self.repo.get_evaluation_by_response(response_id, user_id)
        if not evaluation:
            raise NotFoundError("Speaking evaluation not found for this response")
        return self._to_response(evaluation)

    def list_evaluations(self, user_id: str, limit: int = 50) -> dict[str, Any]:
        """List a user's evaluations (most recent first)."""
        rows = self.repo.list_evaluations(user_id, limit)
        return {
            "results": [self._to_response(r) for r in rows],
            "total": len(rows),
        }

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # AI Speaking Evaluation (Phase 10)
    # ------------------------------------------------------------------
    async def evaluate_transcript(
        self,
        user_id: str,
        evaluation_id: str,
    ) -> dict[str, Any]:
        """Run the AI Speaking Evaluation on a completed transcript.

        Generates an IELTS assessment (4 criteria + overall band + confidence)
        from the stored transcript and persists it. All operations are
        owner-scoped. Idempotent: re-running on an already-evaluated record
        returns the cached result without re-calling the AI provider.
        """
        evaluation = self.repo.get_evaluation(evaluation_id, user_id)
        if not evaluation:
            raise NotFoundError("Speaking evaluation not found")
        if not self._is_transcribed(evaluation):
            raise ValidationError(
                "Recording must be transcribed before it can be AI-assessed"
            )
        if self._is_evaluated(evaluation):
            return self._to_response(evaluation)

        transcript = evaluation.get("transcript") or ""
        ai_result = await self._assess_transcript(transcript)
        fields = self._build_ai_fields(transcript, ai_result, evaluation)
        updated = self.repo.update_evaluation(evaluation_id, user_id, fields)

        # Sync downstream systems: mission progress, XP, streak, prediction,
        # readiness score, weak-skill detection, and adaptive scheduling.
        try:
            evaluation_with_context = {**fields, "id": evaluation_id}
            self.mission_service.sync_after_evaluation(
                user_id,
                evaluation_with_context,
                context={
                    "evaluation_id": evaluation_id,
                    "response_id": evaluation.get("response_id"),
                },
            )
            updated["mission_sync"] = "synced"
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "speaking mission sync skipped user=%s eval=%s: %s",
                user_id, evaluation_id, exc,
            )

        return self._to_response(updated)

    def ensure_evaluation(
        self,
        user_id: str,
        evaluation_id: str,
        background_tasks: Any | None = None,
    ) -> dict[str, Any]:
        """Return the evaluation, lazily enqueuing AI assessment on first read.

        When ``background_tasks`` is supplied (e.g. by a read endpoint), a
        transcribed-but-unevaluated record is auto-queued for AI evaluation so
        the assessment materialises without an explicit call. The current
        (still-pending) record is returned immediately for the first poll.
        """
        evaluation = self.repo.get_evaluation(evaluation_id, user_id)
        if not evaluation:
            raise NotFoundError("Speaking evaluation not found")
        if self._is_evaluated(evaluation):
            return self._to_response(evaluation)
        if background_tasks is not None and self._is_transcribed(evaluation):
            background_tasks.add_task(self.evaluate_transcript, user_id, evaluation_id)
        return self._to_response(evaluation)

    def ensure_evaluation_by_response(
        self,
        user_id: str,
        response_id: str,
        background_tasks: Any | None = None,
    ) -> dict[str, Any]:
        """Fetch a response's evaluation, lazily enqueuing AI assessment."""
        evaluation = self.repo.get_evaluation_by_response(response_id, user_id)
        if not evaluation:
            raise NotFoundError("No evaluation record for this response")
        if self._is_evaluated(evaluation):
            return self._to_response(evaluation)
        if background_tasks is not None and self._is_transcribed(evaluation):
            background_tasks.add_task(
                self.evaluate_transcript, user_id, evaluation["id"]
            )
        return self._to_response(evaluation)

    # ------------------------------------------------------------------
    # AI assessment helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_evaluated(evaluation: dict[str, Any]) -> bool:
        return evaluation.get("overall_band") is not None

    @staticmethod
    def _is_transcribed(evaluation: dict[str, Any]) -> bool:
        return (
            evaluation.get("status") == "completed"
            and bool((evaluation.get("transcript") or "").strip())
        )

    async def _assess_transcript(
        self, transcript: str
    ) -> dict[str, Any]:
        """Call the AI service; return {} on failure so fallback is used."""
        try:
            result = await self.ai_service.analyze_speaking(transcript)
            return result or {}
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("AI speaking evaluation failed, using fallback: %s", exc)
            return {}

    def _build_ai_fields(
        self, transcript: str, ai_result: dict[str, Any], evaluation: dict[str, Any]
    ) -> dict[str, Any]:
        """Assemble the AI evaluation columns to persist."""
        used_ai = bool(ai_result)
        band_score = float(ai_result.get("band_score") or 0.0) if used_ai else 0.0
        feedback = ai_result.get("feedback") or ""
        corrections = ai_result.get("corrections") or []
        if used_ai:
            overall_band = _round_band(band_score)
        else:
            overall_band = self._fallback_band(transcript)
        criteria = self._derive_criteria(transcript, overall_band)
        criteria_bands = {k: v["band"] for k, v in criteria.items()}
        word_count = len((transcript or "").split())

        if used_ai:
            source = "ai"
            strengths, weaknesses, suggestions = self._feedback_to_insights(
                feedback, criteria_bands, word_count
            )
        else:
            source = "deterministic_fallback"
            strengths, weaknesses, suggestions = self._fallback_insights(
                criteria_bands, word_count
            )

        return {
            "overall_band": overall_band,
            "confidence": round(_compute_confidence(criteria_bands, word_count), 2),
            "criteria": criteria,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "corrections": list(corrections),
            "suggestions": suggestions,
            "is_estimate": True,
            "source": source,
            "evaluated_at": datetime.utcnow().isoformat(),
            "evaluation_version": int(evaluation.get("evaluation_version") or 0) + 1,
        }

    @staticmethod
    def _fallback_band(transcript: str) -> float:
        """Deterministic overall band from transcript length (no AI)."""
        word_count = len((transcript or "").split())
        if word_count >= 100:
            band = 7.0
        elif word_count >= 50:
            band = 6.0
        elif word_count >= 20:
            band = 5.0
        else:
            band = 4.0
        return _round_band(band)

    def _derive_criteria(
        self, transcript: str, overall_band: float
    ) -> dict[str, dict[str, Any]]:
        """Derive the four IELTS Speaking criterion bands for a transcript.

        Bands stay within +/-0.5 of the overall band and are derived
        deterministically from transcript features so results are reproducible
        without an AI call.
        """
        words = (transcript or "").split()
        word_count = len(words)
        lower = (transcript or "").lower()
        filler_count = sum(lower.count(f) for f in _FILLERS)
        filler_ratio = filler_count / max(1, word_count)
        questions = lower.count("?")
        sentences = max(1, (transcript or "").count(".") + questions)

        bands = {
            # Fluency & Coherence — penalise heavy filler usage.
            "fluency_coherence": overall_band - (0.5 if filler_ratio > 0.02 else 0.0),
            # Lexical Resource — richer vocabulary with longer answers.
            "lexical_resource": (
                overall_band + 0.5 if word_count >= 60
                else overall_band - 0.5 if word_count < 20
                else overall_band
            ),
            # Grammatical Range — longer, more varied responses.
            "grammatical_range_accuracy": (
                overall_band + 0.5 if word_count >= 60 and sentences >= 4 else overall_band
            ),
            # Pronunciation — not inferable from text; floor relative to length.
            "pronunciation": overall_band if word_count >= 20 else overall_band - 0.5,
        }
        labels = {
            "fluency_coherence": "Fluency and Coherence",
            "lexical_resource": "Lexical Resource",
            "grammatical_range_accuracy": "Grammatical Range and Accuracy",
            "pronunciation": "Pronunciation",
        }
        result = {}
        for key in SPEAKING_CRITERIA_KEYS:
            result[key] = {
                "band": _round_band(bands[key]),
                "label": labels[key],
                "strength": "",
                "weakness": "",
                "errors": [],
                "suggestions": [],
            }
        return result

    @staticmethod
    def _feedback_to_insights(
        feedback: str, criteria_bands: dict[str, float], word_count: int
    ) -> tuple[list, list, list]:
        """Map AI feedback text into strengths/weaknesses/suggestions."""
        strengths = [feedback] if feedback else []
        weakest = (
            min(criteria_bands, key=lambda k: criteria_bands[k])
            if criteria_bands else None
        )
        weaknesses = [f"Work on {weakest.replace('_', ' ')}."] if weakest else []
        suggestions = [
            "Practise answering IELTS Speaking Part 1 questions under a timer.",
            "Record yourself and listen for filler words; reduce um/uh usage.",
        ]
        if word_count < 40:
            suggestions.append("Extend your answers with specific personal examples.")
        return strengths, weaknesses, suggestions

    @staticmethod
    def _fallback_insights(criteria_bands, word_count):
        strengths = ["You delivered a structured spoken response."]
        weaknesses = ["Connect an AI provider to unlock detailed per-criterion feedback."]
        suggestions = [
            "Practise describing a topic for a full minute without stopping.",
            "Build topic-specific vocabulary before your test.",
        ]
        if word_count < 40:
            suggestions.append("Extend your answers with specific personal examples.")
        return strengths, weaknesses, suggestions


    # Response projection
    # ------------------------------------------------------------------
    @staticmethod
    def _to_response(evaluation: dict[str, Any]) -> dict[str, Any]:
        """Project a speaking_evaluations row into the API response shape."""
        return {
            "id": evaluation.get("id"),
            "user_id": evaluation.get("user_id"),
            "response_id": evaluation.get("response_id"),
            "session_id": evaluation.get("session_id"),
            "part": evaluation.get("part") or "part_1",
            "audio_url": evaluation.get("audio_url") or "",
            "audio_duration_seconds": int(evaluation.get("audio_duration_seconds") or 0),
            "file_size_bytes": int(evaluation.get("file_size_bytes") or 0),
            "transcript": evaluation.get("transcript") or "",
            "provider": evaluation.get("provider") or "openai_whisper",
            "model": evaluation.get("model") or "whisper-1",
            "status": evaluation.get("status") or "queued",
            "error_message": evaluation.get("error_message") or "",
            "retry_count": int(evaluation.get("retry_count") or 0),
            "last_processed_at": evaluation.get("last_processed_at"),
            "processed_at": evaluation.get("processed_at"),
            "updated_at": evaluation.get("updated_at"),
            # AI Speaking Evaluation (Phase 10).
            "overall_band": evaluation.get("overall_band"),
            "confidence": evaluation.get("confidence"),
            "criteria": evaluation.get("criteria") or {},
            "strengths": evaluation.get("strengths") or [],
            "weaknesses": evaluation.get("weaknesses") or [],
            "corrections": evaluation.get("corrections") or [],
            "suggestions": evaluation.get("suggestions") or [],
            "is_estimate": bool(evaluation.get("is_estimate", True)),
            "source": evaluation.get("source") or "pending",
            "evaluated_at": evaluation.get("evaluated_at"),
            "evaluation_version": int(evaluation.get("evaluation_version") or 0),
        }


# Singleton bound to the shared DB session.
from app.db.session import db_session

speaking_audio_pipeline_service = SpeakingAudioPipelineService(db_session)
