import time

from fastapi import APIRouter
from pydantic import BaseModel

from bomtempo.core.ai_client import ai_client
from bomtempo.core.tts_service import TTSService

voice_router = APIRouter()


class VoiceRequest(BaseModel):
    text: str
    mobile: bool = True


class VoiceResponse(BaseModel):
    text: str
    audio_url: str


@voice_router.post("/process_voice", response_model=VoiceResponse)
def process_voice(request: VoiceRequest):
    """
    Direct API endpoint for Voice Processing.
    Receives Text -> Returns AI Response + Audio URL.
    Used to bypass WebSocket for better Autoplay handling (User Gesture preservation).
    """
    # 1. AI Processing (Reduced Context for Speed/Simplicity)
    # We will use a generic system prompt since accessing GlobalState per-session data is complex via API.

    system_prompt = (
        "Você é o assistente inteligente do Bomtempo Dashboard. "
        "Responda de forma concisa, direta e útil para um gestor de obras. "
        "Foque em respostas curtas (máximo 2 frases) ideais para conversa por voz. "
        "Não use formatação markdown complexa."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.text},
    ]

    # Call OpenAI (Synchronous, runs in threadpool)
    ai_response = ai_client.query(messages)

    # 2. TTS Generation
    audio_path = TTSService.generate_speech(ai_response)

    if audio_path:
        # Append timestamp to prevent browser caching
        audio_url = f"{audio_path}?t={int(time.time())}"
    else:
        audio_url = ""

    return VoiceResponse(text=ai_response, audio_url=audio_url)
