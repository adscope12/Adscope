# AdScope UI

A minimal, polished, insight-first SaaS interface for the AdScope AI Marketing Insight Engine.

## Design

- **Background**: Soft warm neutral (`#faf9f7`)
- **Accent Color**: Soft coral/peach (`#E6A08B`)
- **Typography**: Inter font family
- **Style**: Premium, calm, simple - insight-first (not dashboard-first)
- **Cards**: Rounded corners (18-20px), subtle shadows, thin borders
- **Spacing**: Generous spacing throughout

## Pages

1. **User Type Selection** - Choose between Business Owner or Media Agency
2. **Upload** - Drag & drop or click to upload CSV/XLSX files
3. **Processing** - Elegant loading state with step-by-step progress
4. **Insights** - Clean insight-first display with Executive Summary, Top Insights, Recommended Actions, and Risk Warnings

## Setup

### 1. Start the FastAPI Backend

```bash
python api.py
```

The API will run on `http://localhost:8000`

### 2. Open the UI

**Option 1: Direct File Open**
- Simply open `ui/index.html` in a modern web browser
- Note: Some browsers may have CORS restrictions for local files

**Option 2: Simple HTTP Server (Recommended)**

```bash
cd ui
python -m http.server 8080
```

Then open: `http://localhost:8080`

**Option 3: Using Node.js http-server**

```bash
npx http-server ui -p 8080
```

Then open: `http://localhost:8080`

## API Configuration

The UI connects to the FastAPI backend at `http://localhost:8000` by default.

To change the API URL, edit the `API_BASE_URL` constant in `index.html`:

```javascript
const API_BASE_URL = 'http://localhost:8000';
```

## Features

- ✅ Clean, modern SaaS design
- ✅ Insight-first layout (not dashboard-heavy)
- ✅ Drag & drop file upload
- ✅ Real-time processing indicators
- ✅ Displays Executive Summary, Top Insights, Recommended Actions, Risk Warnings
- ✅ "Analyze another dataset" button to restart
- ✅ Responsive design
- ✅ Error handling

## File Format

Accepts CSV or XLSX files with marketing campaign data. The reading assistant handles schema interpretation, so column names can vary.

Expected data includes:
- Date
- Campaign
- Platform
- Spend
- Revenue
- Clicks
- Impressions
- Conversions

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Requires JavaScript enabled
- Responsive design (mobile-friendly)
