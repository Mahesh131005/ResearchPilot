import os
os.environ["PROVIDER_MODE"] = "mock"

from app.core.config import settings
settings.PROVIDER_MODE = "mock"

import pytest
import io
import pymupdf as fitz
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import get_db, AsyncSessionLocal

@pytest.fixture
def sample_pdf_bytes():
    """Generates a real valid in-memory 2-page PDF document for testing."""
    doc = fitz.open()
    
    # Page 1
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Generative Artificial Intelligence in Indian Banking.\n"
        "Executive Summary: In recent years, generative artificial intelligence has transitioned "
        "from an experimental technology to a strategic driver of digital transformation in financial institutions. "
        "Banks in India, ranging from public sector giants to agile private sector leaders, are actively piloting "
        "large language models for fraud detection, automated customer service, and credit assessment."
    )
    
    # Page 2
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "Key Challenges and Regulatory Compliance.\n"
        "According to guidelines from the Reserve Bank of India, algorithmic governance, customer data privacy, "
        "and explainability are paramount considerations. Financial institutions face major hurdles including data sovereignty, "
        "hallucination risks in customer-facing chatbots, and integration hurdles with legacy core banking platforms."
    )
    
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

@pytest.fixture
async def async_client():
    """Async HTTP test client for FastAPI."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
