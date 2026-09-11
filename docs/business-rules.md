# Business Rules (verified, source-cited)

Extracted from AGENTS.md/PROJECT_SPEC.md/code comments — do not restate to AI, cite this file instead. Update only when the cited source changes.

---

## 1. PRICING RULES

- Pricing Engine v1.2 is protected; do not rewrite/simplify/modernize merely for compatibility. (AGENTS.md)
- Do not weaken or remove pricing tests to make new work pass. (AGENTS.md)
- Current verified pricing engine and normalized pricing data are authoritative. (AGENTS.md)
- Discount must be between 0 and 1. (engine.py)
- DRE surcharge = base × 0.65 if DRE enabled, else 0. (engine.py)
- Expedited price = quote_net × 1.30 if quote_net > $1000, else × 1.40. (engine.py)
- Emergency price = expedited_price × 1.25. (engine.py)
- W-series gets 0.85 multiplier: quote_list = list_price × 0.85. (engine.py)
- Excel-compatible ROUNDUP used for pricing calculations (legacy behavior). (engine.py)
- Certain legacy worksheet formulas lack series gates (H3 Viton, A3 Viton, H4 Flange Port, Thick-head); these are reproduced for parity with warnings. (engine.py)
- Weld Plate quantity acts as on/off trigger; price is not multiplied by quantity. (engine.py)
- Standard Rod Boot: base price charged once; only stroke component multiplied by quantity. (engine.py)
- Net Each = excel_roundup(subtotal_with_dre × (1 - discount) + legacy_post_discount_add, 0). (engine.py)
- Pricing version stored with quote is v1.2. (quote_service.py)
- Saved quote snapshot must preserve pricing version and original calculation values. (AGENTS.md / PROJECT_SPEC.md)
- Future pricing changes must not recalculate or mutate an already-saved quote record. (AGENTS.md / PROJECT_SPEC.md)

## 2. APPROVAL WORKFLOW RULES

- Shared pending-approval queue exists across employee dashboards with Accept/assign button. (AGENTS.md — scope exception 2026-08-19)
- Employee sign-up: name/email/password + Location dropdown (currently only "Hartselle, AL") creates cross-dashboard approval request instead of auto-creating account. (AGENTS.md — scope exception 2026-08-20)
- Customer sign-up approval request uses same pattern as employee sign-up; on approval, notifies customer's own page client-side (no email) and loads their dashboard. (AGENTS.md — scope exception 2026-08-20)
- User.approval_status defaults to "approved" in schema. (models_db.py)
- User.approval_decided_at is set when an employee approves/holds/denies an account request. (models_db.py)

## 3. CUSTOMER/EMPLOYEE ACCOUNT BEHAVIOR RULES

- Email, username, password_hash columns reserved for future real authentication; nullable and unused now. (models_db.py)
- upsert_customer keeps saved customer directory current from quote's presentation fields. (quote_service.py)

## 4. UI/DATA INTEGRITY RULES

