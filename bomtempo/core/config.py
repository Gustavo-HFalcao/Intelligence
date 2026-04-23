"""
Configurações globais do projeto BOMTEMPO (Reflex)
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()


class Config:
    """Configurações centralizadas"""

    # Diretórios
    ROOT_DIR = Path(__file__).parent.parent.parent  # bomtempo-dashboard/
    ASSETS_DIR = ROOT_DIR / "assets"

    # ── RDO Configuration ────────────────────────────────────────────────────────
    # RDO dados 100% no Supabase — sem Google Sheets nem SQLite para RDO

    # Diretório para PDFs gerados — FORA da pasta do projeto para não
    # acionar o file-watcher do Reflex (que recompila o frontend)
    RDO_PDF_DIR = Path(os.environ.get("RDO_PDF_DIR", str(Path.home() / ".bomtempo_pdfs")))

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://zobukgyldeiparlwczga.supabase.co")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_hGsFo0P6OSkrFBPWbNLnCw_cn7ESLlx")

    # App base URL (used for absolute links in emails)
    # Set APP_URL=https://bomtempo.com.br when that domain goes live
    APP_URL = os.getenv("APP_URL", "https://bomtempo-blue-ocean.reflex.run")

    # Gmail SMTP Configuration (via variáveis de ambiente)
    RDO_EMAIL_USER = os.getenv("RDO_EMAIL_USER", "rdos@bomtempo.com.br")
    RDO_EMAIL_PASSWORD = os.getenv("RDO_EMAIL_PASSWORD", "")
    RDO_SMTP_SERVER = "smtp.gmail.com"
    RDO_SMTP_PORT = 587

    # ── Reports ───────────────────────────────────────────────────────────────
    REPORTS_PDF_DIR = Path(os.environ.get("REPORTS_PDF_DIR", str(Path.home() / ".bomtempo_pdfs")))
    REPORTS_BUCKET = "relatorios-pdfs"

    # ── Fuel Reimbursement (FR) ────────────────────────────────────────────────
    FR_PDF_DIR = Path(os.environ.get("FR_PDF_DIR", str(Path.home() / ".bomtempo_pdfs")))
    FR_BUCKET_NF = "fuel_reimbursements_nf"
    FR_BUCKET_PDF = "fuel_reimbursements_pdfs"
    OPENAI_VISION_KEY = os.getenv("OPENAI_VISION_KEY", "")

    # Data sintética
    USE_SYNTHETIC_DATA = False
    SYNTHETIC_MULTIPLIER = 3
    SYNTHETIC_SEED = 42

    # Brand colors ref
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
