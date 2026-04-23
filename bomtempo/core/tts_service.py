import os
import uuid

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

_TTS_BUCKET = "voice"


class TTSService:
    """
    Text-to-Speech Service using OpenAI TTS-1.
    Uploads audio directly to Supabase Storage bucket 'voice' (public).
    Returns a permanent public URL — no proxy issues, works in dev + production.
    Files can be managed/deleted via Supabase dashboard: Storage > voice.
    """

    @staticmethod
    def generate_speech(text: str) -> str | None:
        """
        Generate speech and upload to Supabase Storage.

        Returns:
            str: Public Supabase Storage URL (e.g. https://xxx.supabase.co/storage/v1/object/public/tts-audio/speech_abc.mp3)
            None: on failure
        """
        if not text:
            return None

        try:
            clean_text = text.replace("**", "").replace("#", "").replace("- ", ". ")
            if len(clean_text) > 1000:
                clean_text = clean_text[:1000] + "..."

            import openai
            from bomtempo.core.ai_client import OPENAI_API_KEY

            api_key = OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not found. TTS skipped.")
                return None

            # Generate audio bytes via OpenAI
            client = openai.Client(api_key=api_key)
            response = client.audio.speech.create(
                model="tts-1", voice="onyx", input=clean_text
            )
            audio_bytes = response.content
            if not audio_bytes:
                logger.error("TTS: OpenAI returned empty content")
                return None

            # Upload to Supabase Storage (ensures bucket exists on first call)
            from bomtempo.core.supabase_client import sb_storage_ensure_bucket, sb_storage_upload

            sb_storage_ensure_bucket(_TTS_BUCKET, public=True)

            filename = f"speech_{uuid.uuid4().hex[:12]}.mp3"
            public_url = sb_storage_upload(
                bucket=_TTS_BUCKET,
                path=filename,
                file_bytes=audio_bytes,
                content_type="audio/mpeg",
            )

            if public_url:
                logger.info(f"TTS uploaded: {public_url}")
                return public_url

            # Fallback: save locally if Supabase upload fails
            logger.warning("TTS: Supabase upload failed, falling back to local file")
            return TTSService._save_local(audio_bytes, filename)

        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def _save_local(audio_bytes: bytes, filename: str) -> str | None:
        """Fallback: save to Reflex uploads dir and return /_upload/ path."""
        try:
            import reflex as rx
            from pathlib import Path
            upload_dir = Path(rx.get_upload_dir())
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_path = upload_dir / filename
            with open(file_path, "wb") as f:
                f.write(audio_bytes)
            if file_path.exists() and file_path.stat().st_size > 0:
                logger.info(f"TTS saved locally: {file_path}")
                return f"/_upload/{filename}"
            return None
        except Exception as e:
            logger.error(f"TTS local fallback failed: {e}")
            return None
