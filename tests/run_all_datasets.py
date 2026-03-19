import json
import os
from pathlib import Path

import requests


API_URL = "http://localhost:8000/analyze"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATA_DIR = PROJECT_ROOT / "test_data"
RESULTS_DIR = PROJECT_ROOT / "tests" / "results"
RESULTS_FILE = RESULTS_DIR / "test_results.json"


def run_dataset(csv_path: Path) -> dict:
    """
    Run a single dataset through the /analyze endpoint and return a structured result record.
    """
    dataset_name = csv_path.name

    # Default record structure
    record = {
        "dataset": dataset_name,
        "success": False,
        "error": None,
        "no_insights": None,
        "insights_count": None,
        "executive_summary": None,
        "prioritized_insights": [],
    }

    try:
        with csv_path.open("rb") as f:
            files = {
                "file": (csv_path.name, f, "text/csv"),
            }
            # We rely on backend defaults for skip_reading / skip_strategic
            response = requests.post(API_URL, files=files, timeout=60)

        if not response.ok:
            # Non-200 response from API
            try:
                data = response.json()
                error_detail = data.get("detail", str(data))
            except Exception:
                error_detail = f"HTTP {response.status_code}"
            record["error"] = error_detail
            return record

        # 200 OK — parse JSON payload
        try:
            data = response.json()
        except Exception as e:
            record["error"] = f"Failed to parse JSON: {e}"
            return record

        # /analyze schema:
        # { executive_summary, prioritized_insights, recommended_checks, risk_warnings }
        executive_summary = data.get("executive_summary", "")
        prioritized_insights = data.get("prioritized_insights") or []

        insights_count = len(prioritized_insights)
        no_insights = insights_count == 0

        record["success"] = True
        record["error"] = None
        record["no_insights"] = no_insights
        record["insights_count"] = insights_count
        record["executive_summary"] = executive_summary

        # Keep insights in a simple title/summary structure for review
        cleaned_insights = []
        for ins in prioritized_insights:
            if not isinstance(ins, dict):
                continue
            cleaned_insights.append(
                {
                    "title": ins.get("title") or ins.get("issue_opportunity", ""),
                    "summary": ins.get("summary", ""),
                }
            )
        record["prioritized_insights"] = cleaned_insights

        return record

    except requests.RequestException as e:
        record["error"] = f"Request error: {e}"
        return record
    except Exception as e:
        record["error"] = f"Unexpected error: {e}"
        return record


def main() -> None:
    # Ensure results directory exists
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all CSV files from test_data/
    csv_files = sorted(TEST_DATA_DIR.glob("*.csv"))

    results = []
    total = len(csv_files)
    success_count = 0
    fail_count = 0
    no_insights_count = 0

    print(f"Found {total} CSV datasets in {TEST_DATA_DIR}.\n")

    # Header for summary table
    print(f"{'Dataset':40} | {'Success':7} | {'No Insights':11} | {'Insights Count':14}")
    print("-" * 85)

    for csv_path in csv_files:
        record = run_dataset(csv_path)
        results.append(record)

        success = record["success"]
        no_insights = record["no_insights"]
        insights_count = record["insights_count"]

        if success:
            success_count += 1
            if no_insights:
                no_insights_count += 1
        else:
            fail_count += 1

        # Pretty values for table
        success_str = "yes" if success else "no"
        if no_insights is True:
            no_insights_str = "yes"
        elif no_insights is False:
            no_insights_str = "no"
        else:
            no_insights_str = "-"

        insights_str = "-" if insights_count is None else str(insights_count)

        print(
            f"{csv_path.name:40} | {success_str:7} | {no_insights_str:11} | {insights_str:14}"
        )

    # Save full structured results
    with RESULTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\nSummary:")
    print(f"- Total datasets   : {total}")
    print(f"- Successful runs  : {success_count}")
    print(f"- Failed runs      : {fail_count}")
    print(f"- No-insights cases: {no_insights_count}")
    print(f"- Results saved to : {RESULTS_FILE}")


if __name__ == "__main__":
    main()

