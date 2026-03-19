"""
Test script for the LLM-Assisted Reading Assistant.

This script demonstrates how to use the reading assistant to interpret
schema inconsistencies without modifying raw data.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reading import ReadingAssistant, read_file


def main():
    """Test the reading assistant."""
    if len(sys.argv) < 2:
        print("Usage: python test_reading_assistant.py <file_path>")
        print("Example: python test_reading_assistant.py sample_data.csv")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    try:
        # Initialize reading assistant
        print(f"Initializing Reading Assistant...")
        assistant = ReadingAssistant()
        
        # Read file (this doesn't modify data, just loads it)
        print(f"Reading file: {file_path}")
        df, file_type = read_file(file_path)
        print(f"File type: {file_type.value}")
        print(f"Columns: {list(df.columns)}")
        print(f"Rows: {len(df)}")
        print()
        
        # Interpret schema using LLM
        print("Interpreting schema with LLM...")
        print("(This may take a few seconds)")
        print()
        
        schema_mapping = assistant.interpret_schema(file_path, original_df=df)
        
        # Display results
        print("=" * 60)
        print("SCHEMA MAPPING RESULTS")
        print("=" * 60)
        print()
        
        print("Column Mappings:")
        for mapping in schema_mapping.column_mappings:
            print(f"  '{mapping.original_name}' → '{mapping.canonical_name}'")
            print(f"    Type: {mapping.field_type}, Confidence: {mapping.confidence:.2f}")
            if mapping.notes:
                print(f"    Notes: {mapping.notes}")
            print()
        
        if schema_mapping.value_mappings:
            print("Value Mappings (Categorical):")
            for mapping in schema_mapping.value_mappings:
                print(f"  Column '{mapping.column_name}':")
                print(f"    '{mapping.original_value}' → '{mapping.canonical_value}'")
                print(f"    Confidence: {mapping.confidence:.2f}")
                print()
        
        if schema_mapping.uncertain_fields:
            print("Uncertain Fields (require caution):")
            for field in schema_mapping.uncertain_fields:
                print(f"  - {field}")
            print()
        
        if schema_mapping.additional_fields:
            print("Additional Fields (preserved but not mapped):")
            for field in schema_mapping.additional_fields:
                print(f"  - {field}")
            print()
        
        if schema_mapping.notes:
            print("Notes:")
            print(f"  {schema_mapping.notes}")
            print()
        
        print("=" * 60)
        print("IMPORTANT: Original data remains untouched!")
        print("Only schema mappings were generated.")
        print("=" * 60)
        
        # Show that original data is unchanged
        print()
        print("Original DataFrame columns (unchanged):")
        print(f"  {list(df.columns)}")
        
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
