"""
Core shared modules for RAG application.

This package contains shared functionality used by both the Streamlit UI (app.py)
and FastAPI service (api.py).
"""

from .config import Settings, get_settings
from .rag import RAGService, RAGResponse

__all__ = ["Settings", "get_settings", "RAGService", "RAGResponse"]
