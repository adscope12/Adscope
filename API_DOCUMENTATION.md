# Marketing Insight Engine API Documentation

## Overview

The Marketing Insight Engine API provides a REST interface for analyzing marketing campaign data and generating strategic insights.

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Running the Server

```bash
# Development server
python api.py

# Or using uvicorn directly
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **Base URL**: `http://localhost:8000`
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc` (Alternative docs)

## Endpoints

### GET `/`
Health check endpoint.

**Response**:
```json
{
  "status": "ok",
  "service": "Marketing Insight Engine API",
  "version": "1.0.0"
}
```

### GET `/health`
Health check endpoint.

**Response**:
```json
{
  "status": "healthy"
}
```

### POST `/analyze`
Analyze a marketing campaign data file and return strategic insights.

**Request**:
- **Method**: POST
- **Content-Type**: `multipart/form-data`
- **Parameters**:
  - `file` (required): CSV or XLSX file with campaign data
  - `skip_reading` (optional, default: false): Skip LLM-assisted reading layer
  - `skip_strategic` (optional, default: false): Skip Strategic LLM layer (not recommended)

**Response** (Success with insights):
```json
{
  "success": true,
  "no_insights": false,
  "result": {
    "executive_summary": "Based on the analyzed campaign data...",
    "top_priorities": [
      {
        "issue_opportunity": "Facebook Platform Underperformance",
        "why_it_matters": "Facebook shows significantly lower ROAS...",
        "expected_impact": "Reallocating budget could improve..."
      }
    ],
    "risks_warnings": [
      "Revenue concentration risk: Top 2 campaigns account for 60%..."
    ],
    "recommended_checks": [
      "Review Facebook campaign settings...",
      "Analyze budget allocation..."
    ],
    "prioritized_insights": [...],
    "notes": "..."
  }
}
```

**Response** (No insights found):
```json
{
  "success": true,
  "no_insights": true,
  "message": "The deterministic engine did not find any statistically significant patterns..."
}
```

**Response** (Error):
```json
{
  "detail": "Error message here"
}
```

**Status Codes**:
- `200`: Success
- `400`: Bad Request (validation error, unsupported file type)
- `404`: File not found
- `500`: Internal server error

## Example Usage

### Using cURL

```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@hebrew_test.csv"
```

### Using Python requests

```python
import requests

url = "http://localhost:8000/analyze"
files = {"file": open("hebrew_test.csv", "rb")}
response = requests.post(url, files=files)

if response.status_code == 200:
    result = response.json()
    if result.get("success"):
        if result.get("no_insights"):
            print("No insights found:", result.get("message"))
        else:
            insights = result.get("result")
            print("Executive Summary:", insights.get("executive_summary"))
            print("Top Priorities:", insights.get("top_priorities"))
else:
    print("Error:", response.json().get("detail"))
```

### Using JavaScript (fetch)

```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8000/analyze', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  if (data.success && !data.no_insights) {
    console.log('Insights:', data.result);
  } else if (data.no_insights) {
    console.log('No insights:', data.message);
  }
})
.catch(error => console.error('Error:', error));
```

## Pipeline Flow

The `/analyze` endpoint runs the complete pipeline:

1. **File Ingestion**: Reads and validates the uploaded file
2. **LLM-Assisted Reading Layer**: Interprets schema inconsistencies (column names, multilingual names, typos)
3. **Canonical Bridge**: Creates canonicalized view with applied mappings
4. **Deterministic Insight Engine**: Generates scored statistical patterns
5. **Strategic LLM Layer**: Interprets and prioritizes insights into strategic recommendations
6. **User-Facing Output**: Returns clean, actionable insights (no internal IDs or technical details)

## Security & Privacy

- **No Data Storage**: Uploaded files are processed in memory and not persisted
- **No Internal IDs**: Pattern IDs, evidence IDs, and internal references are never exposed
- **Sanitized Errors**: Error messages are user-friendly and don't expose internal details
- **Input Validation**: All inputs are validated before processing

## Error Handling

The API provides user-friendly error messages:

- **Empty File**: "File is empty or contains no data rows."
- **Missing Columns**: "Required columns not found after canonical mapping: ['spend', 'revenue']..."
- **Invalid File Type**: "Unsupported file type. Supported: CSV, XLSX, XLS."
- **LLM Errors**: Generic messages without exposing raw LLM output
- **Unexpected Errors**: "An unexpected error occurred. Please check your file and try again."

## File Requirements

- **Supported Formats**: CSV, XLSX, XLS
- **Required Columns**: Must contain spend and revenue data (after canonical mapping)
- **Minimum Data**: At least one row of data
- **Encoding**: UTF-8 recommended (handles Hebrew/English mixed content)

## Response Structure

### Success Response (with insights)
```json
{
  "success": true,
  "no_insights": false,
  "result": {
    "executive_summary": "string",
    "top_priorities": [
      {
        "issue_opportunity": "string",
        "why_it_matters": "string",
        "expected_impact": "string"
      }
    ],
    "risks_warnings": ["string"],
    "recommended_checks": ["string"],
    "prioritized_insights": [
      {
        "title": "string",
        "summary": "string",
        "recommended_actions": ["string"],
        "confidence": 0.0-1.0
      }
    ],
    "notes": "string"
  }
}
```

### Success Response (no insights)
```json
{
  "success": true,
  "no_insights": true,
  "message": "string"
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

## Notes

- The API preserves all robustness and validation behavior from the CLI
- Internal IDs, evidence IDs, and technical details are never exposed
- All error messages are sanitized for user consumption
- The pipeline is stateless - each request is processed independently
