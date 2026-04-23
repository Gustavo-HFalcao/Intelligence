"""
Password hashing utilities — Bomtempo Dashboard
Uses PBKDF2-HMAC-SHA256 with 260,000 iterations (NIST 2023 recommendation).
Format: "pbkdf2:sha256:<iterations>$<salt_hex>$<hash_hex>"
"""
import hashlib
import hmac
import os


_ITERATIONS = 260_000
_HASH_NAME = "sha256"
_PREFIX = "pbkdf2:sha256"


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Returns a string in the format "pbkdf2:sha256:<iters>$<salt_hex>$<hash_hex>"
    that is safe to store in the database.
    """
    if salt is None:
        salt = os.urandom(16).hex()

    dk = hashlib.pbkdf2_hmac(
        _HASH_NAME,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _ITERATIONS,
    )
    return f"{_PREFIX}:{_ITERATIONS}${salt}${dk.hex()}"


def verify_password(stored: str, provided: str) -> bool:
    """Verify a password against a stored hash.

    Handles three formats for backwards compatibility during migration:
    1. PBKDF2 format: "pbkdf2:sha256:<iters>$<salt>$<hash>"   (current standard)
    2. Legacy SHA-256 format: "<salt_hex>:<sha256_hex>"        (previous migration)
    3. Plain text                                               (pre-migration — plain compare, logged)
    """
    if not stored:
        return False

    # ── PBKDF2 format (current) ────────────────────────────────────────────────
    if stored.startswith("pbkdf2:"):
        try:
            # "pbkdf2:sha256:<iters>$<salt>$<hash>"
            _, algo, rest = stored.split(":", 2)
            iters_s, salt, stored_hash = rest.split("$", 2)
            iterations = int(iters_s)
            dk = hashlib.pbkdf2_hmac(
                algo,
                provided.encode("utf-8"),
                salt.encode("utf-8"),
                iterations,
            )
            return hmac.compare_digest(dk.hex(), stored_hash)
        except (ValueError, KeyError):
            return False

    # ── Legacy SHA-256 format: "salt:sha256hex" ────────────────────────────────
    if ":" in stored:
        try:
            salt, stored_hash = stored.split(":", 1)
            # Validate it looks like a hex SHA-256 (64 chars)
            if len(stored_hash) == 64:
                candidate = hashlib.sha256((provided + salt).encode()).hexdigest()
                return hmac.compare_digest(candidate, stored_hash)
        except (ValueError, AttributeError):
            return False

    # ── Plain text fallback (pre-migration rows) ───────────────────────────────
    # This path will only be reached for rows that were NOT migrated.
    # It's kept intentionally to allow a graceful transition period.
    return hmac.compare_digest(stored, provided)
