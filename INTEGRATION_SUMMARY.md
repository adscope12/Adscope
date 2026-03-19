# FastAPI UI Integration Summary

## Files Created

### Templates (`/templates`)
1. **`base.html`** - Base template with common structure, includes CSS and JS
2. **`user_type.html`** - User type selection page (route: `/`)
3. **`upload.html`** - File upload page (route: `/upload`)
4. **`processing.html`** - Processing/loading page (route: `/processing`)
5. **`insights.html`** - Insights display page (route: `/insights`)

### Static Files (`/static`)
1. **`styles.css`** - All CSS styles for AdScope UI (soft neutral background, rounded cards, accent color)
2. **`app.js`** - Shared JavaScript functionality for file upload handling

## Files Modified

1. **`api.py`** - Added:
   - Jinja2Templates setup
   - StaticFiles mounting (`/static` directory)
   - HTML routes: `/`, `/upload`, `/processing`, `/insights`
   - Modified `/analyze` to handle UI form submissions (renders HTML template)
   - Added `/api/analyze` endpoint for JSON API calls (preserves original API behavior)

2. **`requirements.txt`** - Added:
   - `jinja2>=3.1.0`

## Routes

### UI Routes
- **GET `/`** → `user_type.html` - User type selection page
- **GET `/upload`** → `upload.html` - File upload page
- **GET `/processing`** → `processing.html` - Processing page with animated steps
- **GET `/insights`** → `insights.html` - Insights display page
- **POST `/analyze`** → Handles form submissions, renders `insights.html` with results

### API Routes (unchanged)
- **POST `/api/analyze`** → JSON API endpoint (original API behavior preserved)
- **GET `/health`** → Health check

## How to Run

### Command to Run Server

```bash
python api.py
```

### URL to Open

**`http://127.0.0.1:8000`**

or

**`http://localhost:8000`**

The application runs entirely from the FastAPI server - no separate frontend server needed.

## Architecture

```
FastAPI Application (single server)
│
├── UI Routes (HTML templates)
│   ├── GET / → user_type.html
│   ├── GET /upload → upload.html
│   ├── GET /processing → processing.html
│   ├── GET /insights → insights.html
│   └── POST /analyze → processes form, renders insights.html
│
├── API Routes (JSON)
│   └── POST /api/analyze → JSON response (original API)
│
├── Templates (/templates)
│   ├── base.html
│   ├── user_type.html
│   ├── upload.html
│   ├── processing.html
│   └── insights.html
│
└── Static Files (/static)
    ├── styles.css
    └── app.js
```

## Page Flow

1. **`/`** → User selects Business Owner or Media Agency → Click Continue → `/upload`
2. **`/upload`** → User uploads CSV/XLSX file → Click Analyze → POST `/analyze`
3. **POST `/analyze`** → Processes file → Renders `insights.html` with results
4. **`/insights`** → Displays Executive Summary, Top Insights, Recommended Actions, Risk Warnings

## Design Features

- ✅ Soft warm neutral background (`#faf9f7`)
- ✅ Centered white cards with rounded corners (18-20px)
- ✅ Subtle shadows and thin borders
- ✅ Accent color: Soft coral/peach (`#E6A08B`)
- ✅ Modern typography (Inter font)
- ✅ Generous spacing, minimal clutter
- ✅ Branding: "AdScope" + "AI Marketing Insight Engine" in top-left

## API Compatibility

The original JSON API endpoint is preserved at `/api/analyze`:
- Send file with `Accept: application/json` header (or use `/api/analyze`)
- Receive JSON response
- Form submissions to `/analyze` render HTML template

## Notes

- All UI runs from single FastAPI server
- No separate frontend server needed
- Existing backend logic unchanged
- `/analyze` endpoint handles both UI forms and can detect API calls
- `/api/analyze` is the dedicated JSON API endpoint
