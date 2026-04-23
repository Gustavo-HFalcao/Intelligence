import re
import unicodedata
from typing import Any, Dict, Optional

import httpx

from bomtempo.core.logging_utils import get_logger

logger = get_logger(__name__)

# Brazilian state abbreviations
_BR_STATES = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

# Address prefixes that mean the value is a street/road, not a city
_ADDR_PREFIXES = re.compile(
    r"^(ROD\.?|AV\.?|RUA|R\.|ESTRADA|BR[-\s]|CE[-\s]|PE[-\s]|SP[-\s]|"
    r"MG[-\s]|BA[-\s]|GO[-\s]|PR[-\s]|RS[-\s]|MA[-\s]|PA[-\s]|TO[-\s]|"
    r"AL[-\s]|SC[-\s]|RN[-\s]|PI[-\s]|TRAVESSA|BECO|LARGO|SETOR|N[°º]|SN\b)",
    re.IGNORECASE,
)


def _extract_city_from_address(raw: str) -> str:
    """
    Extract the most useful city/search term from a raw address string.

    Strategies (tried in order):
    1. If input looks like a plain city name (no address keywords) — return as-is
    2. Regex: find "CIDADE / UF" or "CIDADE, UF" pattern anywhere in string
    3. Regex: find "CIDADE / UF" or "CIDADE, UF" after a comma or slash
    4. Last comma-segment that doesn't start with a number or address prefix
    5. Return first word that isn't a known address keyword
    """
    s = raw.strip()

    # Strategy 1: Already looks like a city (no road/address keywords)
    if not _ADDR_PREFIXES.search(s) and "/" not in s and len(s.split()) <= 4:
        return s

    # Strategy 2: Pattern "CIDADE / UF" or "CIDADE, UF" (Brazilian standard)
    # e.g. "GUAIÚBA / CE" or "Recife, PE"
    m = re.search(
        r"([A-ZÀ-Ú][A-ZÀ-Ú\s]{2,30})\s*/\s*([A-Z]{2})\b",
        s,
        re.IGNORECASE,
    )
    if m:
        city, state = m.group(1).strip(), m.group(2).upper()
        if state in _BR_STATES:
            return f"{city}, {state}"

    # Strategy 3: "CIDADE, UF" pattern
    m = re.search(
        r"([A-ZÀ-Ú][A-ZÀ-Ú\s]{2,30}),\s*([A-Z]{2})\b",
        s,
        re.IGNORECASE,
    )
    if m:
        city, state = m.group(1).strip(), m.group(2).upper()
        if state in _BR_STATES:
            return f"{city}, {state}"

    # Strategy 4: last comma-segment that isn't a road/number
    parts = [p.strip() for p in re.split(r"[,/]", s)]
    for part in reversed(parts):
        part_clean = part.strip()
        if (
            part_clean
            and not _ADDR_PREFIXES.search(part_clean)
            and not re.match(r"^\d", part_clean)
            and len(part_clean) > 3
        ):
            # Remove trailing state abbreviation if separate token
            tokens = part_clean.split()
            if len(tokens) >= 2 and tokens[-1].upper() in _BR_STATES:
                return part_clean  # keep "Guaiuba CE" together
            return part_clean

    # Strategy 5: fallback — return raw, let the API try
    return s

# Recife Coordinates
LAT = -8.05428
LON = -34.8813
TIMEZONE = "America/Sao_Paulo"


async def get_forecast(lat: float = LAT, lon: float = LON) -> Optional[Dict[str, Any]]:
    """
    Fetches weather data from Open-Meteo API.
    Returns structured data for widget or None if fails.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min",
        "timezone": TIMEZONE,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params, timeout=5.0)
            response.raise_for_status()
            data = response.json()

            # Process data for UI
            return {
                "temp": int(data["current"]["temperature_2m"]),
                "rain": data["current"]["precipitation"],
                "wind": data["current"]["wind_speed_10m"],
                "code": data["current"]["weather_code"],
                # Daily arrays
                "daily_time": data["daily"]["time"],  # ['2023-10-27', ...]
                "daily_rain_sum": data["daily"]["precipitation_sum"],
                "daily_rain_prob": data["daily"]["precipitation_probability_max"],
                "daily_max": data["daily"]["temperature_2m_max"],
                "daily_min": data["daily"]["temperature_2m_min"],
            }

    except Exception as e:
        logger.error(f"Weather API Error: {e}")
        return None


def _normalize_search(name: str) -> str:
    """Strip accents and clean for Open-Meteo geocoding API."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Known encoding corruption fix
    ascii_name = ascii_name.replace("Joo Pessoa", "Joao Pessoa")
    return ascii_name.strip()


async def _geocode_one(client: httpx.AsyncClient, search_name: str) -> Optional[Dict[str, Any]]:
    """Single geocoding attempt — returns result dict or None."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    normed = _normalize_search(search_name)
    try:
        resp = await client.get(
            url,
            params={"name": normed, "count": 3, "language": "pt", "format": "json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results") or []
        # Prefer Brazil results
        for r in results:
            if r.get("country_code", "").upper() == "BR":
                return {
                    "lat": r["latitude"],
                    "lon": r["longitude"],
                    "name": f"{r['name']}, {r.get('admin1', '')}",
                }
        # Any result if no BR found
        if results:
            r = results[0]
            return {
                "lat": r["latitude"],
                "lon": r["longitude"],
                "name": f"{r['name']}, {r.get('admin1', '')}",
            }
    except Exception:
        pass
    return None


async def get_coordinates(city_name: str) -> Optional[Dict[str, Any]]:
    """
    Geocodes a location string (city name OR full address) to lat/lon.

    Tries multiple strategies so that even messy address fields like
    "ROD CE 060, N°. SN BAIRRO: DIST IND DE GUAIUBA, GUAIUBA / CE"
    resolve to a usable coordinate.
    """
    logger.info(f"Geocoding: '{city_name}'")

    # Build a cascade of search candidates
    extracted = _extract_city_from_address(city_name)
    candidates = []

    # Candidate 1: smart-extracted city (may include "City, UF")
    if extracted and extracted.lower() != city_name.lower():
        candidates.append(extracted)

    # Candidate 2: just the city name part (before comma/slash)
    city_part = re.split(r"[,/]", extracted)[0].strip()
    if city_part and city_part not in candidates:
        candidates.append(city_part)

    # Candidate 3: original (fallback)
    orig_clean = city_name.split(",")[0].strip()
    if orig_clean not in candidates:
        candidates.append(orig_clean)

    # Candidate 4: raw original
    if city_name.strip() not in candidates:
        candidates.append(city_name.strip())

    async with httpx.AsyncClient(timeout=12.0) as client:
        for candidate in candidates:
            if not candidate or len(candidate) < 3:
                continue
            result = await _geocode_one(client, candidate)
            if result:
                logger.info(f"Geocoded '{city_name}' via '{candidate}' -> {result['name']}")
                return result
            logger.debug(f"Geocode miss for candidate: '{candidate}'")

    logger.warning(f"Geocode sem resultado para todas as tentativas: '{city_name}'")
    return None


def get_risk_level(data: Dict[str, Any]) -> str:
    """Calculates risk level based on precipitation."""
    if not data:
        return "Unknown"

    today_rain = data.get("daily_rain_sum", [0])[0]
    today_prob = data.get("daily_rain_prob", [0])[0]
    current_rain = data.get("rain", 0)

    if current_rain > 5 or today_rain > 15 or today_prob > 80:
        return "High"
    if current_rain > 0.5 or today_rain > 5 or today_prob > 50:
        return "Medium"
    return "Low"