- Seal code P must be preserved. (AGENTS.md)
- Style 4 - Safety Coupler must be preserved. (AGENTS.md)
- Blank-slate startup required: all fields/options/sections start blank/zero. (AGENTS.md / PROJECT_SPEC.md)
- Field sequence must be: Series, Mount, Bore, Stroke, Rod, Style, Cushion, Ports, Seal, DRE. (AGENTS.md)
- Discount / Net Each / Profit must be clearly separated from Quote button. (AGENTS.md)
- Authoritative pricing remains server-side; do not trust stale browser-only price values. (AGENTS.md / PROJECT_SPEC.md)
- Manual special-order items must support: optional reference part number, description (required), quantity, unit price, extended price, optional internal note, show_on_customer_quote flag (defaults to True). (quote_service.py / PROJECT_SPEC.md)
- Manual items must NOT be silently added to the permanent pricing catalog. (AGENTS.md)
- Manual items do NOT require a cylinder model code. (PROJECT_SPEC.md)
- Manual items must transfer from OrderEntry to Quote Form HTML page and save to database. (AGENTS.md)
- If cylinder pricing is manually overridden in Quote Form, preserve both original server-calculated value and override value separately. (AGENTS.md / PROJECT_SPEC.md)
- Quote button validates required calculator inputs and performs authoritative server-side pricing (re-calculation). (PROJECT_SPEC.md)
- Quote Form HTML should resemble existing Excel Quote Form, feel spreadsheet-like and familiar. (PROJECT_SPEC.md)
- Quote Form editable fields include: Customer/contact/header, attention, reference, comments, descriptions, quantities, manual line details. (PROJECT_SPEC.md)
- Do not expose internal profit/cost information to customer-facing quote unless current business behavior specifically requires it. (PROJECT_SPEC.md)
- Database exists ONLY to save quote records from Quote Form HTML page. (AGENTS.md)
- SQLite must use: WAL mode, foreign keys, parameterized queries, short transactions. (AGENTS.md)
- Saved quote data must include: quote ID/number, timestamps, customer/header snapshot, full cylinder input snapshot, model code, options/modifications/accessories, manual items, pricing breakdown, pricing version, final displayed values, engineering/display values, comments/reference. (AGENTS.md / PROJECT_SPEC.md)
- Quote number format: [first letter of customer name] + MMDDYYHHMM (e.g., "A0819261215" for "AC Hotels" at 08/19/2026 12:15 PM). (quote_numbering.py)
- Quote numbers generated server-side and transactionally at save time, not on page load. (quote_numbering.py / quote_service.py)
- If two quotes for same customer land in same minute, uniqueness maintained by advancing one minute and retrying (up to 20 attempts max). (quote_numbering.py)
- Prefer provided quote number if format matches mmddyyhhmm; fall back to server generation in same format if not provided. (quote_service.py)
- Save Quote button: validate server-side, assign Quote # if not already assigned, save snapshot transactionally, save manual items/options, save pricing version and original calculations, return success message + Quote #, remain on Quote Form. (PROJECT_SPEC.md)
- Validate server-side inputs; parameterize database access; never accept arbitrary filesystem paths from browser. (AGENTS.md)
- Do not commit secrets; do not expose raw stack traces to normal users; log server errors with useful context. (AGENTS.md)
- Use transactional persistence for quote saves; avoid mutable global quote state shared across users. (AGENTS.md)

## 5. OUT-OF-SCOPE / DO-NOT-BUILD ITEMS

- Do NOT build Data1. (AGENTS.md)
- Do NOT build outbound HTTP transmission of quote data. (AGENTS.md)
- Do NOT build email sending. (AGENTS.md)
- Do NOT build SMTP configuration. (AGENTS.md)
- Do NOT build email UI. (AGENTS.md)
- Do NOT build PDF generation or Playwright/Chromium PDF setup. (AGENTS.md)
- Do NOT build customer-contact synchronization with external systems. (AGENTS.md)
- Do NOT build full user authentication/login system (SSO/OAuth/password reset); only local approval-queue mechanism permitted. (AGENTS.md)
- Do NOT build PostgreSQL migration this milestone. (AGENTS.md)
- Do NOT build external integrations of any kind. (AGENTS.md)
- Do NOT create placeholders for out-of-scope features unless tiny interface boundary absolutely necessary for clean architecture; any boundary must contain no network behavior and no user-facing feature. (AGENTS.md)
- No outbound network calls permitted to send quote/customer data outside local Flask application except normal browser requests. (AGENTS.md)
- Do NOT build Quote History/search/retrieval interface this milestone (database is only durable store for future retrieval). (AGENTS.md / PROJECT_SPEC.md)
- Do NOT email, generate PDF, send HTTP requests to another device, or approve anything on Save Quote button. (PROJECT_SPEC.md)
- Do NOT automatically save quote when Quote button is clicked; do not destroy just-saved screen before user sees save succeeded. (PROJECT_SPEC.md)
- Do NOT send actual email for approval queue or sign-up requests; only a no-op placeholder/hook may be added for future email address/config. (AGENTS.md — scope exception 2026-08-20)
