"""
Speech-to-Text service for the Speaking Audio Processing Pipeline.

Responsibilities:
  - Validate audio file uploads (allowed extensions + max file size) before
    they reach storage or the transcription provider.
  - Transcribe audio server-side via the configured provider (OpenAI Whisper
    by default). API keys are read from backend settings only — they are
    never exposed to the frontend.

Providers:
  - "openai"  → POST {STT_API_BASE}/v1/audio/transcriptions (Whisper)
  - "mock"    → deterministic local transcript (no network, useful for tests
                and for running the pipeline without a paid provider)
  - "none"    → transcription disabled; the pipeline marks the evaluation
                failed with a clear, retryable error message
"""
import logging
import re
from typing import Any

from httpx import AsyncClient

from app.core.config import settings
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# MIME → extension mapping used to normalise web uploads before STT.
_CONTENT_TYPE_TO_EXT = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/x-wav": "wav",
    "video/webm": "webm",  # MediaRecorder on some browsers reports video/webm
}


class TranscriptionError(Exception):
    """Raised when the speech-to-text provider fails or is not configured."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


def _allowed_extensions() -> set[str]:
    """Parse the configured extension list into a lowercase set."""
    raw = (settings.STT_ALLOWED_EXTENSIONS or "webm,mp3,mp4,mpeg,mpga,m4a,wav,ogg")
    return {e.strip().lower().lstrip(".") for e in raw.split(",") if e.strip()}


def _extension_from_filename(filename: str) -> str:
    """Return the lowercase extension of a filename ('' if none)."""
    base = (filename or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    match = re.search(r"\.([A-Za-z0-9]{1,10})$", base)
    return match.group(1).lower() if match else ""


def validate_audio_file(
    filename: str,
    content_type: str | None,
    size_bytes: int,
) -> str:
    """
    Validate an audio upload against the configured file-type and size rules.

    Returns the normalised file extension (used for the storage path).

    Raises :class:`ValidationError` when the file type or size is rejected.
    """
    size_bytes = int(size_bytes or 0)
    max_bytes = int(settings.STT_MAX_FILE_SIZE_MB or 25) * 1024 * 1024

    if size_bytes <= 0:
        raise ValidationError("Audio file is empty")

    if size_bytes > max_bytes:
        raise ValidationError(
            f"Audio file is too large ({size_bytes // 1024} KB). "
            f"Maximum allowed size is {settings.STT_MAX_FILE_SIZE_MB} MB."
        )

    # Normalise the extension from either the filename or the MIME type.
    ext = _extension_from_filename(filename) or ""
    if not ext and content_type:
        ext = _CONTENT_TYPE_TO_EXT.get((content_type or "").lower().split(";")[0], "")

    allowed = _allowed_extensions()
    if ext not in allowed:
        raise ValidationError(
            f"Unsupported audio file type '{ext or filename or 'unknown'}'. "
            f"Allowed types: {', '.join(sorted(allowed))}."
        )

    return ext

class SpeechToTextService:
    """Server-side speech-to-text client. Keys live in backend settings only."""

    def __init__(self) -> None:
        self.provider = (settings.STT_PROVIDER or "openai").lower()
        self.model = settings.STT_MODEL or "whisper-1"
        self.api_base = (settings.STT_API_BASE or "https://api.openai.com").rstrip("/")
        self.api_key = settings.OPENAI_API_KEY
        self.retry_attempts = max(0, int(settings.STT_RETRY_ATTEMPTS or 0))

    @property
    def is_configured(self) -> bool:
        """True when a real transcription provider is usable."""
        if self.provider == "mock":
            return True
        return bool(self.api_key)

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Transcribe an audio blob and return the transcript + metadata.

        Returns:
          {"transcript": str, "duration_seconds": float | None,
           "provider": str, "model": str}

        Raises :class:`TranscriptionError` when the provider fails or is not
        configured — callers are expected to record the failure and retry.
        """
        ext = _extension_from_filename(filename)
        safe_name = f"recording.{ext}" if ext else filename or "recording.webm"

        if self.provider == "mock":
            return self._mock_transcript(audio_bytes, safe_name)

        if not self.api_key:
            raise TranscriptionError(
                "Speech-to-text is not configured (missing OPENAI_API_KEY).",
                retryable=False,
            )

        try:
            async with AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.api_base}/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (safe_name, audio_bytes, content_type or "application/octet-stream")},
                    data={
                        "model": self.model,
                        "response_format": "verbose_json",
                        "language": "en",
                        "temperature": 0.0,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning("speech-to-text request failed: %s", exc)
            raise TranscriptionError(f"Transcription request failed: {exc}") from exc

        transcript = str(payload.get("text") or "").strip()
        if not transcript:
            raise TranscriptionError("Transcription returned empty text", retryable=False)

        try:
            duration = float(payload.get("duration") or 0) or None
        except (TypeError, ValueError):
            duration = None

        return {
            "transcript": transcript,
            "duration_seconds": duration,
            "provider": f"{self.provider}:{self.model}",
            "model": self.model,
        }

    def _mock_transcript(self, audio_bytes: bytes, filename: str) -> dict[str, Any]:
        """Deterministic local transcript for tests / provider-free runs."""
        return {
            "transcript": (
                "[Mock transcript] I believe that practicing speaking regularly "
                "helps build confidence and fluency over time. It also allows you "
                "to express your ideas more clearly during the IELTS test."
            ),
            "duration_seconds": max(1.0, len(audio_bytes) / 1024 / 16),  # heuristic
            "provider": "mock:whisper-1",
            "model": self.model,
        }


# Singleton bound to the shared settings.
speech_to_text_service = SpeechToTextService()
