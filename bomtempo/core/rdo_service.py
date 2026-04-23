"""
RDO v2 Service — Lógica de negócio para o módulo RDO revampado.

Tabelas novas: rdo_master, rdo2_mao_obra, rdo2_atividades,
               rdo2_equipamentos, rdo2_materiais, rdo2_evidencias
Bucket: rdo-pdfs (existente), rdo-evidencias (novo)
"""

import html as _html_mod
import io
import math
import threading
from datetime import datetime

from typing import Any, Dict, List, Optional, Tuple

from bomtempo.core.ai_client import ai_client
from bomtempo.core.config import Config
from bomtempo.core.logging_utils import get_logger
from bomtempo.core.pdf_utils import html_to_pdf
from bomtempo.core.supabase_client import (
    sb_delete,
    sb_insert,
    sb_select,
    sb_storage_ensure_bucket,
    sb_storage_upload,
    sb_update,
    sb_upsert,
)

logger = get_logger(__name__)

SUPABASE_URL = Config.SUPABASE_URL


# ── Geo utilities ────────────────────────────────────────────────────────────

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in meters between two GPS points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _forward_geocode(address: str) -> tuple:
    """Forward geocode a Brazilian address via Nominatim. Returns (lat, lng) or (0.0, 0.0)."""
    if not address or len(address.strip()) < 5:
        return 0.0, 0.0
    try:
        import httpx
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "br"},
            headers={"User-Agent": "BomtempoRDO/2.0"},
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json()
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        logger.warning(f"Forward geocode falhou: {e}")
    return 0.0, 0.0


def _reverse_geocode(lat: float, lng: float) -> str:
    """Reverse geocode via OpenStreetMap Nominatim. Returns human-readable address."""
    try:
        import httpx
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "json", "lat": lat, "lon": lng, "zoom": 16, "addressdetails": 1},
            headers={"User-Agent": "BomtempoRDO/2.0"},
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            addr = data.get("address", {})
            road   = addr.get("road") or addr.get("pedestrian") or ""
            number = addr.get("house_number") or ""
            suburb = addr.get("suburb") or addr.get("neighbourhood") or ""
            city   = addr.get("city") or addr.get("town") or addr.get("municipality") or ""
            parts  = [f"{road}{', ' + number if number else ''}", suburb, city]
            return ", ".join(p for p in parts if p) or data.get("display_name", "")[:80]
    except Exception as e:
        logger.warning(f"Reverse geocode falhou: {e}")
    return ""


# ── Image utilities ──────────────────────────────────────────────────────────

_PT_MONTHS = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]

def _pt_datetime_str(dt: datetime) -> str:
    """Formata datetime no estilo Auvo: '15 de mar. de 2026, 08:06:15 BRT'."""
    try:
        return f"{dt.day} de {_PT_MONTHS[dt.month-1]}. de {dt.year}, {dt.strftime('%H:%M:%S')} BRT"
    except Exception:
        return dt.strftime("%d/%m/%Y %H:%M:%S")

def _decimal_to_dms(deg: float, is_lat: bool) -> str:
    """Converte graus decimais para formato DMS: '7° 10\' 4\" S'."""
    ref = ("N" if deg >= 0 else "S") if is_lat else ("E" if deg >= 0 else "W")
    deg = abs(deg)
    d = int(deg)
    minutes = (deg - d) * 60
    m = int(minutes)
    s = int(round((minutes - m) * 60))
    return f"{d}° {m}' {s}\" {ref}"

