import re
from typing import List, Optional

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s*:\s*",
    r"new\s+system\s+instruction",
    r"you\s+are\s+now\s+(unrestricted|DAN|jailbroken)",
    r"bypass\s+(safety|guardrails)",
    r"override\s+system",
]

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
