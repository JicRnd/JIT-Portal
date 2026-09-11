# JIT Cylinder Quote Web - Milestone 1

Calculation-only Flask web interface around the frozen Cylinder Quote Pricing Engine v1.2.

## Scope
- OrderEntry-style browser form.
- Cascading Series -> Bore -> Rod -> Mount choices sourced from extracted pricing data.
- Core cylinder inputs, modifications, position sensing, accessories, special parts, and Standard Rod Boot.
- JSON API returns model code, full price breakdown, List, Net Each, Expedited, Emergency, and legacy compatibility warnings.
- Database foundation (SQLite/SQLAlchemy), lightweight current-user tracking, and atomic quote-number generation.
- Quote saving, Quote Preview editing, PDF generation, email, searchable Quote History, and Data1 approval are planned/in-progress.

## Email Setup (Optional)
Email is disabled by default. To enable the "Email Quote" button, set the SMTP
variables in `.env`:

```ini
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
SMTP_FROM_ADDRESS=quotes@example.com
```

If SMTP is not configured, the rest of the application continues to work normally
and the Email Quote flow returns a clean "not configured" message instead of crashing.

## PDF Generation Setup
PDFs are generated from the server-side quote preview HTML using Playwright and Chromium.
After installing Python requirements, install the browser binary once:

```powershell
py -m pip install -r requirements.txt
py -m playwright install chromium
```

If Chromium is not installed, the application continues to run; PDF routes return a clear
error message explaining the missing setup step.

## Configuration
Copy `.env.example` to `.env` and adjust values as needed. The example file
contains the current database path, default user name, and quote-number format.

## Run on Windows
1. Install Python 3.11 or newer.
2. Open PowerShell in this folder.
3. Create a virtual environment: `py -m venv .venv`
4. Activate it: `\.venv\Scripts\Activate.ps1`
5. Install dependencies: `py -m pip install -r requirements.txt`
6. Install the Chromium browser for PDF generation: `py -m playwright install chromium`
7. Initialize the database: `py scripts/init_db.py`
8. Start the app: `py run.py`
9. Open `http://localhost:5055`

Runtime data is stored in separate SQLite files under `Databases/` (WAL mode
enabled): `User_accounts.db`, `Employee_Contacts.db`, `Quote.db`, `Order.db`,
`Pricing.db`, and `Application.db`. The preserved legacy source is kept as
`Databases/Legacy_cylinder_quote.db` until archival is explicitly approved.
Generated PDF files remain under the configured quote-document directory.

## API
- `GET /api/health`
- `GET /api/catalog`
- `POST /api/calculate`
- `POST /api/quotes` — create a new quote snapshot
- `GET /api/quotes` — search/list saved quotes (`quote_number`, `customer_name`, `model_code`, `status`, `created_by`, `date_from`, `date_to`, `page`, `page_size`)
- `GET /api/quotes/<id>`
- `PATCH /api/quotes/<id>`
- `POST /api/quotes/<id>/pdf` — generate and store a PDF for the current revision
- `POST /api/quotes/<id>/email` — save current edits, regenerate the PDF, and email it
- `POST /api/quotes/<id>/duplicate` — create a fresh draft copy of a saved quote
- `GET /api/quotes/<id>/documents/<doc_id>` — download a generated PDF

The OrderEntry screen includes a **Quote History** button that opens a searchable list of saved quotes. From Quote History you can view an existing quote in the Quote Preview screen, duplicate it into a new draft, or return to OrderEntry.

Example POST body:
```json
{
  "series": "H",
  "bore": "2",
  "rod_diameter": "1",
  "mount": "MX0",
  "stroke": "12",
  "cushion": "NC",
  "port_code": "N",
  "seal_code": "",
  "rod_style": 1,
  "discount": "0.10",
  "dre": false
}
```

The pricing engine remains server-side. Browser JavaScript does not contain authoritative price tables or business arithmetic.
