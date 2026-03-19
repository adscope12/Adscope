"""CLI interface for the Insight Engine with LLM-Assisted Reading Layer."""

import argparse
import sys
from pathlib import Path

from src.reading import read_file, ReadingAssistant
from src.normalization.canonicalizer import prepare_canonical_structure, log_schema_mapping
from src.engine import InsightEngine
from src.llm import StrategicLLMLayer
from src.output.strategic_formatter import (
    format_strategic_output,
    format_strategic_output_json,
    convert_scored_patterns_to_dict,
)
from src.pipeline.pipeline_runner import run_full_pipeline


def main():
    """
    Main CLI entry point.
    
    Pipeline:
    1. File Ingestion: Read CSV or XLSX file
    2. LLM-Assisted Reading Layer: Interpret schema, get mappings
    3. Canonical Structure: Prepare canonical bridge with applied mappings
    4. Deterministic Insight Engine: Process data and generate scored patterns
    5. Strategic LLM Layer: Interpret and prioritize engine outputs
    6. User-Facing Output: Format and display final results
    """
    parser = argparse.ArgumentParser(
        description='Marketing Insight Engine with LLM-Assisted Reading Layer'
    )
    parser.add_argument(
        'file',
        help='Path to CSV or XLSX file with campaign data'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )
    parser.add_argument(
        '--skip-reading',
        action='store_true',
        help='Skip LLM-assisted reading layer (for testing)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress schema mapping output'
    )
    parser.add_argument(
        '--skip-strategic',
        action='store_true',
        help='Skip Strategic LLM layer (output raw engine results)'
    )
    args = parser.parse_args()
    
    try:
        # Delegate to shared pipeline runner to ensure CLI uses the same
        # grounded narrative + strategic fallback flow as the API.
        result = run_full_pipeline(
            file_path=args.file,
            skip_reading=args.skip_reading,
            skip_strategic=args.skip_strategic,
        )

        # Error path from pipeline
        if not result.get("success"):
            error_msg = result.get("error", "Unknown error occurred")
            print(f"Error: {error_msg}", file=sys.stderr)
            return 1

        # No-insights path (preserve explicit messaging)
        if result.get("no_insights"):
            message = result.get("message", "No strong insights detected in this dataset.")
            print("\n" + "=" * 80)
            print("NO INSIGHTS FOUND")
            print("=" * 80)
            print(f"\n{message}")
            print("\nThis may occur if:")
            print("  • The dataset is too small or has insufficient variation")
            print("  • All segments perform similarly")
            print("  • Required metrics (spend, revenue) are missing or invalid")
            print("\nPlease check your data and try again.")
            print("=" * 80)
            return 0

        # Success with insights: adapt result to existing CLI formats
        raw_result = result.get("result") or {}

        if args.json:
            # JSON output: already in strategic JSON shape
            import json
            print(json.dumps(raw_result, indent=2, ensure_ascii=False))
        else:
            # Text output: reuse existing strategic formatter
            # raw_result already has executive_summary/top_priorities/etc.
            print(format_strategic_output(raw_result, hide_internal_ids=True))

        return 0
    
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        return 1
    except ValueError as e:
        # CRITICAL FIX #7: Sanitized user-facing errors
        # ValueError typically indicates user input issues - show clean message
        error_msg = str(e)
        # Remove internal paths and technical details
        if "canonical_structure" in error_msg.lower():
            print("Error: Invalid data structure. Please check your file format.", file=sys.stderr)
        elif "column" in error_msg.lower() or "required" in error_msg.lower():
            print(f"Error: {error_msg}", file=sys.stderr)
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        # CRITICAL FIX #7: Sanitized LLM errors (no raw output leakage)
        error_msg = str(e)
        # Check if this is an LLM-related error
        if "LLM" in error_msg or "JSON" in error_msg or "invalid" in error_msg.lower():
            # Don't expose raw LLM output or technical details
            if "Raw output" in error_msg:
                print("Error: Unable to process schema interpretation. Please try again or contact support.", file=sys.stderr)
            else:
                # Generic error without technical details
                print("Error: Schema interpretation failed. Please check your file format and try again.", file=sys.stderr)
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        return 1
    except Exception as e:
        # CRITICAL FIX #7: Sanitized errors - no tracebacks in user output
        error_msg = str(e)
        # Remove internal paths and technical stack traces
        if "Traceback" in error_msg or "File" in error_msg and ".py" in error_msg:
            # This looks like a traceback - show generic error
            print("Error: An unexpected error occurred. Please check your file and try again.", file=sys.stderr)
            print("For technical support, please provide the file format and error details.", file=sys.stderr)
        else:
            print(f"Error: {error_msg}", file=sys.stderr)
        # Log full error internally (for debugging) but don't show to user
        import logging
        logging.basicConfig(level=logging.ERROR)
        logging.error(f"Internal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
