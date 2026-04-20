"""
RDO Service — geo utilities, EXIF watermark, PDF generation, view_token.
Heavy operations (PIL, PDF) run in thread pool via asyncio.run_in_executor.
"""

import io
import math
import secrets
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from backend.core.logging import get_logger

logger = get_logger(__name__)

_PT_MONTHS = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"]


# ── Geo ─────────────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def reverse_geocode(lat: float, lng: float) -> str:
    try:
        import httpx
        r = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "json", "lat": lat, "lon": lng, "zoom": 16, "addressdetails": 1},
            headers={"User-Agent": "BomtempoRDO/2.0"},
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
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


def fetch_map_thumbnail(lat: float, lng: float, size: Tuple[int,int] = (200, 150)) -> Optional[bytes]:
    try:
        import httpx, io as _io
        from PIL import Image as _PILImage, ImageDraw as _PILDraw

        ZOOM = 15
        TILE = 256
        n = 2 ** ZOOM
        tx = int((lng + 180) / 360 * n)
        ty = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)

        tiles: dict = {}
        headers = {"User-Agent": "BomtempoRDO/2.0 (watermark)"}
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                url = f"https://tile.openstreetmap.org/{ZOOM}/{tx+dx}/{ty+dy}.png"
                try:
                    resp = httpx.get(url, timeout=4, headers=headers)
                    if resp.status_code == 200:
                        tiles[(dx, dy)] = _PILImage.open(_io.BytesIO(resp.content)).convert("RGB")
                except Exception:
                    pass

        if not tiles:
            return None

        canvas = _PILImage.new("RGB", (TILE * 3, TILE * 3), (210, 210, 210))
        for (dx, dy), tile_img in tiles.items():
            canvas.paste(tile_img, ((dx + 1) * TILE, (dy + 1) * TILE))

        fx = (lng + 180) / 360 * n - tx
        fy = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n - ty
        px = int(TILE + fx * TILE)
        py = int(TILE + fy * TILE)

        draw = _PILDraw.Draw(canvas)
        R = 9
        draw.ellipse([px-R, py-R, px+R, py+R], fill=(201,139,42), outline=(255,255,255), width=3)
        draw.ellipse([px-3, py-3, px+3, py+3], fill=(255,255,255))

        crop_w, crop_h = size[0]*3, size[1]*3
        left = max(0, px - crop_w//2)
        top  = max(0, py - crop_h//2)
        right  = min(canvas.width, left+crop_w)
        bottom = min(canvas.height, top+crop_h)
        result = canvas.crop((left, top, right, bottom)).resize(size)

        buf = _io.BytesIO()
        result.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.debug(f"Map thumbnail falhou: {e}")
        return None


def extract_exif_full(img_bytes: bytes) -> Tuple[float, float, Optional[datetime]]:
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
                try:
                    dt_original = datetime.strptime(str(val), "%Y:%m:%d %H:%M:%S")
                except Exception:
                    pass

        lat, lng = 0.0, 0.0
        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            def _dms(dms, ref: str) -> float:
                d, m, s = [float(x) for x in dms]
                dd = d + m/60 + s/3600
                return -dd if ref in ("S","W") else dd
            lat = _dms(gps_info["GPSLatitude"],  gps_info.get("GPSLatitudeRef",  "N"))
            lng = _dms(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))

        return lat, lng, dt_original
    except Exception as e:
        logger.debug(f"EXIF extract: {e}")
        return 0.0, 0.0, None


def apply_watermark(img_bytes: bytes, meta: Dict[str, Any], content_type: str = "image/jpeg") -> bytes:
    """Append geolocation audit panel below photo."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        W, H = img.size

        panel_h = max(100, int(H * 0.22))
        map_w   = int(W * 0.35)

        canvas = Image.new("RGB", (W, H + panel_h), (15, 20, 30))
        canvas.paste(img, (0, 0))

        # copper stripe
        stripe_h = 4
        stripe = Image.new("RGB", (W, stripe_h), (201, 139, 42))
        canvas.paste(stripe, (0, H))

        draw = ImageDraw.Draw(canvas)

        # text area
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        rede_time  = meta.get("rede_time",  "—")
        local_time = meta.get("local_time", "—")
        lat        = meta.get("lat", 0.0)
        lng        = meta.get("lng", 0.0)
        address    = meta.get("address", "")
        contrato   = meta.get("contrato", "")

        lines = [
            f"Horário rede: {rede_time}",
            f"Horário local: {local_time}",
            f"GPS: {lat:.6f}, {lng:.6f}" if (lat or lng) else "GPS: não disponível",
            address[:60] if address else "",
            f"Contrato: {contrato}" if contrato else "",
        ]
        y = H + stripe_h + 6
        text_w = W - map_w - 8
        for line in lines:
            if not line:
                continue
            draw.text((6, y), line, fill=(220, 200, 160), font=font)
            y += 14

        # map thumbnail
        map_bytes = meta.get("map_bytes")
        if map_bytes:
            try:
                map_img = Image.open(io.BytesIO(map_bytes)).resize((map_w, panel_h - stripe_h))
                canvas.paste(map_img, (W - map_w, H + stripe_h))
            except Exception:
                pass

        buf = io.BytesIO()
        fmt = "JPEG" if "jpeg" in content_type.lower() or "jpg" in content_type.lower() else "PNG"
        canvas.save(buf, format=fmt, quality=88)
        return buf.getvalue()
    except Exception as e:
        logger.warning(f"Watermark falhou: {e}")
        return img_bytes


def generate_view_token() -> str:
    return secrets.token_urlsafe(32)
