"""
FastAPI application for Marketing Insight Engine.

Provides a REST API interface for the insight generation pipeline.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Any, List, Dict
import logging
from datetime import datetime, date
import pandas as pd

from src.pipeline.pipeline_runner import run_full_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-friendly types.
    
    Handles:
    - pandas Timestamp -> ISO format string
    - datetime/date -> ISO format string
    - numpy bool_ -> Python bool
    - numpy integer -> Python int
    - numpy floating -> Python float
    - numpy arrays -> Python list
    - numpy scalars (via .item())
    - nested dicts/lists recursively
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    import numpy as np
    
    # Handle pandas Timestamp
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle date objects
    if isinstance(obj, date):
        return obj.isoformat()
    
    # Handle numpy boolean types explicitly (must come before generic numpy check)
    if isinstance(obj, np.bool_):
        return bool(obj)
    
    # Handle numpy integer types
    if isinstance(obj, np.integer):
        return int(obj)
    
    # Handle numpy floating types
    if isinstance(obj, np.floating):
        return float(obj)
    
    # Handle numpy arrays
    if isinstance(obj, np.ndarray):
        return [_make_json_serializable(item) for item in obj.tolist()]
    
    # Handle other numpy scalar types (via .item() method)
    if hasattr(obj, 'item') and hasattr(obj, 'dtype'):
        try:
            return _make_json_serializable(obj.item())
        except (ValueError, AttributeError):
            pass
    
    # Handle dictionaries - recurse
    if isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    
    # Handle lists/tuples - recurse
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    
    # Return as-is if already serializable
    return obj


app = FastAPI(
    title="AdScope - AI Marketing Insight Engine",
    description="AI Marketing Insight Engine for analyzing campaign data and generating strategic insights",
    version="1.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Add CORS middleware for UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """User type selection page."""
    return templates.TemplateResponse("user_type.html", {"request": request})


@app.get("/app", response_class=HTMLResponse)
async def app_ui() -> HTMLResponse:
    """
    Serve the single-page AdScope UI located at ui/index.html.

    This keeps the backend logic and existing templates unchanged and
    simply returns the HTML content of the new UI.
    """
    try:
        with open("ui/index.html", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="ui/index.html not found. Make sure the UI file exists.",
            status_code=500,
        )
    return HTMLResponse(content=content)


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request, error: Optional[str] = None):
    """Upload page."""
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "error": error
    })


@app.get("/processing", response_class=HTMLResponse)
async def processing_page(request: Request):
    """Processing page."""
    return templates.TemplateResponse("processing.html", {"request": request})


@app.get("/insights", response_class=HTMLResponse)
async def insights_page(request: Request):
    """Insights page - requires result data in session or query params."""
    # For now, return empty insights page (will be populated by POST /analyze redirect)
    return templates.TemplateResponse("insights.html", {
        "request": request,
        "result": {}
    })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/analyze")
async def analyze_file_api(
    file: UploadFile = File(..., description="CSV or XLSX file with campaign data"),
    skip_reading: bool = False,
    skip_strategic: bool = False,
):
    """
    API endpoint for analyzing files (JSON response).
    
    This is the original API endpoint, kept for JSON API clients.
    For UI form submissions, use POST /analyze instead.
    """
    # Validate file type
    if file.content_type not in [
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        file_ext = file.filename.lower().split('.')[-1] if file.filename else ''
        if file_ext not in ['csv', 'xlsx', 'xls']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported: CSV, XLSX, XLS. Got: {file.content_type or file_ext}"
            )
    
    try:
        file_content = await file.read()
        file_name = file.filename or "uploaded_file.csv"
        
        logger.info(f"API: Processing file: {file_name}, size: {len(file_content)} bytes")
        
        result = run_full_pipeline(
            file_content=file_content,
            file_name=file_name,
            skip_reading=skip_reading,
            skip_strategic=skip_strategic,
        )
        
        if result.get("success"):
            if result.get("no_insights"):
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "no_insights": True,
                        "message": result.get("message", "No insights found"),
                    }
                )
            else:
                result_data = result.get("result")
                if result_data is not None:
                    result_data = _make_json_serializable(result_data)
                
                response_content = {
                    "success": True,
                    "no_insights": False,
                    "result": result_data,
                }
                
                if "warning" in result:
                    response_content["warning"] = result.get("warning")
                
                response_content = _make_json_serializable(response_content)
                
                return JSONResponse(status_code=200, content=response_content)
        else:
            error_msg = result.get("error", "Unknown error occurred")
            logger.error(f"Pipeline error: {error_msg}")
            
            status_code = 400
            if "not found" in error_msg.lower():
                status_code = 404
            elif "unexpected" in error_msg.lower() or "internal" in error_msg.lower():
                status_code = 500
            
            raise HTTPException(status_code=status_code, detail=error_msg)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /api/analyze endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your file. Please try again."
        )


@app.post("/analyze")
async def analyze_file(
    file: UploadFile = File(..., description="CSV or XLSX file with campaign data"),
    skip_reading: bool = Form(False),
    skip_strategic: bool = Form(False),
):
    """
    JSON endpoint for the SPA at /app.

    Adapts the internal engine output to the simplified shape expected
    by the frontend:

        {
          "executive_summary": "...",
          "prioritized_insights": [...],
          "recommended_checks": [],
          "risk_warnings": []
        }

    The underlying pipeline (run_full_pipeline) and /api/analyze logic
    remain unchanged.
    """
    # Validate file type (same rules as /api/analyze)
    if file.content_type not in [
        "text/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        file_ext = file.filename.lower().split('.')[-1] if file.filename else ''
        if file_ext not in ['csv', 'xlsx', 'xls']:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported: CSV, XLSX, XLS. Got: {file.content_type or file_ext}",
            )

    try:
        # Read file content
        file_content = await file.read()
        file_name = file.filename or "uploaded_file.csv"

        logger.info(f"/analyze SPA: Processing file: {file_name}, size: {len(file_content)} bytes")

        # Run full pipeline (same engine as /api/analyze)
        result = run_full_pipeline(
            file_content=file_content,
            file_name=file_name,
            skip_reading=skip_reading,
            skip_strategic=skip_strategic,
        )

        # CRITICAL: Convert entire result dict to JSON-serializable types FIRST
        # This ensures numpy bools in success/no_insights fields are converted
        result = _make_json_serializable(result)

        if not result.get("success"):
            # Pipeline reported an error
            error_msg = result.get("error", "Unknown error occurred")
            logger.error(f"/analyze SPA pipeline error: {error_msg}")
            logger.info("/analyze SPA response status=error")

            status_code = 400
            if "not found" in error_msg.lower():
                status_code = 404
            elif "unexpected" in error_msg.lower() or "internal" in error_msg.lower():
                status_code = 500

            raise HTTPException(status_code=status_code, detail=error_msg)

        # No-insights case: still return the simplified JSON shape
        if result.get("no_insights"):
            message = result.get("message", "No insights found")
            logger.info("/analyze SPA response status=no_insights")
            payload = {
                "executive_summary": message,
                "prioritized_insights": [],
                "recommended_checks": [],
                "risk_warnings": [],
            }
            # Ensure payload is JSON serializable
            payload = _make_json_serializable(payload)
            return JSONResponse(status_code=200, content=payload)

        # Success with insights: adapt the engine result to UI shape
        raw_result = result.get("result") or {}
        raw_result = _make_json_serializable(raw_result)

        executive_summary = raw_result.get("executive_summary", "")
        top_priorities = raw_result.get("top_priorities") or []
        raw_prioritized = raw_result.get("prioritized_insights") or []
        raw_recommended_checks = raw_result.get("recommended_checks") or []
        raw_risks = raw_result.get("risks_warnings") or []
        
        # Ensure top_priorities list items are also JSON-serializable
        top_priorities = _make_json_serializable(top_priorities)
        raw_prioritized = _make_json_serializable(raw_prioritized)
        raw_recommended_checks = _make_json_serializable(raw_recommended_checks)
        raw_risks = _make_json_serializable(raw_risks)

        logger.info(
            "/analyze SPA raw result counts: top_priorities=%d, prioritized_insights=%d, recommended_checks=%d, risks_warnings=%d",
            len(top_priorities), len(raw_prioritized), len(raw_recommended_checks), len(raw_risks)
        )

        prioritized_insights: List[Dict[str, Any]] = []
        # Prefer top_priorities for UX consistency; fallback to prioritized_insights when needed.
        if top_priorities:
            for prio in top_priorities:
                if not isinstance(prio, dict):
                    continue
                # Convert each priority dict to ensure all nested values are JSON-serializable
                prio = _make_json_serializable(prio)
                title = prio.get("issue_opportunity", "")
                why = prio.get("why_it_matters", "")
                impact = prio.get("expected_impact", "")

                parts = [p for p in [why, impact] if p]
                summary = " ".join(parts).strip()
                prioritized_insights.append({"title": title, "summary": summary})
        else:
            for item in raw_prioritized:
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "")
                summary = item.get("summary", "")
                if title or summary:
                    prioritized_insights.append({"title": title, "summary": summary})

        payload = {
            "executive_summary": executive_summary,
            "prioritized_insights": prioritized_insights,
            "recommended_checks": raw_recommended_checks,
            "risk_warnings": raw_risks,
        }

        # Ensure entire payload is JSON serializable (handles numpy bools, etc.)
        payload = _make_json_serializable(payload)
        logger.info(
            "/analyze SPA response status=success, prioritized_insights=%d",
            len(payload.get("prioritized_insights", []))
        )

        return JSONResponse(status_code=200, content=payload)

    except HTTPException:
        # Propagate HTTP errors as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in /analyze SPA endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while processing your file. Please try again.",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
