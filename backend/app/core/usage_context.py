import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

_usage_ctx: ContextVar[Optional[Dict[str, Any]]] = ContextVar("usage_context", default=None)

def set_usage_context(
    user_id: Optional[uuid.UUID] = None,
    job_id: Optional[uuid.UUID] = None,
    client_token: Optional[str] = None,
) -> Any:
    """Sets the current task usage context with user and optional research job details."""
    return _usage_ctx.set({
        "user_id": user_id,
        "job_id": job_id,
        "client_token": client_token,
    })

def get_usage_context() -> Optional[Dict[str, Any]]:
    """Returns the current task usage context, or None if not set."""
    return _usage_ctx.get()

def clear_usage_context(token: Any) -> None:
    """Resets the usage context back to its previous state."""
    if token is not None:
        try:
            _usage_ctx.reset(token)
        except Exception:
            _usage_ctx.set(None)

