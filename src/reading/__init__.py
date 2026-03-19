"""
Reading module for file ingestion and LLM-assisted schema interpretation.

This module handles:
- File ingestion (CSV and XLSX)
- LLM-assisted reading layer for schema interpretation
- Schema mapping generation (without modifying raw data)
"""

from .file_ingestion import read_file, FileType
from .reading_assistant import ReadingAssistant, SchemaMapping

__all__ = [
    "read_file",
    "FileType",
    "ReadingAssistant",
    "SchemaMapping",
]
