from typing import Optional, Any
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str = "1.0.0"

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None