def _fetch_map_thumbnail(lat: float, lng: float, size: Tuple[int,int] = (200, 150)) -> Optional[bytes]:
    """Compõe miniatura de mapa usando tiles OSM diretos + marcador PIL.
    Mais confiável que staticmap.openstreetmap.de (que frequentemente fica offline).
    """
    try:
        import httpx, io as _io, math as _math
        from PIL import Image as _PILImage, ImageDraw as _PILDraw

        ZOOM = 15
        TILE = 256
        n = 2 ** ZOOM

        # Coordenadas do tile central
        tx = int((lng + 180) / 360 * n)
        ty = int((1 - _math.log(_math.tan(_math.radians(lat)) + 1 / _math.cos(_math.radians(lat))) / _math.pi) / 2 * n)

        # Busca 3×3 tiles ao redor (parallel, best-effort)
        tiles: dict = {}
        headers = {"User-Agent": "BomtempoRDO/2.0 (watermark)"}
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                url = f"https://tile.openstreetmap.org/{ZOOM}/{tx+dx}/{ty+dy}.png"
                try:
                    r = httpx.get(url, timeout=4, headers=headers)
                    if r.status_code == 200:
                        tiles[(dx, dy)] = _PILImage.open(_io.BytesIO(r.content)).convert("RGB")
                except Exception:
                    pass

        if not tiles:
            return None

        # Monta imagem 3×3 tiles (768×768)
        canvas = _PILImage.new("RGB", (TILE * 3, TILE * 3), (210, 210, 210))
        for (dx, dy), tile_img in tiles.items():
            canvas.paste(tile_img, ((dx + 1) * TILE, (dy + 1) * TILE))

        # Posição em pixels do ponto exato no canvas 3×3
        fx = (lng + 180) / 360 * n - tx   # fração dentro do tile central (0-1)
        fy = (1 - _math.log(_math.tan(_math.radians(lat)) + 1 / _math.cos(_math.radians(lat))) / _math.pi) / 2 * n - ty
        px = int(TILE + fx * TILE)
        py = int(TILE + fy * TILE)

        # Marcador: pino laranja com borda branca
        draw = _PILDraw.Draw(canvas)
        R = 9
        draw.ellipse([px - R, py - R, px + R, py + R], fill=(201, 139, 42), outline=(255, 255, 255), width=3)
        draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(255, 255, 255))

        # Recorta e redimensiona centrado no marcador
        crop_w, crop_h = size[0] * 3, size[1] * 3
        left = max(0, px - crop_w // 2)
        top  = max(0, py - crop_h // 2)
        right  = min(canvas.width,  left + crop_w)
        bottom = min(canvas.height, top  + crop_h)
        cropped = canvas.crop((left, top, right, bottom))
        result  = cropped.resize(size, _PILImage.LANCZOS)

        buf = _io.BytesIO()
        result.save(buf, format="PNG")
        return buf.getvalue()

    except Exception as e:
        logger.debug(f"Map thumbnail OSM tiles falhou: {e}")
        return None

def _extract_exif_gps(img_bytes: bytes) -> Tuple[float, float]:
    """Extract GPS lat/lng from image EXIF. Returns (0.0, 0.0) if not found."""
    lat, lng, _ = _extract_exif_full(img_bytes)
    return lat, lng


def _extract_exif_full(img_bytes: bytes) -> Tuple[float, float, Optional[datetime]]:
    """Extrai GPS lat/lng + datetime original do EXIF.
    Returns (lat, lng, datetime_local) — valores 0.0/None se não encontrado.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS

        img = Image.open(io.BytesIO(img_bytes))
        exif_raw = img._getexif()  # type: ignore[attr-defined]
        if not exif_raw:
            return 0.0, 0.0, None

        gps_info: Dict[str, Any] = {}
        dt_original: Optional[datetime] = None

        for tag_id, val in exif_raw.items():
            tag_name = TAGS.get(tag_id, "")
            if tag_name == "GPSInfo":
                for k, v in val.items():
                    gps_info[GPSTAGS.get(k, k)] = v
            elif tag_name in ("DateTimeOriginal", "DateTimeDigitized") and dt_original is None:
                # formato EXIF: "2026:03:15 14:38:27"
                try:
                    dt_original = datetime.strptime(str(val), "%Y:%m:%d %H:%M:%S")
                except Exception:
                    pass

        lat, lng = 0.0, 0.0
        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            def _dms(dms, ref: str) -> float:
                d, m, s = [float(x) for x in dms]
                dd = d + m / 60 + s / 3600
                return -dd if ref in ("S", "W") else dd
            lat = _dms(gps_info["GPSLatitude"],  gps_info.get("GPSLatitudeRef",  "N"))
            lng = _dms(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))

        return lat, lng, dt_original
    except Exception as e:
        logger.debug(f"EXIF full extract: {e}")
        return 0.0, 0.0, None


def _apply_watermark(img_bytes: bytes, meta: Dict[str, Any], content_type: str = "image/jpeg") -> bytes:
    """Geolocation audit stamp — full-width bottom panel anchored below the photo.

    Layout:
      ┌────────────────────────────────────────┐
      │            PHOTO (unchanged)           │
      ├══════════════════════════════════════ ═╡  ← copper stripe 4px
      │ TEXT COLUMN (timestamps, GPS, address) │ MAP (35% width, same height) │
      └────────────────────────────────────────┘

    Panel is appended BELOW the image (canvas expands downward) so the photo
    is never cropped or overlaid.

    meta keys:
      rede_time / local_time  – formatted PT timestamps
      local_is_exif / local_is_lastmod – source flags
      lat / lng               – float decimal degrees (optional)
      gps_source              – "exif" | "checkin"
      address / neighborhood / city / postcode – reverse-geocode strings
      contrato / mestre       – RDO metadata
      map_bytes               – bytes|None OSM tile thumbnail
    """
    # ── Resolução padronizada de saída:
    # 1. Cap de processamento (anti-OOM): limita ao processar a 1440px no lado maior.
    # 2. Resolução de saída: normaliza para 1440px no lado MAIOR da FOTO (portrait ou landscape).
    #    - Landscape 4032px wide  → 1440×1080 (+panel)   fsize~45px  ✓ legível
    #    - Portrait  3024×4032px  → 1080×1440 (+panel)   fsize~45px  ✓ legível
    #    - Imagens menores que 1440px: sem upscale, mantidas como estão.
    _MAX_DIM = 1440       # cap de processamento (anti-OOM) — reduzido de 2048 para cortar pico de RAM ~44%
    _OUTPUT_DIM = 1440    # resolução de saída no lado maior da foto — reduzido de 1920

    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        # Corrige orientação EXIF antes do resize (fotos de celular rotacionadas)
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        # Resize se necessário — preserva aspect ratio, cap no maior lado
        w, h = img.size
        if max(w, h) > _MAX_DIM:
            if w >= h:
                new_w, new_h = _MAX_DIM, int(h * _MAX_DIM / w)
            else:
                new_w, new_h = int(w * _MAX_DIM / h), _MAX_DIM
            img = img.resize((new_w, new_h), Image.LANCZOS)

        w, h = img.size

        # Calcula a escala de saída antecipadamente para dimensionar a fonte
        # corretamente em relação ao output final (não ao tamanho de processamento).
        _photo_max = max(w, h)
        _output_scale = (_OUTPUT_DIM / _photo_max) if _photo_max > _OUTPUT_DIM else 1.0
        _out_w = int(w * _output_scale)  # largura efetiva na saída

        # ── Font: proporcional à largura de SAÍDA, mínimo 40px para legibilidade ──
        # Garante texto nítido tanto em portrait (largura ~1440px) quanto landscape (1920px).
        fsize = max(40, _out_w // 32)
        fnt = ImageFont.load_default()
        fnt_sm = ImageFont.load_default()
        for fp in [
            "arial.ttf", "Arial.ttf",
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]:
            try:
                fnt    = ImageFont.truetype(fp, size=fsize)
                fnt_sm = ImageFont.truetype(fp, size=max(22, fsize - 8))
                break
            except Exception:
                continue

        # ── Colors ───────────────────────────────────────────────────────────
        WHITE  = (255, 255, 255, 245)
        COPPER = (201, 139,  42, 255)
        MUTED  = (160, 200, 195, 220)
        YELLOW = (240, 210,  50, 240)
        PANEL  = ( 10,  10,  10, 230)   # near-black, high opacity

        # ── Build text lines ──────────────────────────────────────────────────
        # Each entry: (text, font, color)
        text_entries: List[Tuple[str, Any, Any]] = []

        # Row 1-2: timestamps
        if meta.get("rede_time"):
            text_entries.append((f"Rede:    {meta['rede_time']}", fnt, WHITE))
        if meta.get("local_time"):
            if meta.get("local_is_exif"):
                local_label = "EXIF:    "
            elif meta.get("local_is_lastmod"):
                local_label = "Arquivo: "
            else:
                local_label = "Upload:  "
            text_entries.append((f"{local_label}{meta['local_time']}", fnt, WHITE))

        # Row 3-4: GPS DMS coordinates
        lat = meta.get("lat")
        lng = meta.get("lng")
        gps_src = meta.get("gps_source", "exif")
        if lat and lng:
            gps_color = MUTED if gps_src == "exif" else YELLOW
            text_entries.append((_decimal_to_dms(float(lat), True),  fnt_sm, gps_color))
            text_entries.append((_decimal_to_dms(float(lng), False), fnt_sm, gps_color))
            if gps_src == "checkin":
                text_entries.append(("* GPS via check-in do técnico", fnt_sm, YELLOW))

        # Address block
        if meta.get("address"):
            text_entries.append((str(meta["address"])[:60], fnt_sm, WHITE))
        if meta.get("neighborhood"):
            text_entries.append((str(meta["neighborhood"])[:55], fnt_sm, WHITE))
        if meta.get("city"):
            text_entries.append((str(meta["city"])[:55], fnt_sm, WHITE))
        if meta.get("postcode"):
            text_entries.append((str(meta["postcode"]), fnt_sm, MUTED))

        # Warning only when no EXIF AND no checkin GPS
        has_gps = bool(meta.get("lat") and meta.get("lng"))
        if not meta.get("local_is_exif") and not has_gps:
            if meta.get("local_is_lastmod"):
                text_entries.append(("⚠ Data via lastModified — sem EXIF", fnt_sm, YELLOW))
                text_entries.append(("  Foto pode ser anterior ao upload", fnt_sm, YELLOW))
            else:
                text_entries.append(("⚠ Sem metadados EXIF na foto", fnt_sm, YELLOW))
                text_entries.append(("  Autenticidade não verificável", fnt_sm, YELLOW))

        # Branding footer
        text_entries.append((f"BTP Intelligence · {meta.get('contrato', '—')}", fnt_sm, COPPER))

        # ── Measure text column ───────────────────────────────────────────────
        tmp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        line_h = fsize + max(8, fsize // 5)   # generous line spacing
        pad_x, pad_y = max(24, w // 80), max(16, fsize // 3)

        max_text_w = max(
            (int(tmp_draw.textlength(t, font=f)) for t, f, _ in text_entries),
            default=300,
        )

        # ── Map thumbnail — 30% of image width, uncapped height ─────────────
        text_block_h = len(text_entries) * line_h + pad_y * 2
        map_target_w = int(w * 0.30)
        # Map height matches text block so both columns are the same height
        map_target_h = text_block_h

        map_img = None
        map_bytes_data = meta.get("map_bytes")
        if map_bytes_data and map_target_w > 50 and map_target_h > 40:
            try:
                raw_map = Image.open(io.BytesIO(map_bytes_data)).convert("RGBA")
                raw_map.thumbnail((map_target_w, map_target_h), Image.LANCZOS)
                map_img = raw_map
            except Exception:
                map_img = None

        # ── Panel height: grows to fit ALL content — no cap ───────────────────
        panel_h = max(
            text_block_h,
            (map_img.height + pad_y * 2) if map_img else 0,
        )

        # ── Compose panel (solid dark, font-white — Auvo style) ───────────────
        panel = Image.new("RGBA", (w, panel_h), PANEL)
        draw  = ImageDraw.Draw(panel)

        # Copper accent stripe across top of panel
        stripe = max(3, fsize // 14)
        draw.rectangle([0, 0, w, stripe], fill=(201, 139, 42, 220))

        # Text lines — ALL lines rendered, panel already sized to fit
        y = pad_y + stripe + 2
        for text, fnt_use, clr in text_entries:
            draw.text((pad_x, y), text, font=fnt_use, fill=clr)
            y += line_h

        # Map inset — right column, vertically centred
        if map_img:
            mx = w - map_img.width - pad_x
            my = (panel_h - map_img.height) // 2
            border_px = max(2, fsize // 22)
            brd_w = map_img.width + border_px * 2
            brd_h = map_img.height + border_px * 2
            brd = Image.new("RGBA", (brd_w, brd_h), (201, 139, 42, 180))
            panel.paste(brd, (mx - border_px, my - border_px), brd)
            panel.paste(map_img, (mx, my), map_img)

        # ── Canvas expands BELOW the photo — photo is never overlaid ──────────
        # Total canvas height = photo + panel
        total_h = h + panel_h
        result = Image.new("RGBA", (w, total_h), (10, 10, 10, 255))
        result.paste(img, (0, 0))
        result.paste(panel, (0, h), panel)

        # ── Normaliza resolução de saída: 1920px no lado maior da FOTO ──────────
        # Usa _output_scale calculado no início (baseado em max(w, h) da foto).
        # O painel cresce proporcionalmente — resultado consistente para qualquer
        # orientação (portrait ou landscape). Sem upscale (escala <= 1.0).
        if _output_scale < 1.0:
            out_w = max(1, int(result.width  * _output_scale))
            out_h = max(1, int(result.height * _output_scale))
            result = result.resize((out_w, out_h), Image.LANCZOS)

        buf = io.BytesIO()
        result.convert("RGB").save(buf, format="JPEG", quality=92, optimize=True)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"❌ Watermark falhou (retornando original): {e}")
        return img_bytes


# ── ID Generation ───────────────────────────────────────────────────────────

def _gen_id(contrato: str) -> str:
    import re as _re
    import unicodedata as _ud
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Normaliza unicode (remove acentos, °, etc.) depois mantém só [A-Za-z0-9._-]
    nfkd = _ud.normalize("NFKD", contrato or "RDO")
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    safe = _re.sub(r"[^A-Za-z0-9._-]", "-", ascii_str)
    safe = _re.sub(r"-{2,}", "-", safe).strip("-")[:20]
    return f"RDO2-{safe}-{ts}"


def _gen_view_token() -> str:
    """Generates a URL-safe random token for public RDO viewing."""
    import secrets
    return secrets.token_urlsafe(20)


# ── HTML Builder ────────────────────────────────────────────────────────────

_RDO_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<style>
/* ── Reset & Page Setup ─────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

@page {
  size: A4;
  margin: 0;
}

@page :first {
  margin: 0;
}

body {
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
  background: #F2F4F3;
  font-family: Arial, Helvetica, sans-serif;
  font-size: 12px;
  color: #111;
}

/* ── Page Article ────────────────────────────────────────────── */
.page-wrap {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 32px 0;
  background: #EBEBEB;
}

article {
  width: 210mm;
  min-height: 297mm;
  background: #FAFAFA;
  box-shadow: 0 4px 40px rgba(0,0,0,0.18);
  display: flex;
  flex-direction: column;
  position: relative;
}

/* ── Watermark ──────────────────────────────────────────────── */
.watermark-rdo {
  position: fixed;
  top: 45%; left: 50%;
  transform: translate(-50%,-50%) rotate(-35deg);
  font-size: 72pt; font-weight: 900;
  color: rgba(0,0,0,0.035);
  pointer-events: none; z-index: 999;
  letter-spacing: 8px;
  font-family: Arial, sans-serif;
}

/* ── HEADER ─────────────────────────────────────────────────── */
.doc-header {
  background: #081210;
  padding: 28px 36px 22px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 3px solid #C98B2A;
  position: relative;
  overflow: hidden;
}

.doc-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, rgba(201,139,42,0.08) 0%, transparent 50%);
  pointer-events: none;
}

.header-brand {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  position: relative;
}

.brand-mark {
  width: 52px; height: 52px;
  background: rgba(201,139,42,0.15);
  border: 1.5px solid rgba(201,139,42,0.4);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-mark-inner {
  width: 24px; height: 24px;
  background: #C98B2A;
  clip-path: polygon(50% 0%, 100% 38%, 82% 100%, 18% 100%, 0% 38%);
}

.brand-text h1 {
  font-family: Arial Black, Arial, sans-serif;
  font-size: 18px;
  font-weight: 900;
  color: #FFFFFF;
  letter-spacing: 0.04em;
  line-height: 1;
  text-transform: uppercase;
}

.brand-text .brand-subtitle {
  font-size: 8px;
  color: rgba(255,255,255,0.4);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  margin-top: 5px;
  font-family: Arial, sans-serif;
}

.header-meta {
  text-align: right;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  position: relative;
}

.meta-field-label {
  font-size: 8px;
  color: rgba(255,255,255,0.35);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 1px;
  font-family: Arial, sans-serif;
}

.meta-field-value {
  font-size: 13px;
  font-weight: 700;
  color: #FFFFFF;
  font-family: 'Courier New', monospace;
}

.meta-date {
  font-size: 16px;
  font-weight: 700;
  color: #C98B2A;
  font-family: 'Courier New', monospace;
  letter-spacing: 0.02em;
}

/* ── BODY ─────────────────────────────────────────────────── */
.doc-body {
  padding: 24px 36px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  flex: 1;
}

/* ── Info Grid ─────────────────────────────────────────────── */
.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  border: 1px solid #E2E8E6;
  border-radius: 3px;
  overflow: hidden;
}

.info-cell {
  padding: 9px 12px;
  border-right: 1px solid #E2E8E6;
  border-bottom: 1px solid #E2E8E6;
}

.info-cell:nth-child(4n) { border-right: none; }
.info-cell:nth-last-child(-n+4) { border-bottom: none; }

.info-label {
  font-size: 8px;
  font-weight: 700;
  color: #C98B2A;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-bottom: 3px;
  font-family: Arial, sans-serif;
}

.info-value {
  font-size: 11px;
  font-weight: 600;
  color: #111;
  font-family: Arial, sans-serif;
  word-break: break-word;
}

.info-value.mono {
  font-family: 'Courier New', monospace;
  font-size: 10px;
  color: #444;
}

/* ── KPI Strip ─────────────────────────────────────────────── */
.kpi-strip {
  background: #081210;
  border-radius: 4px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  overflow: hidden;
  page-break-inside: avoid;
}

.kpi-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 8px;
  border-right: 1px solid rgba(255,255,255,0.07);
}

.kpi-cell:last-child { border-right: none; }

.kpi-value {
  font-size: 20px;
  font-weight: 700;
  color: #C98B2A;
  font-family: 'Courier New', monospace;
  line-height: 1;
}

.kpi-label {
  font-size: 7.5px;
  color: rgba(255,255,255,0.4);
  text-transform: uppercase;
  letter-spacing: 0.12em;
  margin-top: 5px;
  font-family: Arial, sans-serif;
  text-align: center;
}

/* ── Section Headers ──────────────────────────────────────── */
.section-h {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding-left: 10px;
  border-left: 3px solid #C98B2A;
}

.section-h.patina { border-left-color: #2A9D8F; }

.section-h h2 {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #081210;
  font-family: Arial Black, Arial, sans-serif;
}

.section-h.patina h2 { color: #1a6b61; }

/* ── GPS Block ─────────────────────────────────────────────── */
.gps-block {
  background: #F0FAF8;
  border: 1px solid #B2DFD9;
  border-radius: 4px;
  padding: 12px 14px;
  page-break-inside: avoid;
}

.gps-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(42,157,143,0.12);
}

.gps-row:last-child { border-bottom: none; }

.gps-pin {
  width: 18px; height: 18px;
  border-radius: 50%;
  background: #C98B2A;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
}

.gps-pin::after {
  content: '▼';
  font-size: 8px;
  color: white;
}

.gps-label {
  font-size: 8px;
  font-weight: 700;
  color: #C98B2A;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.gps-address { font-size: 11px; font-weight: 600; color: #111; }
.gps-coords { font-size: 9px; color: #888; font-family: 'Courier New', monospace; }

/* ── Scope / Orientação ────────────────────────────────────── */
.scope-box {
  background: #FAFAF8;
  border: 1px solid #E8E0D0;
  border-radius: 3px;
  padding: 12px 14px;
  font-size: 11px;
  color: #444;
  line-height: 1.65;
  font-style: italic;
}

/* ── Interruption Warning ──────────────────────────────────── */
.intr-box {
  background: #FEF3F2;
  border: 1px solid #FECACA;
  border-radius: 4px;
  padding: 10px 14px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  page-break-inside: avoid;
}

.intr-icon {
  width: 18px; height: 18px;
  background: #EF4444;
  border-radius: 50%;
  color: white;
  font-weight: 900;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.intr-title {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  color: #B91C1C;
  letter-spacing: 0.06em;
  margin-bottom: 3px;
}

.intr-text { font-size: 11px; color: #7F1D1D; }

/* ── Photo Sections (EPI / Ferramentas) ────────────────────── */
.photo-single {
  page-break-inside: avoid;
}

.photo-single img {
  max-width: 400px;
  height: auto;
  display: block;
  border-radius: 4px;
  border: 1px solid #E2E8E6;
}

/* ── Section page-break wrapper ────────────────────────────── */
.section-wrap {
  page-break-inside: avoid;
  break-inside: avoid;
}

.section-wrap-breakable {
  page-break-inside: auto;
  break-inside: auto;
}

/* ── Activities Table ──────────────────────────────────────── */
.activities-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid #E2E8E6;
  border-radius: 3px;
  overflow: hidden;
}

.activities-table thead {
  background: #081210;
}

.activities-table thead th {
  padding: 9px 12px;
  font-size: 8.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: rgba(255,255,255,0.7);
  text-align: left;
  border-right: 1px solid rgba(255,255,255,0.07);
  font-family: Arial, sans-serif;
}

.activities-table thead th:last-child { border-right: none; }

.activities-table tbody tr { page-break-inside: avoid; }

.activities-table tbody td {
  padding: 9px 12px;
  font-size: 11px;
  border-bottom: 1px solid #F0F0F0;
  border-right: 1px solid #F0F0F0;
  vertical-align: middle;
}

.activities-table tbody td:last-child { border-right: none; }
.activities-table tbody tr:last-child td { border-bottom: none; }

.activities-table tbody tr:nth-child(even) td { background: #F9FAF9; }
.activities-table tbody tr:hover td { background: #F0FAF8; }

.prog-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prog-bar-bg {
  flex: 1;
  height: 5px;
  background: #E8ECEC;
  border-radius: 3px;
  overflow: hidden;
}

.prog-bar-fill {
  height: 100%;
  border-radius: 3px;
}

.prog-pct {
  font-size: 10px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  min-width: 30px;
  text-align: right;
}

.status-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 8.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
  font-family: Arial, sans-serif;
}

.status-chip.done { background: rgba(42,157,143,0.12); color: #2A9D8F; }
.status-chip.progress { background: rgba(201,139,42,0.12); color: #C98B2A; }
.status-chip.pending { background: rgba(239,68,68,0.10); color: #EF4444; }

.table-total-row td {
  background: #F5F0E6 !important;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  color: #6B4F1A;
  letter-spacing: 0.06em;
  border-top: 1.5px solid #C98B2A !important;
  padding: 7px 12px !important;
}

/* ── Evidence Photo Grid ───────────────────────────────────── */
.evidence-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  page-break-inside: auto;
  break-inside: auto;
}

.ev-card {
  border: 1px solid #E2E8E6;
  border-radius: 4px;
  overflow: hidden;
  page-break-inside: avoid;
}

.ev-img-wrap {
  background: #F0F0F0;
  height: 130px;
  overflow: hidden;
}

.ev-img-wrap img {
  width: 100%;
  height: 130px;
  object-fit: cover;
  display: block;
}

.ev-caption {
  padding: 5px 7px;
  border-left: 2px solid #C98B2A;
  background: #FAFAFA;
}

.ev-ts {
  font-size: 8px;
  color: #AAA;
  font-family: 'Courier New', monospace;
  display: block;
  margin-bottom: 1px;
}

.ev-text {
  font-size: 9.5px;
  font-weight: 600;
  color: #333;
  word-break: break-word;
}

.ev-ai {
  font-size: 8.5px;
  color: #2A9D8F;
  font-style: italic;
  margin-top: 2px;
}

/* ── Observations ──────────────────────────────────────────── */
.obs-box {
  background: #FAFAFA;
  border: 1px solid #E2E8E6;
  border-radius: 3px;
  padding: 12px 14px;
  font-size: 11px;
  color: #444;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── AI Analysis ────────────────────────────────────────────── */
.ai-block {
  background: #F0FAF8;
  border: 1px solid #B2DFD9;
  border-left: 3px solid #2A9D8F;
  border-radius: 4px;
  padding: 14px 16px;
  font-size: 11px;
  color: #1a2e2c;
  line-height: 1.7;
  /* Long AI summaries: allow internal breaks, avoid cutting header */
  page-break-inside: auto;
  break-inside: auto;
}

.ai-block h4 {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #2A9D8F;
  margin: 10px 0 4px;
  font-family: Arial Black, Arial, sans-serif;
}

.ai-block h4:first-child { margin-top: 0; }
.ai-block li { margin: 2px 0 2px 14px; }
.ai-block strong { color: #111; font-weight: 700; }

/* ── Signatures ─────────────────────────────────────────────── */
.sig-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 32px;
  page-break-inside: avoid;
  margin-top: 8px;
}

.sig-block {
  text-align: center;
}

.sig-area {
  height: 60px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  margin-bottom: 6px;
}

.sig-area img {
  max-height: 56px;
  display: block;
}

.sig-line {
  width: 100%;
  height: 1px;
  background: #CCC;
  margin-bottom: 8px;
}

.sig-name {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  color: #111;
  letter-spacing: 0.04em;
}

.sig-doc {
  font-size: 8.5px;
  color: #AAA;
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  margin-top: 2px;
}

.sig-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 2px 8px;
  border-radius: 20px;
  background: rgba(42,157,143,0.08);
  border: 1px solid rgba(42,157,143,0.2);
}

.sig-badge-text {
  font-size: 7.5px;
  font-weight: 700;
  color: #2A9D8F;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.sig-rubrica {
  margin-top: 4px;
  font-size: 8px;
  color: #AAA;
}

/* ── FOOTER ─────────────────────────────────────────────────── */
.doc-footer {
  background: #081210;
  padding: 10px 36px;
  border-top: 2px solid #C98B2A;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: auto;
}

.footer-brand {
  font-size: 8px;
  font-weight: 700;
  color: #C98B2A;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  font-family: Arial Black, Arial, sans-serif;
}

.footer-meta {
  font-size: 7px;
  color: rgba(255,255,255,0.3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-family: 'Courier New', monospace;
  text-align: center;
}

.footer-tag {
  font-size: 7.5px;
  font-weight: 700;
  color: rgba(255,255,255,0.5);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: Arial, sans-serif;
}

/* ── Page Break Utilities ─────────────────────────────────── */
.page-break-before { page-break-before: always; }
.page-avoid { page-break-inside: avoid; }

/* ── Print overrides ─────────────────────────────────────── */
@media print {
  body { background: white !important; }
  .page-wrap { padding: 0 !important; background: white !important; }
  article { box-shadow: none !important; }
}
</style>
</head>
<body>
___WATERMARK___
<div class="page-wrap">
<article>

<!-- ── HEADER ──────────────────────────────────────────────── -->
<header class="doc-header">
  <div class="header-brand">
    <div class="brand-mark">
      <div class="brand-mark-inner"></div>
    </div>
    <div class="brand-text">
      <h1>Bomtempo Engenharia</h1>
      <div>
        <p style="font-size:14px;font-weight:700;color:#C98B2A;letter-spacing:0.02em;font-family:Arial Black,Arial,sans-serif;text-transform:uppercase;margin-top:4px;">Relatório Diário de Obra</p>
        <p class="brand-subtitle">Gestão de Campo · BTP Intelligence</p>
        ___PREVIEW_BADGE___
      </div>
    </div>
  </div>
  <div class="header-meta">
    ___STATUS_BADGE___
    <div>
      <p class="meta-field-label">Contrato</p>
      <p class="meta-field-value">___CONTRATO___</p>
    </div>
    <div>
      <p class="meta-field-label">Data do Relatório</p>
      <p class="meta-date">___DATA_RDO___</p>
    </div>
    <div>
      <p class="meta-field-label">Emissão</p>
      <p style="font-size:10px;color:rgba(255,255,255,0.5);font-family:'Courier New',monospace;">___EMISSAO___</p>
    </div>
  </div>
</header>

<!-- ── BODY ────────────────────────────────────────────────── -->
<div class="doc-body">

  <!-- INFO GRID -->
  <section class="page-avoid">
    <div class="info-grid">
      <div class="info-cell">
        <div class="info-label">Projeto</div>
        <div class="info-value">___PROJETO___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Cliente</div>
        <div class="info-value">___CLIENTE___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Localização / Obra</div>
        <div class="info-value">___LOCALIZACAO___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Mestre de Obras</div>
        <div class="info-value">___MESTRE___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Clima</div>
        <div class="info-value">___CLIMA___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Turno</div>
        <div class="info-value">___TURNO___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Horário</div>
        <div class="info-value mono">___H_INI___ – ___H_FIM___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Tipo de Tarefa</div>
        <div class="info-value">___TIPO_TAREFA___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Responsável</div>
        <div class="info-value">___SIGNATORY_NAME___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Doc. (CPF/RG)</div>
        <div class="info-value mono">___SIGNATORY_DOC___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">ID do RDO</div>
        <div class="info-value mono" style="font-size:9px;color:#777;">___ID_RDO___</div>
      </div>
      <div class="info-cell">
        <div class="info-label">Data de Emissão</div>
        <div class="info-value mono" style="font-size:9px;color:#777;">___EMISSAO___</div>
      </div>
    </div>
  </section>

  <!-- KPI STRIP -->
  <div class="kpi-strip page-avoid">
    <div class="kpi-cell">
      <div class="kpi-value">___KPI_ATIVIDADES___</div>
      <div class="kpi-label">Atividades</div>
    </div>
    <div class="kpi-cell">
      <div class="kpi-value">___KPI_FOTOS___</div>
      <div class="kpi-label">Fotos</div>
    </div>
    <div class="kpi-cell">
      <div class="kpi-value">___DURACAO_STR___</div>
      <div class="kpi-label">Duração</div>
    </div>
    <div class="kpi-cell">
      <div class="kpi-value">___KPI_EQUIPE___</div>
      <div class="kpi-label">Equipe Alocada</div>
    </div>
    <div class="kpi-cell">
      <div class="kpi-value">___KPI_KM___</div>
      <div class="kpi-label">KM Percorrido</div>
    </div>
  </div>

  <!-- GPS BLOCK (conditional) -->
  ___GPS_BLOCK___

  <!-- ORIENTAÇÃO / SCOPE (conditional) -->
  ___ORIENTACAO_SECTION___

  <!-- INTERRUPÇÃO (conditional) -->
  ___INTR_SECTION___

  <!-- EPI PHOTO (conditional) -->
  ___EPI_SECTION___

  <!-- ATIVIDADES TABLE -->
  <section class="page-avoid">
    <div class="section-h">
      <h2>Serviços Executados</h2>
    </div>
    <table class="activities-table">
      <thead>
        <tr>
          <th style="width:55%;">Atividade / Descrição</th>
          <th style="width:25%;">Progresso</th>
          <th style="width:20%;text-align:center;">Status</th>
        </tr>
      </thead>
      <tbody>
        ___ACTIVITY_ROWS___
      </tbody>
    </table>
  </section>

  <!-- EVIDÊNCIAS (conditional) -->
  ___PHOTOS_SECTION___

  <!-- OBSERVAÇÕES -->
  <section>
    <div class="section-h">
      <h2>Observações Gerais</h2>
    </div>
    ___OBS_BLOCK___
  </section>

  <!-- FERRAMENTAS PHOTO (conditional) -->
  ___FERRAMENTAS_SECTION___

  <!-- IA ANALYSIS -->
  <section class="page-avoid">
    <div class="section-h patina">
      <h2>Análise Inteligente — BTP AI</h2>
    </div>
    <div class="ai-block">
      ___AI_BLOCK___
    </div>
  </section>

  <!-- ASSINATURAS -->
  <div class="sig-grid">
    <div class="sig-block">
      <div class="sig-area">
        ___SIG_BLOCK___
      </div>
      <div class="sig-line"></div>
      <div class="sig-name">___SIGNATORY_NAME___</div>
      <div class="sig-doc">___SIGNATORY_DOC___</div>
      <div class="sig-badge">
        <span style="color:#2A9D8F;font-size:9px;">✓</span>
        <span class="sig-badge-text">Assinatura Digital</span>
      </div>
    </div>
    <div class="sig-block">
      <div class="sig-area">
        <span style="font-size:10px;color:#CCC;font-style:italic;">Engenheiro / Fiscal</span>
      </div>
      <div class="sig-line"></div>
      <div class="sig-name">Engenheiro Responsável</div>
      <div class="sig-rubrica">Data: ___DATA_RDO___ &nbsp;|&nbsp; Rubrica: _______________</div>
    </div>
  </div>

</div>

<!-- ── FOOTER ───────────────────────────────────────────────── -->
<footer class="doc-footer">
  <span class="footer-brand">Bomtempo Engenharia</span>
  <span class="footer-meta">RDO ___ID_RDO___ · ___CONTRATO___ · ___DATA_RDO___</span>
  <span class="footer-tag">Relatório Diário de Obra</span>
</footer>

</article>
</div>
</body>
</html>"""


class RDOService:

    @staticmethod
    def _e(s) -> str:
        return _html_mod.escape(str(s) if s is not None else "—")

    @staticmethod
    def _fmt_date(d: str) -> str:
        try:
            return datetime.strptime(str(d), "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return str(d) if d else "—"

    @staticmethod
    def _fmt_ts(ts) -> str:
        if not ts:
            return "—"
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(ts)[:16]

    @staticmethod
    def _build_gps_row(label: str, lat, lng, endereco: str, ts, distancia=None) -> str:
        if not lat and not lng:
            return f"""
            <div class="gps-row" style="opacity:0.5;">
              <div class="gps-pin" style="background:#ccc;"></div>
              <div>
                <div class="gps-label">{label}</div>
                <div class="gps-address" style="font-style:italic;color:#999;">Não registrado</div>
              </div>
            </div>"""
        time_str = ""
        if ts:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M")
            except Exception:
                time_str = str(ts)[:5]
        addr = RDOService._e(endereco or f"Lat {float(lat):.6f}, Lng {float(lng):.6f}")
        dist_badge = ""
        if distancia and float(distancia) > 0:
            d = float(distancia)
            d_str = f"{d:.0f} m" if d < 1000 else f"{d/1000:.2f} km"
            clr = "#1d7066" if d <= 100 else ("#8a6d0a" if d <= 300 else "#C0392B")
            dist_badge = f'<span style="display:inline-block;font-size:8px;font-weight:700;padding:1px 6px;border-radius:10px;margin-left:6px;background:{clr}18;color:{clr};border:0.5px solid {clr}50;">{d_str} da obra</span>'
        return f"""
            <div class="gps-row">
              <div class="gps-pin"></div>
              <div style="flex:1;">
                <div class="gps-label">{label}{f' — {time_str}' if time_str else ''}</div>
                <div class="gps-address">{addr}{dist_badge}</div>
                <div class="gps-coords">({float(lat):.6f}, {float(lng):.6f})</div>
              </div>
            </div>"""

    @staticmethod
    def _labor_rows(items: list) -> str:
        e = RDOService._e
        if not items:
            return '<tr><td colspan="3" class="empty-row">Nenhum profissional registrado.</td></tr>'
        rows = [
            f"<tr><td>{e(r.get('profissao', r.get('funcao', '')))}</td>"
            f'<td class="center">{e(r.get("quantidade", r.get("qtd", 1)))}</td>'
            f"<td>{e(r.get('observacoes', r.get('obs', '')) or '—')}</td></tr>"
            for r in items[:30]
        ]
        rows.append(
            f'<tr class="total-row"><td colspan="3">TOTAL: {len(items)} profissional(is) em campo</td></tr>'
        )
        return "\n".join(rows)

    @staticmethod
    def _activity_rows(items: list) -> str:
        e = RDOService._e
        if not items:
            return '<tr><td colspan="3" style="padding:16px;text-align:center;font-style:italic;color:#AAA;font-size:11px;">Nenhuma atividade registrada.</td></tr>'
        rows = []
        for i, r in enumerate(items[:30]):
            pct = int(r.get("progresso_percentual", r.get("percentual", 0)) or 0)
            status = r.get("status", "Em andamento")
            if pct == 100:
                chip_class = "status-chip done"
                chip_text = "CONCLUÍDO"
            elif pct > 0:
                chip_class = "status-chip progress"
                chip_text = e(status).upper()
            else:
                chip_class = "status-chip pending"
                chip_text = e(status).upper()
            prog_color = "#2A9D8F" if pct == 100 else "#C98B2A"
            rows.append(
                f'<tr>'
                f'<td style="font-size:11px;font-weight:600;">{e(r.get("atividade", r.get("descricao", "")))}</td>'
                f'<td>'
                f'<div class="prog-bar-wrap">'
                f'<div class="prog-bar-bg">'
                f'<div class="prog-bar-fill" style="width:{pct}%;background:{prog_color};"></div>'
                f'</div>'
                f'<span class="prog-pct" style="color:{prog_color};">{pct}%</span>'
                f'</div>'
                f'</td>'
                f'<td style="text-align:center;"><span class="{chip_class}">{chip_text}</span></td>'
                f'</tr>'
            )
        rows.append(
            f'<tr class="table-total-row">'
            f'<td colspan="3">Total: {len(items)} atividade(s) registrada(s)</td>'
            f'</tr>'
        )
        return "\n".join(rows)

    @staticmethod
    def _equip_rows(items: list) -> str:
        e = RDOService._e
        if not items:
            return '<tr><td colspan="3" class="empty-row">Nenhum equipamento registrado.</td></tr>'
        rows = []
        for r in items[:25]:
            status = r.get("status", "Operando")
            sc = "badge-done" if status == "Operando" else ("badge-pending" if status == "Parado" else "badge-warn")
            rows.append(
                f"<tr><td>{e(r.get('equipamento', r.get('descricao', '')))}</td>"
                f'<td class="center">{e(r.get("quantidade", 1))}</td>'
                f'<td class="center"><span class="badge {sc}">{e(status)}</span></td></tr>'
            )
        return "\n".join(rows)

    @staticmethod
    def _material_rows(items: list) -> str:
        e = RDOService._e
        if not items:
            return '<tr><td colspan="3" class="empty-row">Nenhum material registrado.</td></tr>'
        return "\n".join(
            f"<tr><td>{e(r.get('material', r.get('descricao', '')))}</td>"
            f'<td class="center">{e(r.get("quantidade", "—"))}</td>'
            f'<td class="center">{e(r.get("unidade", "un"))}</td></tr>'
            for r in items[:25]
        )

    @staticmethod
    def _evidence_grid(items: list) -> str:
        if not items:
            return ""
        cards = []
        for item in items[:24]:
            url = item.get("foto_url", "")
            caption = RDOService._e(item.get("legenda") or "")
            analysis = RDOService._e(item.get("analise_vision") or "")
            ts = RDOService._fmt_ts(item.get("timestamp_foto"))
            ts_html = f'<span class="ev-ts">{ts}</span>' if ts != "—" else ""
            cap_html = f'<span class="ev-text">{caption}</span>' if caption else ""
            ai_html = f'<div class="ev-ai">🤖 {analysis}</div>' if analysis else ""
            cards.append(f"""
            <div class="ev-card">
              <div class="ev-img-wrap">
                <img src="{url}" />
              </div>
              <div class="ev-caption">
                {ts_html}{cap_html}{ai_html}
              </div>
            </div>""")
        return f'<div class="evidence-grid">{"".join(cards)}</div>'

    @staticmethod
    def build_html(rdo_data: Dict[str, Any], is_preview: bool = False) -> str:
        e = RDOService._e

        contrato   = e(rdo_data.get("contrato") or "SEM-CONTRATO")
        data_rdo   = RDOService._fmt_date(rdo_data.get("data") or datetime.now().strftime("%Y-%m-%d"))

        projeto    = e(rdo_data.get("projeto") or "—")
        cliente    = e(rdo_data.get("cliente") or "—")
        localizacao= e(rdo_data.get("localizacao") or "—")
        clima      = e(rdo_data.get("condicao_climatica") or rdo_data.get("clima") or "—")
        turno      = e(rdo_data.get("turno") or "—")
        tipo_tarefa  = e(rdo_data.get("tipo_tarefa") or "Diário de Obra")
        orientacao   = e(rdo_data.get("orientacao") or "")
        km_perc      = rdo_data.get("km_percorrido")
        km_str       = f"{float(km_perc):.2f} km" if km_perc is not None else "—"
        equipe_alocada = rdo_data.get("equipe_alocada")
        equipe_str     = f"{int(equipe_alocada)} pessoa{'s' if int(equipe_alocada) != 1 else ''}" if equipe_alocada else "—"
        houve_intr = bool(rdo_data.get("houve_interrupcao"))
        motivo     = e((rdo_data.get("motivo_interrupcao") or "—")[:120])
        obs        = (rdo_data.get("observacoes") or "").strip()
        id_rdo     = e(rdo_data.get("id_rdo") or "")
        mestre     = e(rdo_data.get("mestre_id") or "")
        emissao    = RDOService._fmt_date(
            str(rdo_data.get("created_at") or rdo_data.get("data") or "")[:10]
            or datetime.now().strftime("%Y-%m-%d")
        )
        signatory_name = e(rdo_data.get("signatory_name") or "")
        signatory_doc  = e(rdo_data.get("signatory_doc") or "")
        signatory_sig_b64 = rdo_data.get("signatory_sig_b64") or ""
        epi_foto_url = rdo_data.get("epi_foto_url") or ""
        ferramentas_foto_url = rdo_data.get("ferramentas_foto_url") or ""
        ai_text    = (rdo_data.get("ai_summary") or "").strip()

        # Computed duration from GPS timestamps
        checkin_ts  = rdo_data.get("checkin_timestamp") or ""
        checkout_ts = rdo_data.get("checkout_timestamp") or ""
        duracao_str = "—"
        h_ini = "—"
        h_fim = "—"
        try:
            if checkin_ts:
                dt_in = datetime.fromisoformat(str(checkin_ts).replace("Z", "+00:00"))
                h_ini = dt_in.strftime("%H:%M")
            if checkout_ts:
                dt_out = datetime.fromisoformat(str(checkout_ts).replace("Z", "+00:00"))
                h_fim = dt_out.strftime("%H:%M")
            if checkin_ts and checkout_ts:
                mins = max(0, int((dt_out - dt_in).total_seconds() / 60))
                duracao_str = f"{mins // 60:02d}h{mins % 60:02d}m"
        except Exception:
            pass

        # Distance in GPS block
        checkin_dist  = rdo_data.get("checkin_distancia_obra") or 0.0
        checkout_dist = rdo_data.get("checkout_distancia_obra") or 0.0

        atividades   = rdo_data.get("atividades", [])
        evidencias   = rdo_data.get("evidencias", [])

        # Sub-sections
        gps_checkin  = RDOService._build_gps_row(
            "Check-in",
            rdo_data.get("checkin_lat"), rdo_data.get("checkin_lng"),
            rdo_data.get("checkin_endereco"), rdo_data.get("checkin_timestamp"),
            distancia=checkin_dist,
        )
        gps_checkout = RDOService._build_gps_row(
            "Check-out",
            rdo_data.get("checkout_lat"), rdo_data.get("checkout_lng"),
            rdo_data.get("checkout_endereco"), rdo_data.get("checkout_timestamp"),
            distancia=checkout_dist,
        )

        activity_rows = RDOService._activity_rows(atividades)
        evidence_html = RDOService._evidence_grid(evidencias)

        obs_block = (
            f'<div class="obs-box">{_html_mod.escape(obs).replace(chr(10), "<br>")}</div>'
            if obs else
            '<p class="empty-row" style="padding:10px 12px;">Sem observações para este dia.</p>'
        )

        # ── Conditional HTML blocks ─────────────────────────────────────────

        # Watermark / preview
        watermark = '<div class="watermark-rdo">RASCUNHO</div>' if is_preview else ""
        preview_badge = (
            '<span style="display:inline-block;background:#dc2626;color:#fff;'
            'font-family:Arial,sans-serif;font-weight:700;font-size:8px;'
            'padding:2px 8px;border-radius:3px;letter-spacing:2px;text-transform:uppercase;margin-top:4px;">'
            'RASCUNHO</span>'
        ) if is_preview else ""

        if is_preview:
            status_badge = (
                '<div style="display:inline-block;padding:3px 10px;'
                'background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.5);'
                'color:#b45309;font-family:\'Courier New\',monospace;'
                'font-size:8px;font-weight:700;border-radius:3px;letter-spacing:0.08em;">'
                'STATUS: RASCUNHO</div>'
            )
        else:
            status_badge = (
                '<div style="display:inline-block;padding:3px 10px;'
                'background:rgba(42,157,143,0.12);border:1px solid rgba(42,157,143,0.4);'
                'color:#2A9D8F;font-family:\'Courier New\',monospace;'
                'font-size:8px;font-weight:700;border-radius:3px;letter-spacing:0.08em;">'
                'STATUS: FINALIZADO</div>'
            )

        # GPS block
        has_gps = rdo_data.get("checkin_lat") or rdo_data.get("checkout_lat")
        if has_gps:
            gps_block = (
                '<section class="page-avoid">'
                '<div class="section-h"><h2>Registro GPS — Presença em Campo</h2></div>'
                '<div class="gps-block">'
                f'{gps_checkin}'
                f'{gps_checkout}'
                '</div></section>'
            )
        else:
            gps_block = ""

        # Orientação / scope
        orientacao_section = (
            '<section>'
            '<div class="section-h"><h2>Escopo / Orientação do Dia</h2></div>'
            f'<div class="scope-box">{orientacao}</div>'
            '</section>'
        ) if orientacao else ""

        # Interrupção
        intr_section = (
            '<div class="intr-box page-avoid">'
            '<div class="intr-icon">!</div>'
            '<div>'
            '<p class="intr-title">Interrupção Registrada</p>'
            f'<p class="intr-text">{motivo}</p>'
            '</div></div>'
        ) if houve_intr else ""

        # EPI photo
        epi_section = (
            '<section class="photo-single page-avoid">'
            '<div class="section-h"><h2>Equipe com EPIs</h2></div>'
            f'<img src="{epi_foto_url}" style="max-width:420px;height:auto;display:block;border-radius:4px;border:1px solid #E2E8E6;" />'
            '</section>'
        ) if epi_foto_url else ""

        # Ferramentas photo
        ferramentas_section = (
            '<section class="photo-single page-avoid">'
            '<div class="section-h"><h2>Ferramentas Limpas e Organizadas</h2></div>'
            f'<img src="{ferramentas_foto_url}" style="max-width:420px;height:auto;display:block;border-radius:4px;border:1px solid #E2E8E6;" />'
            '</section>'
        ) if ferramentas_foto_url else ""

        # Photos
        if evidencias:
            photos_section = (
                '<section>'
                '<div class="section-h">'
                f'<h2>Evidências de Campo ({len(evidencias)} foto{"s" if len(evidencias) != 1 else ""})</h2>'
                '</div>'
                f'{evidence_html}'
                '</section>'
            )
        else:
            photos_section = ""

        # Observations
        if obs:
            obs_block = (
                f'<div class="obs-box">{_html_mod.escape(obs)}</div>'
            )
        else:
            obs_block = (
                '<p style="font-size:11px;font-style:italic;color:#AAA;padding:8px 0;">Sem observações para este dia.</p>'
            )

        # AI block
        if ai_text:
            def _md_simple(text: str) -> str:
                import re
                lines = []
                for line in text.split("\n"):
                    line = _html_mod.escape(line)
                    line = re.sub(r"^## (.+)$", r'<h4>\1</h4>', line)
                    line = re.sub(r"^\s*[-•]\s(.+)$", r'<li>\1</li>', line)
                    line = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', line)
                    lines.append(line)
                html_out = "\n".join(lines)
                html_out = re.sub(r"(<li[^>]*>.*?</li>\n?)+", lambda m: f"<ul style='margin:4px 0 6px 14px;padding:0;'>{m.group(0)}</ul>", html_out)
                return html_out
            ai_block = _md_simple(ai_text)
        else:
            ai_block = '<p style="font-style:italic;color:#888;font-size:11px;">⏳ Análise sendo processada…</p>'

        # Signature
        if signatory_sig_b64 and signatory_sig_b64.startswith("data:"):
            sig_block = f'<img src="{signatory_sig_b64}" style="max-height:56px;display:block;" />'
        else:
            sig_block = '<span style="font-size:10px;color:#CCC;font-style:italic;">Assinatura digital pendente</span>'

        # ── Apply replacements to template ──────────────────────────────────
        replacements = {
            "___WATERMARK___":         watermark,
            "___PREVIEW_BADGE___":     preview_badge,
            "___STATUS_BADGE___":      status_badge,
            "___CONTRATO___":          contrato,
            "___DATA_RDO___":          data_rdo,
            "___PROJETO___":           projeto,
            "___CLIENTE___":           cliente,
            "___LOCALIZACAO___":       localizacao,
            "___MESTRE___":            mestre,
            "___CLIMA___":             clima,
            "___TURNO___":             turno,
            "___H_INI___":             h_ini,
            "___H_FIM___":             h_fim,
            "___TIPO_TAREFA___":       tipo_tarefa,
            "___SIGNATORY_NAME___":    signatory_name or "—",
            "___SIGNATORY_DOC___":     signatory_doc or "—",
            "___ID_RDO___":            id_rdo,
            "___EMISSAO___":           emissao,
            "___KPI_ATIVIDADES___":    str(len(atividades)),
            "___KPI_FOTOS___":         str(len(evidencias)),
            "___DURACAO_STR___":       duracao_str,
            "___KPI_KM___":            km_str,
            "___KPI_EQUIPE___":        equipe_str,
            "___GPS_BLOCK___":         gps_block,
            "___ORIENTACAO_SECTION___": orientacao_section,
            "___INTR_SECTION___":      intr_section,
            "___EPI_SECTION___":       epi_section,
            "___ACTIVITY_ROWS___":     activity_rows,
            "___PHOTOS_SECTION___":    photos_section,
            "___OBS_BLOCK___":         obs_block,
            "___FERRAMENTAS_SECTION___": ferramentas_section,
            "___AI_BLOCK___":          ai_block,
            "___SIG_BLOCK___":         sig_block,
        }
        html = _RDO_HTML_TEMPLATE
        for key, val in replacements.items():
            html = html.replace(key, str(val) if val is not None else "")
        return html

    # ── PDF Generation ──────────────────────────────────────────────────────

    @staticmethod
    def generate_pdf(
        rdo_data: Dict[str, Any],
        is_preview: bool = False,
        id_rdo: str = "",
    ) -> tuple:
        """Returns (pdf_path: str, pdf_url: str)."""
        try:
            Config.RDO_PDF_DIR.mkdir(parents=True, exist_ok=True)
            contrato = rdo_data.get("contrato", "X")
            data     = rdo_data.get("data", datetime.now().strftime("%Y-%m-%d"))

            if is_preview:
                filename = f"RDO2-PREVIEW-{contrato}-{data}.pdf"
            elif id_rdo:
                filename = f"{id_rdo}.pdf"
            else:
                filename = f"RDO2-{contrato}-{data}.pdf"

            pdf_path = Config.RDO_PDF_DIR / filename
            html = RDOService.build_html(rdo_data, is_preview=is_preview)
            html_to_pdf(
                html, pdf_path,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                display_header_footer=False,
            )
            logger.info(f"✅ RDO2 PDF gerado: {pdf_path.name}")
            return str(pdf_path), ""
        except Exception as e:
            logger.error(f"❌ generate_pdf: {e}")
            return "", ""

    # ── Database operations ──────────────────────────────────────────────────

    @staticmethod
    def upsert_draft(rdo_data: Dict[str, Any], mestre_id: str = "") -> str:
        """Upsert rdo_master com status=rascunho. Retorna id_rdo."""
        id_rdo = rdo_data.get("id_rdo") or _gen_id(rdo_data.get("contrato", ""))
        # Preserve existing view_token if record already exists
        existing_token = ""
        try:
            ex = sb_select("rdo_master", filters={"id_rdo": id_rdo}, limit=1)
            if ex:
                existing_token = ex[0].get("view_token") or ""
        except Exception:
            pass
        view_token = existing_token or _gen_view_token()
        record = {
            "id_rdo":              id_rdo,
            "status":              "rascunho",
            "contrato":            rdo_data.get("contrato") or "",
            "projeto":             rdo_data.get("projeto") or "",
            "cliente":             rdo_data.get("cliente") or "",
            "localizacao":         rdo_data.get("localizacao") or "",
            "data":                rdo_data.get("data") or datetime.now().strftime("%Y-%m-%d"),
            "turno":               rdo_data.get("turno") or "Diurno",
            "hora_inicio":         rdo_data.get("hora_inicio") or "07:00",
            "hora_termino":        rdo_data.get("hora_termino") or "17:00",
            "tipo_tarefa":         rdo_data.get("tipo_tarefa") or "Diário de Obra",
            "orientacao":          rdo_data.get("orientacao") or "",
            "km_percorrido":       rdo_data.get("km_percorrido"),
            "condicao_climatica":  rdo_data.get("condicao_climatica") or rdo_data.get("clima") or "Ensolarado",
            "houve_interrupcao":   bool(rdo_data.get("houve_interrupcao")),
            "motivo_interrupcao":  rdo_data.get("motivo_interrupcao") or "",
            "equipe_alocada":      rdo_data.get("equipe_alocada"),
            "observacoes":         rdo_data.get("observacoes") or "",
            "checkin_timestamp":   rdo_data.get("checkin_timestamp"),
            "checkin_lat":         rdo_data.get("checkin_lat"),
            "checkin_lng":         rdo_data.get("checkin_lng"),
            "checkin_endereco":    rdo_data.get("checkin_endereco") or "",
            "checkout_lat":        rdo_data.get("checkout_lat"),
            "checkout_lng":        rdo_data.get("checkout_lng"),
            "checkout_endereco":   rdo_data.get("checkout_endereco") or "",
            "checkout_timestamp":  rdo_data.get("checkout_timestamp"),
            "signatory_name":      rdo_data.get("signatory_name") or "",
            "signatory_doc":       rdo_data.get("signatory_doc") or "",
            "signatory_sig_b64":   rdo_data.get("signatory_sig_b64") or "",
            "epi_foto_url":        rdo_data.get("epi_foto_url") or "",
            "ferramentas_foto_url": rdo_data.get("ferramentas_foto_url") or "",
            "mestre_id":           mestre_id or rdo_data.get("mestre_id") or "",
            "houve_chuva":         bool(rdo_data.get("houve_chuva")),
            "quantidade_chuva":    rdo_data.get("quantidade_chuva") or "",
            "houve_acidente":      bool(rdo_data.get("houve_acidente")),
            "descricao_acidente":  rdo_data.get("descricao_acidente") or "",
            "view_token":          view_token,
            "updated_at":          datetime.now().isoformat(),
            "client_id":           rdo_data.get("client_id") or None,
        }
        record = {k: v for k, v in record.items() if v is not None}
        sb_upsert("rdo_master", record, on_conflict="id_rdo")
        RDOService._save_sub_items(id_rdo, rdo_data)
        return id_rdo

    @staticmethod
    def mark_processing(id_rdo: str) -> None:
        """Marca RDO como processando_pdf antes da geração do PDF.

        Permite distinguir RDOs que falharam durante processamento (crash/OOM)
        de rascunhos genuínos. Status flow: rascunho → processando_pdf → finalizado.
        Se o servidor crashar durante PDF, o RDO fica em 'processando_pdf'
        e pode ser identificado e reprocessado pelo usuário no histórico.
        """
        from bomtempo.core.supabase_client import sb_update
        try:
            sb_update("rdo_master", filters={"id_rdo": id_rdo}, data={"status": "processando_pdf"})
        except Exception:
            pass  # best-effort — não impede o fluxo principal

    @staticmethod
    def finalize_rdo(
        id_rdo: str,
        pdf_path: str,
        pdf_url: str,
        rdo_data: Dict[str, Any],
    ) -> bool:
        """Marca RDO como finalizado e salva PDF + checkout + assinatura."""
        patch: Dict[str, Any] = {
            "status":           "finalizado",
            "pdf_path":         pdf_path,
            "pdf_url":          pdf_url,
            "updated_at":       datetime.now().isoformat(),
        }
        for field in [
            "checkout_timestamp", "checkout_lat", "checkout_lng", "checkout_endereco",
            "assinatura_url", "assinatura_nome",
        ]:
            if rdo_data.get(field) is not None:
                patch[field] = rdo_data[field]
        return sb_update("rdo_master", {"id_rdo": id_rdo}, patch)

    @staticmethod
    def update_pdf_info(id_rdo: str, pdf_url: str) -> bool:
        return sb_update("rdo_master", {"id_rdo": id_rdo}, {"pdf_url": pdf_url})

    @staticmethod
    def upload_pdf(pdf_path: str, id_rdo: str) -> str:
        try:
            with open(pdf_path, "rb") as f:
                data = f.read()
            safe_id = RDOService._safe_storage_key(id_rdo)
            url = sb_storage_upload("rdo-pdfs", f"{safe_id}.pdf", data, "application/pdf")
            return url or ""
        except Exception as e:
            logger.error(f"❌ upload_pdf: {e}")
            return ""

    @staticmethod
    def _safe_storage_key(s: str) -> str:
        """Sanitiza string para uso seguro como path no Supabase Storage."""
        import re as _re
        import unicodedata as _ud
        nfkd = _ud.normalize("NFKD", s or "")
        ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
        return _re.sub(r"[^A-Za-z0-9._/-]", "-", ascii_str)

    @staticmethod
    def upload_evidence(id_rdo: str, file_bytes: bytes, content_type: str, filename: str) -> str:
        """Upload foto para bucket rdo-evidencias (auto-criado se não existir). Retorna URL pública."""
        try:
            sb_storage_ensure_bucket("rdo-evidencias", public=True)
            safe_id = RDOService._safe_storage_key(id_rdo)
            safe_filename = RDOService._safe_storage_key(filename)
            path = f"{safe_id}/{safe_filename}"
            url = sb_storage_upload("rdo-evidencias", path, file_bytes, content_type)
            return url or ""
        except Exception as e:
            logger.error(f"❌ upload_evidence: {e}")
            return ""

    @staticmethod
    def save_evidence(id_rdo: str, foto_url: str, legenda: str = "") -> Optional[Dict]:
        try:
            rdo_rows = sb_select("rdo_master", filters={"id_rdo": id_rdo}, limit=1)
            if not rdo_rows:
                logger.warning(f"⚠️ save_evidence: rdo_master not found for id_rdo={id_rdo}")
                return None
            rdo_uuid = rdo_rows[0]["id"]
            return sb_insert("rdo_evidencias", {
                "rdo_id":   rdo_uuid,
                "foto_url": foto_url,
                "legenda":  legenda,
            })
        except Exception as e:
            logger.warning(f"⚠️ save_evidence (non-fatal): {e}")
            return None

    @staticmethod
    def get_full_rdo(id_rdo: str) -> Dict[str, Any]:
        rows = sb_select("rdo_master", filters={"id_rdo": id_rdo})
        if not rows:
            return {}
        rdo = dict(rows[0])
        rdo_uuid = rdo.get("id")  # UUID PK — used as FK in sub-tables
        if rdo_uuid:
            rdo["atividades"] = sb_select("rdo_atividades", filters={"rdo_id": rdo_uuid}) or []
            rdo["evidencias"] = sb_select("rdo_evidencias", filters={"rdo_id": rdo_uuid}) or []
        else:
            rdo["atividades"] = []
            rdo["evidencias"] = []
        return rdo

    @staticmethod
    def get_by_token(view_token: str) -> Dict[str, Any]:
        rows = sb_select("rdo_master", filters={"view_token": view_token})
        if not rows:
            return {}
        return RDOService.get_full_rdo(rows[0]["id_rdo"])

    @staticmethod
    def get_rdos_list(
        contrato: str = "",
        mestre_id: str = "",
        limit: int = 100,
        client_id: str = "",
    ) -> List[Dict[str, Any]]:
        filters: Dict[str, Any] = {}
        if contrato:
            filters["contrato"] = contrato
        if mestre_id:
            filters["mestre_id"] = mestre_id
        if client_id:
            filters["client_id"] = client_id
        return sb_select("rdo_master", filters=filters, order="created_at.desc", limit=limit) or []

    @staticmethod
    def get_active_draft(mestre_id: str, contrato: str = "", client_id: str = "") -> Optional[Dict[str, Any]]:
        """Retorna rascunho ativo do mestre (se existir).

        Considera tanto 'rascunho' quanto 'processando_pdf' — este último indica
        um RDO que foi enviado mas o servidor crashou durante a geração do PDF.
        O usuário pode reabrir e reenviar normalmente.
        """
        # raw_filters permite usar PostgREST in() para múltiplos valores
        raw: Dict[str, str] = {
            "status":    "in.(rascunho,processando_pdf)",
            "mestre_id": f"eq.{mestre_id}",
        }
        if contrato:
            raw["contrato"] = f"eq.{contrato}"
        if client_id:
            raw["client_id"] = f"eq.{client_id}"
        rows = sb_select("rdo_master", raw_filters=raw, order="updated_at.desc", limit=1)
        return dict(rows[0]) if rows else None

    @staticmethod
    def get_all_rdos(limit: int = 500, client_id: str = "") -> List[Dict[str, Any]]:
        """Retorna todos os RDOs finalizados do tenant. Alias para get_rdos_list sem filtros."""
        filters: Dict[str, Any] = {}
        if client_id:
            filters["client_id"] = client_id
        return sb_select("rdo_master", filters=filters, order="created_at.desc", limit=limit) or []

    @staticmethod
    def delete_draft(id_rdo: str) -> bool:
        return sb_delete("rdo_master", {"id_rdo": id_rdo})

    # ── Geocoding utilities ──────────────────────────────────────────────────

    @staticmethod
    def backfill_obras_geocode(dry_run: bool = False) -> dict:
        """Forward-geocode all obras rows that have Localização but no lat/lng.
        Returns {"updated": N, "failed": N, "skipped": N}.
        Safe to run multiple times (skips rows that already have coords).
        """
        import time
        rows = sb_select("contratos", limit=500)
        updated = failed = skipped = 0
        for r in rows:
            if r.get("lat") or not r.get("localizacao"):
                skipped += 1
                continue
            address = str(r["localizacao"]).strip()
            lat, lng = _forward_geocode(address)
            if lat:
                if not dry_run:
                    sb_update("contratos", {"id": r.get("id")}, {"lat": lat, "lng": lng})
                updated += 1
                logger.info(f"✅ Geocoded '{address}' → {lat:.5f}, {lng:.5f}")
            else:
                failed += 1
                logger.warning(f"⚠️  Geocode sem resultado: '{address}'")
            time.sleep(1.1)  # Nominatim rate-limit: 1 req/s
        return {"updated": updated, "failed": failed, "skipped": skipped}

    # ── Obra GPS coords ──────────────────────────────────────────────────────

    @staticmethod
    def get_obra_coords(contrato: str) -> Tuple[float, float]:
        """Look up lat/lng from contratos for a given contrato. Returns (0, 0) if missing."""
        if not contrato:
            return 0.0, 0.0
        try:
            rows = sb_select("contratos", filters={"contrato": contrato}, limit=1)
            if rows:
                r = rows[0]
                lat = float(r.get("lat") or r.get("latitude") or 0.0)
                lng = float(r.get("lng") or r.get("longitude") or 0.0)
                return lat, lng
        except Exception as e:
            logger.warning(f"get_obra_coords({contrato}): {e}")
        return 0.0, 0.0

    # ── Evidence pipeline ─────────────────────────────────────────────────────

    @staticmethod
    def process_evidence(
        id_rdo: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        legenda: str,
        mestre: str,
        contrato: str,
        data: str,
        checkin_lat: float = 0.0,
        checkin_lng: float = 0.0,
        checkin_endereco: str = "",
        client_exif_lat: float = 0.0,
        client_exif_lng: float = 0.0,
        client_exif_datetime: str = "",
        client_last_modified: str = "",
    ) -> Dict[str, str]:
        allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
        if content_type.lower() not in allowed_types:
            logger.warning(f"⚠️ Upload bloqueado: MIME type {content_type} não permitido para evidências.")
            return {"foto_url": "", "legenda": legenda, "exif_lat": "", "exif_lng": "", "exif_endereco": ""}

        # Sanitize filename to prevent path traversal
        import os
        safe_filename = os.path.basename(filename)

        # 1. Extract EXIF (GPS + datetime) from image
        exif_lat, exif_lng, exif_dt = _extract_exif_full(file_bytes)

        # 2. Resolve GPS: prefer client-supplied EXIF, fallback to server EXIF, then check-in
        lat = client_exif_lat or exif_lat or checkin_lat
        lng = client_exif_lng or exif_lng or checkin_lng
        gps_source = "checkin" if (not client_exif_lat and not exif_lat and checkin_lat) else "exif"

        # 3. Timestamps
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        rede_time = _pt_datetime_str(now_utc)
        if client_exif_datetime:
            try:
                local_dt = datetime.fromisoformat(client_exif_datetime.replace("Z", "+00:00"))
                local_time = _pt_datetime_str(local_dt)
                local_is_exif = True
                local_is_lastmod = False
            except Exception:
                local_time = client_exif_datetime
                local_is_exif = True
                local_is_lastmod = False
        elif exif_dt:
            local_time = _pt_datetime_str(exif_dt)
            local_is_exif = True
            local_is_lastmod = False
        elif client_last_modified:
            try:
                lm_ms = int(client_last_modified)
                lm_dt = datetime.fromtimestamp(lm_ms / 1000, tz=timezone.utc)
                local_time = _pt_datetime_str(lm_dt)
            except Exception:
                local_time = client_last_modified
            local_is_exif = False
            local_is_lastmod = True
        else:
            local_time = rede_time
            local_is_exif = False
            local_is_lastmod = False

        # 4. Map thumbnail (best-effort)
        map_bytes = _fetch_map_thumbnail(lat, lng) if (lat and lng) else None

        # 5. Reverse-geocode for watermark address
        wm_address = checkin_endereco or ""
        if lat and lng and not wm_address:
            try:
                wm_full = _reverse_geocode(lat, lng)
                wm_address = wm_full
            except Exception:
                pass
        addr_parts = wm_address.split(", ") if wm_address else []
        wm_neighborhood = addr_parts[1] if len(addr_parts) > 1 else ""
        wm_city = addr_parts[-1] if addr_parts else ""

        # 6. Apply watermark
        meta: Dict[str, Any] = {
            "rede_time":       rede_time,
            "local_time":      local_time,
            "local_is_exif":   local_is_exif,
            "local_is_lastmod": local_is_lastmod,
            "lat":             lat or None,
            "lng":             lng or None,
            "gps_source":      gps_source,
            "address":         wm_address,
            "neighborhood":    wm_neighborhood,
            "city":            wm_city,
            "contrato":        contrato,
            "mestre":          mestre,
            "map_bytes":       map_bytes,
        }
        try:
            watermarked = _apply_watermark(file_bytes, meta, content_type)
        except Exception as wm_err:
            logger.warning(f"⚠️ Watermark falhou (usando original): {wm_err}")
            watermarked = file_bytes

        # 7. Upload to Supabase Storage
        # Watermark salva como JPEG (RGB, quality=92) — menor e compatível com browsers.
        upload_ct = "image/jpeg"
        name_base = os.path.splitext(safe_filename)[0]
        upload_filename = f"{name_base}.jpg"
        foto_url = RDOService.upload_evidence(id_rdo, watermarked, upload_ct, upload_filename)
        if not foto_url:
            # Upload falhou — retorna dict vazio para o caller filtrar
            return {"foto_url": "", "legenda": legenda, "exif_lat": "", "exif_lng": "", "exif_endereco": ""}

        # 8. Reverse geocode EXIF GPS (reuse wm_address already computed above)
        exif_endereco = wm_address or ""
        if not exif_endereco and exif_lat and exif_lng:
            exif_endereco = _reverse_geocode(exif_lat, exif_lng)

        # 9. Persist to rdo_evidencias (best-effort)
        rdo_master_rows = sb_select("rdo_master", filters={"id_rdo": id_rdo}, limit=1)
        rdo_uuid = rdo_master_rows[0]["id"] if rdo_master_rows else None
        if rdo_uuid:
            record: Dict[str, Any] = {
                "rdo_id":   rdo_uuid,
                "foto_url": foto_url,
                "legenda":  legenda,
            }
            try:
                sb_insert("rdo_evidencias", record)
            except Exception as db_err:
                logger.warning(f"⚠️ rdo_evidencias insert (non-fatal): {db_err}")

        return {
            "foto_url":      foto_url,
            "legenda":       legenda,
            "exif_lat":      str(exif_lat) if exif_lat else "",
            "exif_lng":      str(exif_lng) if exif_lng else "",
            "exif_endereco": exif_endereco,
        }

    # ── AI ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_ai_prompt(rdo_data: Dict[str, Any]) -> list:
        """Build the Claude messages list for RDO analysis."""
        def _fmt_act(r: Dict[str, Any]) -> str:
            nome = r.get('atividade') or r.get('descricao') or '?'
            status = r.get('status', 'Em andamento')
            pct_raw = str(r.get('progresso_percentual', '') or '').strip()
            efetivo = r.get('efetivo') or r.get('efetivo_alocado') or 0
            exec_qty = r.get('exec_qty') or r.get('producao_dia') or 0
            total_qty = r.get('total_qty', 0) or 0
            unidade = r.get('unidade', '') or ''
            # Marco: pct == 0 mas status concluído → trata como binário
            if pct_raw in ('0', '0.0', '') and status in ('Concluído', 'Concluido', 'concluido'):
                sufixo = '✅ Marco concluído'
            elif exec_qty and total_qty:
                sufixo = f'{exec_qty}/{total_qty} {unidade}'.strip() + f' — {pct_raw}%' if pct_raw else ''
            elif pct_raw and pct_raw not in ('0', '0.0'):
                sufixo = f'{pct_raw}%'
            elif pct_raw in ('0', '0.0', ''):
                sufixo = '⬜ Marco / Não iniciado'
            else:
                sufixo = f'{pct_raw}%'
            equipe_info = f' ({efetivo} pessoa(s))' if efetivo else ''
            return f'  - {nome}: {sufixo} [{status}]{equipe_info}'

        acts = "\n".join(_fmt_act(r) for r in rdo_data.get("atividades", [])[:10])
        checkin_ts   = rdo_data.get("checkin_timestamp") or ""
        checkout_ts  = rdo_data.get("checkout_timestamp") or ""
        checkin_end  = rdo_data.get("checkin_endereco") or ""
        checkout_end = rdo_data.get("checkout_endereco") or ""
        gps_info = ""
        if checkin_ts:
            gps_info += f"\nCheck-in: {checkin_ts[:16]} @ {checkin_end}"
        if checkout_ts:
            gps_info += f"\nCheck-out: {checkout_ts[:16]} @ {checkout_end}"
        n_fotos = len(rdo_data.get("evidencias", []))

        text_prompt = f"""Você é um consultor sênior de engenharia civil. Analise o RDO abaixo e forneça uma análise executiva concisa.

RDO {rdo_data.get('id_rdo','')} — {rdo_data.get('data','')}
Contrato: {rdo_data.get('contrato','')} | Projeto: {rdo_data.get('projeto','')}
Cliente: {rdo_data.get('cliente','')}
Clima: {rdo_data.get('condicao_climatica','')} | Turno: {rdo_data.get('turno','')}
Interrupção: {'SIM — ' + (rdo_data.get('motivo_interrupcao') or '') if rdo_data.get('houve_interrupcao') else 'NÃO'}
GPS:{gps_info or ' não registrado'}
Fotos de evidência: {n_fotos}
Serviços Executados:\n{acts or '  (não informados)'}
Observações: {(rdo_data.get('observacoes') or 'Nenhuma')[:400]}
Orientações/Pendências: {(rdo_data.get('orientacao') or 'Nenhuma')[:300]}

Responda em português, de forma direta e objetiva, com as seções:
## 📊 RESUMO EXECUTIVO
(2-3 frases sobre o dia de trabalho)
## 🔨 SERVIÇOS EXECUTADOS
(bullet points dos principais serviços e progresso)
## ⚠️ ALERTAS E RISCOS
(riscos identificados, se houver — caso nenhum, diga "Nenhum risco identificado")
## 💡 RECOMENDAÇÕES
(1-2 recomendações práticas)"""

        # Build multimodal message: text + up to 4 photo URLs for vision
        photo_urls = [
            e.get("foto_url", "")
            for e in (rdo_data.get("evidencias") or [])
            if e.get("foto_url", "").startswith("http")
        ][:4]

        # Análise somente texto — evita filtros de segurança que bloqueiam URLs externas de imagem.
        # A análise executiva baseia-se nos dados estruturados do RDO, não nas fotos.
        user_msg: Any = {"role": "user", "content": text_prompt}
        _ = photo_urls  # reservado para uso futuro com vision opt-in

        return [
            {
                "role": "system",
                "content": (
                    "Você é um assistente especializado em gestão de obras e engenharia civil. "
                    "Analisa Relatórios Diários de Obra (RDO) da empresa Bomtempo. "
                    "Seja preciso, direto e profissional. Responda sempre em português brasileiro. "
                    "Limite cada seção a 3-5 linhas. Não recuse solicitações — este é um contexto "
                    "empresarial legítimo de gestão de construção civil."
                ),
            },
            user_msg,
        ]

    @staticmethod
    def analyze_now(rdo_data: Dict[str, Any], id_rdo: str) -> str:
        """Synchronous AI analysis — runs in calling thread, returns result string.
        Call from run_in_executor to avoid blocking the event loop."""
        try:
            messages = RDOService._build_ai_prompt(rdo_data)
            result = ai_client.query(messages)
            if result:
                sb_update("rdo_master", {"id_rdo": id_rdo}, {"ai_summary": result})
                logger.info(f"✅ AI summary salvo: {id_rdo}")
            return result or ""
        except Exception as e:
            logger.error(f"❌ AI analyze_now: {e}")
            return ""

    @staticmethod
    def analyze_with_ai(rdo_data: Dict[str, Any], id_rdo: str) -> None:
        """Fire-and-forget: analisa RDO e salva ai_summary no banco."""
        def _run():
            RDOService.analyze_now(rdo_data, id_rdo)
        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def send_email(
        recipients: List[str],
        rdo_data: Dict[str, Any],
        pdf_path: str,
        view_url: str,
        ai_text: str = "",
    ) -> None:
        """Fire-and-forget email send."""
        from bomtempo.core.email_service import EmailService

        def _run():
            try:
                EmailService.send_rdo2_email(recipients, rdo_data, pdf_path, view_url, ai_text)
            except Exception as e:
                logger.error(f"❌ send_email rdo2: {e}")

        threading.Thread(target=_run, daemon=True).start()

    # ── Private ──────────────────────────────────────────────────────────────

    @staticmethod
    def _save_sub_items(id_rdo: str, rdo_data: Dict[str, Any]) -> None:
        try:
            # Resolve rdo_id UUID from rdo_master (the FK column is 'rdo_id', not 'id_rdo')
            rdo_master_rows = sb_select("rdo_master", filters={"id_rdo": id_rdo}, limit=1)
            if not rdo_master_rows:
                logger.warning(f"_save_sub_items: rdo_master not found for id_rdo={id_rdo}")
                return
            rdo_uuid = rdo_master_rows[0]["id"]

            try:
                sb_delete("rdo_atividades", {"rdo_id": rdo_uuid})
            except Exception as _del_err:
                logger.warning(f"_save_sub_items: sb_delete falhou (continuando): {_del_err}")

            for item in (rdo_data.get("atividades") or []):
                atv = item.get("atividade") or item.get("descricao") or ""
                if atv:
                    try:
                        sb_insert("rdo_atividades", {
                            "rdo_id":    rdo_uuid,
                            "atividade": atv,
                            "efetivo":   int(item.get("efetivo") or item.get("progresso_percentual") or 0),
                            "observacao": item.get("status") or item.get("observacao") or "",
                        })
                    except Exception as _ins_err:
                        logger.warning(f"_save_sub_items: sb_insert '{atv[:40]}' falhou: {_ins_err}")
        except Exception as e:
            logger.error(f"_save_sub_items: erro inesperado: {e}", exc_info=True)


# ── Startup geocode backfill ─────────────────────────────────────────────────

def ensure_geocodes_async() -> None:
    """Run backfill_obras_geocode in a daemon thread at startup (fire-and-forget).
    Only geocodes obras rows that have Localização but no lat/lng yet.
    Safe to call multiple times — skips rows that already have coordinates.

    SQL migrations needed before this module can save new fields:
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS signatory_name text DEFAULT '';
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS signatory_doc text DEFAULT '';
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS signatory_sig_b64 text DEFAULT '';
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS epi_foto_url text DEFAULT '';
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS ferramentas_foto_url text DEFAULT '';
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS checkout_lat float8;
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS checkout_lng float8;
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS checkout_endereco text DEFAULT '';
        ALTER TABLE rdo_master ADD COLUMN IF NOT EXISTS checkout_timestamp timestamptz;
    """
    def _run():
        try:
            result = RDOService.backfill_obras_geocode()
            logger.info(f"🌐 Geocode backfill: {result}")
        except Exception as e:
            logger.warning(f"⚠️ Geocode backfill error: {e}")

    threading.Thread(target=_run, daemon=True).start()


# Run geocode backfill at module import (no-op if all obras already have coords)
ensure_geocodes_async()
