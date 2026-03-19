"""
LLM-Assisted Reading Assistant for schema interpretation.

This module uses LLM to interpret inconsistent schemas without modifying
raw customer data values. It only suggests canonical mappings.

CRITICAL: Data Immutability Rule
- The LLM MUST NOT modify raw customer data values
- It may only interpret schema and suggest mappings
- Original data remains untouched
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

from .file_ingestion import read_file, get_schema_info


# Load environment variables
def _load_env() -> None:
    """Load .env file from repo root."""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)


@dataclass
class ColumnMapping:
    """Mapping from original column name to canonical name."""
    original_name: str
    canonical_name: str
    confidence: float  # 0.0 to 1.0
    field_type: str  # "dimension", "metric", "metadata", "uncertain"
    notes: Optional[str] = None


@dataclass
class ValueMapping:
    """Mapping from original categorical value to canonical value."""
    column_name: str
    original_value: str
    canonical_value: str
    confidence: float  # 0.0 to 1.0


@dataclass
class SchemaMapping:
    """
    Schema mapping result from LLM-assisted reading.
    
    This contains only metadata about mappings - no actual data values.
    The original dataset remains untouched.
    """
    column_mappings: List[ColumnMapping] = field(default_factory=list)
    value_mappings: List[ValueMapping] = field(default_factory=list)
    uncertain_fields: List[str] = field(default_factory=list)
    additional_fields: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "column_mappings": [
                {
                    "original_name": m.original_name,
                    "canonical_name": m.canonical_name,
                    "confidence": m.confidence,
                    "field_type": m.field_type,
                    "notes": m.notes,
                }
                for m in self.column_mappings
            ],
            "value_mappings": [
                {
                    "column_name": m.column_name,
                    "original_value": m.original_value,
                    "canonical_value": m.canonical_value,
                    "confidence": m.confidence,
                }
                for m in self.value_mappings
            ],
            "uncertain_fields": self.uncertain_fields,
            "additional_fields": self.additional_fields,
            "notes": self.notes,
        }


class ReadingAssistant:
    """
    LLM-Assisted Reading Assistant for schema interpretation.
    
    This class uses LLM to interpret inconsistent schemas and suggest
    canonical mappings. It does NOT modify raw customer data values.
    
    Architecture position:
    - Runs BEFORE the deterministic insight engine
    - Interprets schema only (column names, categorical values)
    - Returns mapping metadata, not modified data
    """
    
    def __init__(self, model: Optional[str] = None):
        """
        Initialize the Reading Assistant.
        
        Args:
            model: OpenAI model name (defaults to gpt-4o-mini or from env)
        """
        _load_env()
        
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing OPENAI_API_KEY in environment (.env).")
        
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        # Lazy import to keep module import clean
        from openai import OpenAI  # type: ignore
        self.client = OpenAI(api_key=self.api_key)
    
    def interpret_schema(
        self,
        file_path: str,
        original_df: Optional[pd.DataFrame] = None,
    ) -> SchemaMapping:
        """
        Interpret schema of uploaded file and return canonical mappings.
        
        This function:
        - Reads the file (if DataFrame not provided)
        - Extracts schema information (column names, types, sample values)
        - Calls LLM to interpret schema inconsistencies
        - Returns mapping suggestions
        
        CRITICAL: This does NOT modify the original data.
        It only returns mapping metadata.
        
        Args:
            file_path: Path to the file (used for context, not re-read if df provided)
            original_df: Optional DataFrame (if already loaded)
            
        Returns:
            SchemaMapping with suggested canonical mappings
            
        Raises:
            RuntimeError: If LLM returns invalid response
            Exception: If file cannot be read or processed
        """
        # Read file if DataFrame not provided
        if original_df is None:
            df, _ = read_file(file_path)
        else:
            df = original_df.copy()  # Work with copy to avoid modifying original
        
        # Extract schema information (metadata only, no actual data values)
        schema_info = get_schema_info(df)
        
        # Call LLM to interpret schema
        mapping_dict = self._call_llm_for_schema(schema_info)
        
        # Parse LLM response into SchemaMapping object
        return self._parse_llm_response(mapping_dict, schema_info)
    
    def _call_llm_for_schema(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call LLM to interpret schema and suggest canonical mappings.
        
        Args:
            schema_info: Schema metadata (columns, types, sample values)
            
        Returns:
            Dictionary with LLM response containing mappings
            
        Raises:
            RuntimeError: If LLM returns invalid JSON or violates constraints
        """
        system_prompt = (
            "You are a schema interpretation assistant for marketing campaign data. "
            "Your job is to interpret inconsistent column names and suggest canonical mappings.\n\n"
            
            "CRITICAL RULES - YOU MUST FOLLOW THESE:\n"
            "1. You MUST NOT modify, change, or suggest changes to any data VALUES (numbers, text records)\n"
            "2. You MUST NOT estimate missing values\n"
            "3. You MUST NOT fabricate or interpolate data\n"
            "4. You may ONLY interpret SCHEMA (column names, structure)\n"
            "5. You may ONLY suggest canonical MAPPINGS (original name → canonical name)\n"
            "6. You may classify fields (dimension, metric, metadata, uncertain)\n"
            "7. You may identify ambiguous fields that need caution\n\n"
            
            "Your output must be valid JSON only (no markdown, no extra text).\n"
            "Return a JSON object with the following structure:\n"
            "- column_mappings: array of {original_name, canonical_name, confidence (0-1), field_type, notes (optional)}\n"
            "- value_mappings: array of {column_name, original_value, canonical_value, confidence (0-1)} for categorical fields only\n"
            "- uncertain_fields: array of column names that are ambiguous\n"
            "- additional_fields: array of column names that are preserved but not mapped\n"
            "- notes: string with any important observations\n\n"
            
            "Common canonical names:\n"
            "- Dimensions: campaign, device, platform, date\n"
            "- Metrics: spend, revenue, clicks, impressions, conversions\n"
            "- Common platform aliases: google/google ads, facebook/meta/פייסבוק, etc.\n"
            "- Handle Hebrew/English mixed naming\n"
            "- Handle typos and alternate spellings"
        )
        
        user_prompt = (
            "Given this schema information, suggest canonical mappings:\n\n"
            f"Columns: {schema_info['columns']}\n"
            f"Data types: {schema_info['dtypes']}\n"
            f"Row count: {schema_info['row_count']}\n"
            f"Sample values (for categorical columns): {schema_info['sample_values']}\n\n"
            
            "Interpret the schema and suggest canonical mappings. "
            "Remember: you are only mapping SCHEMA, not modifying data values."
        )
        
        # Call LLM
        try:
            # Try with response_format (for newer OpenAI API versions)
            try:
                chat = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,  # Low temperature for consistent mapping
                    response_format={"type": "json_object"},  # Force JSON output
                )
            except TypeError:
                # Fallback for older API versions that don't support response_format
                chat = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,  # Low temperature for consistent mapping
                )
            text = chat.choices[0].message.content
            
            # CRITICAL FIX #3: Safer LLM JSON parsing with graceful failure handling
            # Try to extract JSON from response (may be wrapped in markdown)
            result = None
            
            # First, try direct JSON parsing
            try:
                result = json.loads(text)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                import re
                # Look for JSON in code blocks
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass
                
                # If still no result, try to find JSON object in text
                if result is None:
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group(0))
                        except json.JSONDecodeError:
                            pass
            
            # If parsing still failed, raise sanitized error
            if result is None:
                # CRITICAL FIX #7: Don't leak raw LLM output in error
                raise RuntimeError(
                    "Schema interpretation failed: Unable to parse LLM response. "
                    "Please check your file format and try again. "
                    "If the problem persists, the file may have an unsupported structure."
                )
            
            # Validate that result has expected structure
            if not isinstance(result, dict):
                raise RuntimeError(
                    "Schema interpretation failed: Invalid response format. "
                    "Please try again or check your file structure."
                )
            
            return result
            
        except RuntimeError:
            # Re-raise RuntimeErrors (our sanitized errors)
            raise
        except Exception as e:
            # CRITICAL FIX #7: Sanitized error - don't expose internal details
            raise RuntimeError(
                f"Schema interpretation failed: {type(e).__name__}. "
                "Please check your file format and try again."
            ) from e
    
    def _parse_llm_response(
        self,
        llm_response: Dict[str, Any],
        schema_info: Dict[str, Any],
    ) -> SchemaMapping:
        """
        Parse LLM response into SchemaMapping object.
        
        CRITICAL FIX #3: Validates LLM response structure.
        
        Args:
            llm_response: Raw LLM response dictionary
            schema_info: Original schema information
            
        Returns:
            SchemaMapping object
            
        Raises:
            RuntimeError: If LLM response structure is invalid
        """
        # Validate LLM response has expected structure
        if not isinstance(llm_response, dict):
            raise RuntimeError(
                "Schema interpretation failed: Invalid response structure. "
                "Please try again or check your file format."
            )
        
        column_mappings = []
        for mapping in llm_response.get("column_mappings", []):
            # Validate mapping structure
            if not isinstance(mapping, dict):
                continue  # Skip invalid mappings
            
            original_name = mapping.get("original_name", "")
            canonical_name = mapping.get("canonical_name", "")
            
            # Skip empty mappings
            if not original_name or not canonical_name:
                continue
            
            column_mappings.append(
                ColumnMapping(
                    original_name=original_name,
                    canonical_name=canonical_name,
                    confidence=float(mapping.get("confidence", 0.5)),
                    field_type=mapping.get("field_type", "uncertain"),
                    notes=mapping.get("notes"),
                )
            )
        
        value_mappings = []
        for mapping in llm_response.get("value_mappings", []):
            # Validate mapping structure
            if not isinstance(mapping, dict):
                continue  # Skip invalid mappings
            
            column_name = mapping.get("column_name", "")
            original_value = mapping.get("original_value", "")
            canonical_value = mapping.get("canonical_value", "")
            
            # Skip empty mappings
            if not column_name or not original_value or not canonical_value:
                continue
            
            value_mappings.append(
                ValueMapping(
                    column_name=column_name,
                    original_value=original_value,
                    canonical_value=canonical_value,
                    confidence=float(mapping.get("confidence", 0.5)),
                )
            )
        
        return SchemaMapping(
            column_mappings=column_mappings,
            value_mappings=value_mappings,
            uncertain_fields=llm_response.get("uncertain_fields", []),
            additional_fields=llm_response.get("additional_fields", []),
            notes=llm_response.get("notes"),
        )
