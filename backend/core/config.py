"""
Configurações globais do backend FastAPI — Bomtempo Intelligence
Nomes de variáveis de ambiente idênticos ao .env original (sem renomear chaves).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    ROOT_DIR = Path(__file__).parent.parent.parent

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://zobukgyldeiparlwczga.supabase.co")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # ── App ───────────────────────────────────────────────────────────────────
    APP_URL: str = os.getenv("APP_URL", "http://localhost:5173")

    # ── Gmail SMTP ────────────────────────────────────────────────────────────
    RDO_EMAIL_USER: str = os.getenv("RDO_EMAIL_USER", "")
    RDO_EMAIL_PASSWORD: str = os.getenv("RDO_EMAIL_PASSWORD", "")
    RDO_SMTP_SERVER: str = "smtp.gmail.com"
    RDO_SMTP_PORT: int = 587

    # ── OpenAI ────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_VISION_KEY: str = os.getenv("OPENAI_VISION_KEY", "")

    # ── Celery / Redis ────────────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── Storage buckets (inalterados) ─────────────────────────────────────────
    REPORTS_BUCKET: str = "relatorios-pdfs"
    FR_BUCKET_NF: str = "fuel_reimbursements_nf"
    FR_BUCKET_PDF: str = "fuel_reimbursements_pdfs"

    # ── PDF temp dirs ─────────────────────────────────────────────────────────
    RDO_PDF_DIR: Path = Path(os.environ.get("RDO_PDF_DIR", str(Path.home() / ".bomtempo_pdfs")))
    REPORTS_PDF_DIR: Path = Path(os.environ.get("REPORTS_PDF_DIR", str(Path.home() / ".bomtempo_pdfs")))
    FR_PDF_DIR: Path = Path(os.environ.get("FR_PDF_DIR", str(Path.home() / ".bomtempo_pdfs")))

    # ── Brand colors (referência para PDF templates) ──────────────────────────
    BRAND_COLORS = {
        "primary_green": "#0B5B3E",
        "dark_green": "#071D15",
        "light_green": "#0D7050",
        "gold": "#C98B2A",
        "light_gold": "#E0A63B",
        "gold_soft": "#F5D78E",
        "orange": "#E89845",
        "bg_void": "#030504",
        "bg_depth": "#081210",
        "bg_surface": "#0E1A17",
    }

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list = [
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
        os.getenv("APP_URL", ""),
    ]

    # ── Session ───────────────────────────────────────────────────────────────
    SESSION_SECRET_KEY: str = os.getenv("SESSION_SECRET_KEY", "change-me-in-production-please")
    SESSION_MAX_AGE: int = 60 * 60 * 24 * 7  # 7 dias
