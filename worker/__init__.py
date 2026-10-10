"""
Worker izolat de extragere a textului din documente PDF/DOCX (arhitectură orchestrator + worker).
"""

from worker.extractor import (
    ExtractConfig,
    ExtractResult,
    PageText,
    detect_language,
    extract_document,
    resolve_tesseract,
)
from worker.ai_adapter import AIConfig, analyze_text, build_prompt, parse_ai_json
from worker.xmp_injector import InjectResult, inject_metadata

__all__ = [
    "ExtractConfig",
    "ExtractResult",
    "PageText",
    "detect_language",
    "extract_document",
    "resolve_tesseract",
    "AIConfig",
    "analyze_text",
    "build_prompt",
    "parse_ai_json",
    "InjectResult",
    "inject_metadata",
]
