import re
import uuid
import hashlib
import datetime
import bcrypt
import jwt
from typing import List, Optional, Dict, Any

from app.core.config import settings

# Prompt injection markers
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s*:\s*",
    r"new\s+system\s+instruction",
    r"you\s+are\s+now\s+(unrestricted|DAN|jailbroken)",
    r"bypass\s+(safety|guardrails)",
    r"override\s+system",
]

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validates password complexity:
    - Minimum 10 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special symbol
    Returns (is_valid: bool, message: str).
    """
    if len(password) < 10:
        return False, "Password must be at least 10 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one numerical digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\\/~`]", password):
        return False, "Password must contain at least one special symbol (!@#$%^&*...)."
    return True, "Password meets security requirements"

def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt with salt factor 12."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def hash_token(token: str) -> str:
    """Computes a SHA-256 hash of a token string for secure persistent storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_access_token(data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Creates a signed, time-bounded JWT access token."""
    to_encode = data.copy()
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "iat": now,
        "exp": expire,
        "type": "access",
        "jti": uuid.uuid4().hex,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Creates a signed, time-bounded JWT refresh token."""
    to_encode = data.copy()
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "iat": now,
        "exp": expire,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a JWT token.
    Raises jwt.PyJWTError subclasses (ExpiredSignatureError, InvalidTokenError, etc.) on failure.
    """
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"require": ["exp", "sub", "type"]}
    )

class SecurityAuditor:
    """Detects prompt injection vectors and sanitizes untrusted retrieved content."""

    @staticmethod
    def sanitize_untrusted_content(text: str) -> str:
        """
        Neutralizes potential injection markers in external web text and uploaded PDF content.
        """
        if not text:
            return ""

        sanitized = text
        for pattern in PROMPT_INJECTION_PATTERNS:
            sanitized = re.sub(pattern, "[FLAGGED_CONTENT_REMOVED]", sanitized, flags=re.IGNORECASE)

        # Neutralize control characters
        sanitized = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", sanitized)
        return sanitized.strip()

    @staticmethod
    def format_safe_context(source_label: str, content: str) -> str:
        """
        Wraps untrusted external evidence within cryptographic-style strict isolation boundaries.
        Instructs the LLM that content within boundaries is data, never instructions.
        """
        safe_content = SecurityAuditor.sanitize_untrusted_content(content)
        return (
            f"<<<UNTRUSTED_EVIDENCE_BOUNDARY_START source=\"{source_label}\">>>\n"
            f"{safe_content}\n"
            f"<<<UNTRUSTED_EVIDENCE_BOUNDARY_END>>>"
        )
