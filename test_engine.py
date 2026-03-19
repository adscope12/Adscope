"""Simple test script for the Insight Engine."""

import sys
from src.engine import InsightEngine
from src.selection.formatter import format_insights

def test_engine():
    """Test the engine with sample data."""
    print("Testing Insight Engine...")
    print("=" * 80)
    
    try:
        engine = InsightEngine()
        insights = engine.process("sample_data.csv", top_n=4)
        
        print(f"\nFound {len(insights)} insights\n")
        print(format_insights(insights))
        
        print("\n" + "=" * 80)
        print("Test completed successfully!")
        return 0
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(test_engine())
