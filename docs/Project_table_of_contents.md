# Cylinder Quote To HTML - Project Table of Contents

This document is the working map for the active Flask application. Keep the paths and workflow notes current whenever a page, route, or connected file is moved or renamed.

## 1. Application Location and Startup

- Workspace root: `C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML`
- Active application: `C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML\Cylinder_Quote_Web_Milestone_1`
- Flask entry point: `Cylinder_Quote_Web_Milestone_1/run.py`
- Application factory: `Cylinder_Quote_Web_Milestone_1/app/web.py:create_app()`
- Default local address: `http://127.0.0.1:5055`
- Startup batch file: `Cylinder_Quote_Web_Milestone_1/RUN_CYLINDER_QUOTE.bat`

## 2. HTML Pages and Web Addresses

### 2.1 Portal Landing Page

- File: `Cylinder_Quote_Web_Milestone_1/app/templates/portal_landing.html`
- URL: `http://127.0.0.1:5055/`
- Route: `Cylinder_Quote_Web_Milestone_1/app/portal.py` function `landing()`
- Associated files:
  - `Cylinder_Quote_Web_Milestone_1/app/static/portal_landing.css`
  - `Cylinder_Quote_Web_Milestone_1/app/static/portal.js`
  - `Cylinder_Quote_Web_Milestone_1/app/static/portal_common.css`
- Purpose: Entry page for customer and employee login/signup choices.

### 2.2 Customer Login

- File: `Cylinder_Quote_Web_Milestone_1/app/templates/portal_login.html`
- URL: `http://127.0.0.1:5055/customer/login`
- Route: `Cylinder_Quote_Web_Milestone_1/app/portal.py` function `customer_login()`
- Connected backend: `login("customer")` in `app/portal.py`
- Associated files:
  - `Cylinder_Quote_Web_Milestone_1/app/static/portal_auth.css`
  - `Cylinder_Quote_Web_Milestone_1/app/static/portal_common.css`
- Successful destination: `/customer/dashboard`.
- Login accepts the customer username or email and password. The backend creates the session and redirects the customer to the dashboard.

### 2.3 Customer Dashboard

- HTML file: `Cylinder_Quote_Web_Milestone_1/app/customer dashboard/customer_dashboard.html`
- CSS file: `Cylinder_Quote_Web_Milestone_1/app/customer dashboard/customer_dashboard.css`
- URL: `http://127.0.0.1:5055/customer/dashboard`
- Route: `Cylinder_Quote_Web_Milestone_1/app/portal.py` function `customer_dashboard()`
- CSS route: `http://127.0.0.1:5055/customer/dashboard.css`
- Connected backend:
  - `app/portal.py` queries the signed-in customer's quotes.
  - `app/models_db.py` provides `Quote` and user models.
  - `app/db.py` provides the database session.
- Buttons and links:
  - `New Quote` -> `/customer/quote-entry`
  - `Open` -> `/quote_form_customer?quote_id=<quote id>`
  - `Log Out` -> `/logout`
- Important behavior: the dashboard-opened quote form uses `Update Order`; a newly created quote uses `Order Now`.
- Customer-facing Quote ID source: render `quote.quote_number` (for example, `B0910261342`).
- Do not render `quote.order_form_snapshot.order_number` on this page. That value is the internal Order ID (for example, `J0910261343`) created when `Order Now` submits a quote for approval.

### 2.4 Customer Calculator / New Quote

- File: `Cylinder_Quote_Web_Milestone_1/app/templates/customer_calculator.html`
- URL: `http://127.0.0.1:5055/customer/quote-entry`
- Route: `Cylinder_Quote_Web_Milestone_1/app/portal.py` function `customer_quote_entry()`
- Associated files:
  - `Cylinder_Quote_Web_Milestone_1/app/customer_quote_form/customer_quote_form.js`
  - `Cylinder_Quote_Web_Milestone_1/app/customer_quote_form/customer_quote_form.css`
  - `Cylinder_Quote_Web_Milestone_1/app/static/pricing_calculator.css`
  - `Cylinder_Quote_Web_Milestone_1/app/web.py` API routes
- Purpose: Customer enters cylinder specifications, options, discount, and manual parts, then clicks `Quote`.
- Quote flow: calculator -> `POST /api/quote/draft` -> customer quote form.

### 2.5 Customer Quote Form

- File: `Cylinder_Quote_Web_Milestone_1/app/customer_quote_form/customer_quote_form.html`
- Script: `Cylinder_Quote_Web_Milestone_1/app/customer_quote_form/customer_quote_form.js`
- Stylesheets:
  - `Cylinder_Quote_Web_Milestone_1/app/customer_quote_form/customer_quote_form.css`
- Moved asset URLs:
  - `/customer/quote-form.css` serves `customer_quote_form.css`.
  - `/customer/quote-form.js` serves `customer_quote_form.js`.
- Entry URL: `http://127.0.0.1:5055/customer/quote-entry?draft=1`
- Existing quote URL: `http://127.0.0.1:5055/customer/quote-entry?quote_id=<quote id>`
- Existing customer dashboard quote URL: `http://127.0.0.1:5055/customer/quote-form?quote_number=<quote number>`
- Legacy route note: `/quote_form_customer` redirects to `/customer/quote-form` while preserving query parameters for older saved links.
- CSS editing note: the stylesheet is read when the document is loaded. Refresh or reopen the page after editing `customer_quote_form.css`; an already-open tab will keep its existing CSS rules because the Flask app does not provide live CSS hot reload.
- Connected backend routes in `app/web.py`:
  - `POST /api/quote/draft` recalculates and builds the draft.
  - `POST /api/quotes` saves a new quote.
  - `PATCH /api/quotes/<quote id>` updates an existing quote.
  - `POST /api/quotes/<quote id>/order` submits the order request.
- Layout note: the shared Includes/Comments area in `customer_quote_form.html`
  is a fixed-height split. `.xq-includes-panel` always occupies 70% and
  `.xq-comments-panel` occupies 30%; the includes list scrolls within its
  panel when needed and stays blank when there are no included items.
- Buttons:
  - New quote: `Order Now`.
  - Existing dashboard quote: `Update Order`.
  - `Dashboard` -> `/customer/dashboard`.

### 2.6 Employee Login

- File: `Cylinder_Quote_Web_Milestone_1/app/templates/portal_login.html`
- URL: `http://127.0.0.1:5055/employee/login`
- Route: `Cylinder_Quote_Web_Milestone_1/app/portal.py` function `employee_login()`
- Connected backend: `login("employee")` in `app/portal.py`.
- Successful destination: `/employee/dashboard`.

### 2.7 Employee Dashboard

- File: `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/employee_dashboard.html`
- CSS: `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/Employees_dashboard.css`
- URL: `http://127.0.0.1:5055/employee/dashboard`
- Moved CSS URL: `http://127.0.0.1:5055/employee/dashboard.css`
- Route: `app/portal.py` function `employee_dashboard()`.
- Main functions:
  - Review and accept pending customer quotes.
  - Review and approve pending customer accounts.
  - Navigate to quote history and order history.
- Pending approval queue display:
  - `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/employee_dashboard.html`
    renders quote rows with Type `Quote`, the quote number in the Reference
    column, and the employee status label.
  - `Cylinder_Quote_Web_Milestone_1/app/Admin_Dashboard/Admin_dashboard.html`
    uses the same Type, quote-number Reference, and status display for
    administrator pending rows.
  - `Cylinder_Quote_Web_Milestone_1/app/portal.py` function
    `employee_dashboard()` prepares the row data; internal `accepted` and
    `pending` states display as `Pending Approval`.
  - Regression coverage: `Cylinder_Quote_Web_Milestone_1/tests/test_pending_approval_queue.py`.
- Connected files:
  - `Cylinder_Quote_Web_Milestone_1/app/portal.py`
  - `Cylinder_Quote_Web_Milestone_1/app/web.py`
  - `Cylinder_Quote_Web_Milestone_1/app/models_db.py`
  - `Cylinder_Quote_Web_Milestone_1/app/db.py`

### 2.8 Employee Quote and Order History

- Quote history HTML: `Cylinder_Quote_Web_Milestone_1/app/Employee_Quote_History/employee_quote_history.html`
- Quote history URL: `http://127.0.0.1:5055/employee/quote-history`
- Quote history route: `app/Employee_Quote_History/Employee_quote_history_search.py` function `employee_quote_history_page()`.
- Order history HTML: `Cylinder_Quote_Web_Milestone_1/app/employee_order_history/employee_order_history.html`
- Order history blueprint: `app/employee_order_history/Employee_order_history_search.py`, blueprint `employee_order_history`.
- Order history page URL: `http://127.0.0.1:5055/employee_order_history/employee_order_history.html`
- Order history page URL: `http://127.0.0.1:5055/employee_order_history/employee_order_history.html`.
- Order history search URL: `http://127.0.0.1:5055/employee/order-history-search?q=<text>`.
- Order history CSS and JavaScript routes are owned by the
  `employee_order_history` blueprint in
  `app/employee_order_history/Employee_order_history_search.py`, not by
  `app/web.py`.
- Order history reads matching records from `Databases/Order.db` and displays the
  saved Order ID, model code, customer, date, total, and status. The `Open` link
  returns to `/order-form?order_id=<id>`.
- Shared history CSS used by the dashboard pages: `Cylinder_Quote_Web_Milestone_1/app/static/portal_history.css`.
- The legacy portal-based `app/Employee_/employee_history.html` template has been
  removed. The standalone employee-order-history template and blueprint are the
  only implementation.
- `employee_order_history_button` is a page-local CSS class, not a custom HTML
  element or Flask component. On the order-history page its rules are in
  `Cylinder_Quote_Web_Milestone_1/app/employee_order_history/employee_order_history.css`:
  inline-block layout, red gradient background, border, shadow, white bold text,
  padding, and pointer cursor. `employee_order_history_button secondary` overrides
  the appearance with a light background, dark text, and gray border/shadow. The
  class is used on
  the New Quote, search, clear-search, and measurement-choice buttons.
- The employee order-history module does not use `portal.*` endpoint lookups.
  Its login redirect and navigation links use the existing literal URL paths.

### 2.8.1 Employee and Admin Dashboard Action Bar and Stats

- Employee dashboard HTML: `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/employee_dashboard.html`.
- Employee dashboard CSS: `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/Employees_dashboard.css`.
- Administrator dashboard HTML: `Cylinder_Quote_Web_Milestone_1/app/Admin_Dashboard/Admin_dashboard.html`.
- Administrator dashboard CSS: `Cylinder_Quote_Web_Milestone_1/app/Admin_Dashboard/admin_dashboard.css`.
- Dashboard route and header-stat calculation: `Cylinder_Quote_Web_Milestone_1/app/portal.py`, function `employee_dashboard()`.
- Current action labels omit `My`; the AI Usage Dashboard action is intentionally hidden for now.
- Action labels remain on one line, and the action bar can wrap while keeping buttons at the
  same row height as Customers.
- The current-month Quoted count uses non-canceled quotes in the signed-in user's Quote
  History ownership scope. The current-month Approved count uses approved quotes in that
  same scope with `approved_at` in the current month, matching Order History visibility.
- The dashboard search form has a `search_box` wrapper and an `X` button that clears
  the dashboard search input and hides live suggestions without submitting.
- The Customer Lookup dialog result table is vertically scrollable, allowing more
  than four customer results to be viewed within the popup.
- Employee order history and quote history also use a `search_box` wrapper with a
  page-specific `X` clear button that hides suggestions and returns focus to the input.
- Customer Accounts uses the existing `manage_users.html` template and now lists
  active, inactive, and denied customer accounts with an Active/Not Active/Denied
  status selector. Employee account status behavior is unchanged.
- Employee and admin Customer Lookup rows use the customer API fields in this order:
  Company Name, POC, Address, City, State, Zip, Phone, Email, Membership, Notes.
  Notes persist on the Customer directory record, and signed-up company/POC values
  are sourced from the matching customer User account.
- Customer directory schema additions are limited to `company_name`, `poc`, and
  `notes`, with lightweight SQLite migration in `app/db.py`.
- Working notes: `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/Employee_dashboard_notes.txt`
  and `Cylinder_Quote_Web_Milestone_1/app/Order_Form/Order_Form_Notes.txt`.

### 2.9 Customer and Employee Signup


 Customer page: `Cylinder_Quote_Web_Milestone_1/app/Landing_page/Customer_signup/customer_signup.html`
 Employee page: `Cylinder_Quote_Web_Milestone_1/app/Landing_page/Employee_signup/employee_signup.html`
 Parts catalog: `Cylinder_Quote_Web_Milestone_1/app/Parts_catalog_page/parts_catalog.html` -> `/parts-catalog`
- Manage users: `Cylinder_Quote_Web_Milestone_1/app/templates/manage_users.html` -> `/manage-users`
- Customer accounts: `Cylinder_Quote_Web_Milestone_1/app/templates/customer_accounts.html` -> `/customer-accounts`
- Employee quote form HTML: `Cylinder_Quote_Web_Milestone_1/app/Employee_quote_form/employee_quote_forms.html`
- Employee quote form script: `Cylinder_Quote_Web_Milestone_1/app/Employee_quote_form/employee_quote_form.js`
  - Served at `/employee/quote-form.js`.
  - Existing employee quotes allow the discount percentage to be edited; Net Each and dependent delivery prices update immediately, and Save/Update submits the normalized discount for server-side recalculation.
- Employee quote form stylesheet: `Cylinder_Quote_Web_Milestone_1/app/Employee_quote_form/employee_quote_form.css`
  - Served at `/employee/quote-form.css`.
  - `Update Now` updates the currently loaded saved quote.
  - `New Order` always creates a separate quote using the existing new-order save behavior.
  - The rendered employee quote sheet is editable, including displayed labels, descriptions, names, prices, dimensions, and other visible quote text; this does not expose application source code.
  - These edits are captured as plain-text and field-value data under the quote's existing `order_form_snapshot`, restored when the quote is reopened, and carried into the order snapshot.
- Order form HTML: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.html`
  - Served by `/order-form` and `/order-approval`.
- Order form CSS: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.css`
  - Served at `/order-form.css`.
- Order form JavaScript: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.js`
  - Served at `/order-form.js`.
- Connected backend: `Cylinder_Quote_Web_Milestone_1/app/web.py`.
  - `POST /api/quotes/<quote id>/order` assigns employee-submitted pending quotes to the submitting employee so the returned order form can be opened immediately.
- Approval and delete findings:
  - The employee and admin pending-approval Delete forms post to
    `app/portal.py` route `delete_pending_quote`.
  - The route soft-deletes the claimed quote by setting status `canceled`,
    `deleted_at`, and `deleted_by_user_id`, then redirects to `/employee/dashboard`.
    The canceled record remains in `Databases/Quote.db` but no longer matches the
    pending queue query.
  - `POST /api/quotes/<quote id>/order/approve` creates or updates the matching
    `orders` row in `Databases/Order.db` with the order-form snapshot.
  - The standalone employee-order-history page includes orders created, assigned, edited, or approved by
    the signed-in employee/admin through the corresponding Quote user fields.
  - `/employee/quote-history` is user-scoped to quotes created, assigned, edited,
    or approved by the signed-in employee/admin.
  - On 2026-09-15, quote numbers `K0911261653` and `B0911261630` were verified
    and moved from accepted/pending operational states to `approved` in both
    `Quote.db` and their matching `Order.db` rows for assigned employee user 2.
- Working notes:
  - `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/Employee_dashboard_notes.txt`
  - `Cylinder_Quote_Web_Milestone_1/app/Order_Form/Order_Form_Notes.txt`

### 2.12 Shared PNG Assets

- `Cylinder_Quote_Web_Milestone_1/app/PNG/Quoteformdrawing1.png`
- `Cylinder_Quote_Web_Milestone_1/app/PNG/Quoteformdrawing.png`
- `Cylinder_Quote_Web_Milestone_1/app/PNG/quote_form_logo.png`
- `Cylinder_Quote_Web_Milestone_1/app/PNG/quote_form_cylinder.png`
- `Cylinder_Quote_Web_Milestone_1/app/PNG/quote_form_cares.png`
- Image route: `/images/<filename>` in `Cylinder_Quote_Web_Milestone_1/app/web.py`.
- Active quote, order, approval, and login templates use the image route for
  the shared logo and quote drawing assets.

### 2.13 Additional Organized Files

- Admin dashboard CSS: `Cylinder_Quote_Web_Milestone_1/app/Admin_Dashboard/admin_dashboard.css`
  - Served at `/admin/dashboard.css`.
- Shared quote-form CSS: `Cylinder_Quote_Web_Milestone_1/app/Quote_Form/quote_form.css`
  - Served at `/quote-form.css` and used by customer and employee quote forms.
- Shared quote-form JavaScript: `Cylinder_Quote_Web_Milestone_1/app/Quote_Form/quote_form.js`
  - Served at `/quote-form.js`.
- Employee calculator HTML: `Cylinder_Quote_Web_Milestone_1/app/Employee_/employee_calculator.html`
  - Loaded through the `Employee_` Jinja template folder.

### 2.14 Final Organized Page Files

- Parts catalog page: `Cylinder_Quote_Web_Milestone_1/app/Parts_catalog_page/parts_catalog.html`
  - URL: `/parts-catalog`.
  - Route: `app/portal.py` function `parts_catalog()`.
- Landing page file: `Cylinder_Quote_Web_Milestone_1/app/Landing_page/Landing_page.html`.
  - Registered through the `Landing_page` Jinja template folder.
- Employee signup page: `Cylinder_Quote_Web_Milestone_1/app/Landing_page/Employee_signup/employee_signup.html`.
  - URL: `/employee/signup`.
  - Route: `app/portal.py` function `employee_signup()`.
- Customer signup page: `Cylinder_Quote_Web_Milestone_1/app/Landing_page/Customer_signup/customer_signup.html`.
  - URL: `/customer/signup`.
  - Route: `app/portal.py` function `customer_signup()`.

### 2.15 Order Form TieRod Reference

- Source workbook: `Cylinder_Quote_Web_Milestone_1/2026 JIT Order Entry V3.xlsm`.
- Source sheet: `TieRod` (worksheet table; it contains no embedded Excel chart objects).
- Browser data snapshot: `Cylinder_Quote_Web_Milestone_1/app/static/tierod_reference.json`.
  - Normalizes 160 TieRod selector rules and 66 separate MT4 calculation-rule records.
  - Generated from the workbook for local browser use; the workbook is not loaded at runtime.
- Consumer: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.js`.
  - Matches the quote's Series, Bore, Rod, and Mount values against normalized TieRod rules, including the separate MT4 mount rule set.
  - Populates only the existing bottom Testing Data `Tie Rod` row's `Bore / Diameter`, `Length`, and `Thread` fields.
  - Keeps the quote's existing Stop Tube value for the MT4 `Stop Tube/ET` field until the MT4 runtime input/output contract is implemented.

The normalized TieRod artifact is intentionally limited to the Order Form testing section. It does not participate in pricing, quote calculation, approval, persistence, or any other page.

### 2.16 Order Form Testing Weight Source

- Order Form testing renderer: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.js` function `engineeringOutputs()`.
- Workbook sources: `Cylinder_Quote_Web_Milestone_1/2026 JIT Order Entry V3.xlsm`, `Data!S31:X56` for H/HM and `Data!Y31:AD48` for A/LH.
- Offline extraction: `Cylinder_Quote_Web_Milestone_1/scripts/extract_sheet_h.py` uses pandas to normalize the A/LH `Y:AD` chart into `Cylinder_Quote_Web_Milestone_1/app/static/sheet_h_engineering.json` as `weight_rules`.
- Rule: the matching family-specific bore/rod row displays base weight plus weight-per-inch times stroke; the result is shown in the Barrel testing row as `Weight <value>`.
- Family selection: A and LH use the `Y:AD` chart; H and HM use the `S:X` chart/fallback table.
- Source notes: `Cylinder_Quote_Web_Milestone_1/app/Pricing/H_Sheet_Notes.txt`.

## 3. Shared Backend and Data Connections

### 3.1 Flask Route and Application Layer

- `Cylinder_Quote_Web_Milestone_1/app/web.py`
  - Creates the Flask app.
  - Registers API routes for calculation, drafts, quotes, customers, PDFs, email logging, ordering, approval, and documents.
  - Connects requests to the pricing and quote services.
- `Cylinder_Quote_Web_Milestone_1/app/portal.py`
  - Registers portal pages, authentication, dashboard pages, account approval, quote approval, and administration routes.
- `Cylinder_Quote_Web_Milestone_1/app/quote_service.py`
  - Builds quote snapshots, saves quote edits, duplicates quotes, and converts quote records to JSON.
  - Persists employee quote-form edits inside the existing quote/order snapshot without changing the pricing snapshot.
- `Cylinder_Quote_Web_Milestone_1/app/service.py`
  - Builds quote drafts and performs server-side calculation.

### 3.2 Pricing and Catalog

- `Cylinder_Quote_Web_Milestone_1/cylinder_quote_engine/engine.py` - Pricing engine.
- `Cylinder_Quote_Web_Milestone_1/cylinder_quote_engine/models.py` - Pricing models.
- `Cylinder_Quote_Web_Milestone_1/cylinder_quote_engine/data.py` - Pricing data access.
- `Cylinder_Quote_Web_Milestone_1/app/catalog.py` - Catalog construction.
- `Cylinder_Quote_Web_Milestone_1/app/pricing_catalog_service.py` - Catalog and parts catalog operations.
- `Cylinder_Quote_Web_Milestone_1/pricing_data/` - Normalized pricing data.

### 3.3 Database and Models

- `Cylinder_Quote_Web_Milestone_1/app/db.py` - SQLite engine and sessions.
- `Cylinder_Quote_Web_Milestone_1/app/models_db.py` - SQLAlchemy models.
- `Cylinder_Quote_Web_Milestone_1/Databases/Quote.db` - Quotes, quote items, quote documents, approvals, and quote numbering.
- `Cylinder_Quote_Web_Milestone_1/Databases/Order.db` - Submitted order snapshots.
- `Cylinder_Quote_Web_Milestone_1/Databases/User_accounts.db` - Users and account approval.
- `Cylinder_Quote_Web_Milestone_1/Databases/Employee_Contacts.db` - Customer contacts.
- `Cylinder_Quote_Web_Milestone_1/Databases/Pricing.db` - Catalog and price data.

## 4. Main Workflows

### 4.1 Customer Login to Dashboard

1. Customer opens `http://127.0.0.1:5055/customer/login`.
2. `portal.py` validates the username/email and password.
3. The session is created.
4. The customer is redirected to `http://127.0.0.1:5055/customer/dashboard`.
5. `customer_dashboard.html` displays that customer's saved quotes.

### 4.2 New Customer Quote

1. Customer clicks `New Quote` on the dashboard.
2. Customer fills in `customer_calculator.html`.
3. Customer clicks `Quote`.
4. `POST /api/quote/draft` sends the data to server-side calculation.
5. `customer_quote_form.html` displays the calculated quote.
6. The button says `Order Now` for this new quote.
7. Saving uses `POST /api/quotes`, then ordering uses `POST /api/quotes/<quote id>/order`.

### 4.3 Existing Customer Quote

1. Customer clicks `Open` beside a quote on the dashboard.
2. The browser opens `/customer/quote-entry?quote_id=<quote id>`.
3. The quote is loaded by `GET /api/quotes/<quote id>`.
4. The button says `Update Order` so the customer does not mistake it for a new cylinder order.
5. Saving changes uses `PATCH /api/quotes/<quote id>`.

### 4.4 Employee Acceptance Workflow

1. A customer signup creates an account awaiting approval.
2. An employee opens `/employee/dashboard`.
3. The employee uses the acceptance controls in `employee_dashboard.html`.
4. The approval POST route in `app/portal.py` updates the account or quote status in the database.

### 4.5 Pending Approval Quote Lifecycle

1. A quote with status `pending_approval` and no employee assignment appears in
  the `New Accept Request` queue on the employee/admin dashboard.
2. `POST /employee/quotes/<quote id>/accept` assigns the quote to the employee
  who accepted it and moves it to that employee's `Pending Approvals` section.
  The dashboard Type is `Pending Approval`; “Accepted Pending Quote” is not a
  workflow type or status.
3. Opening the accepted quote and then returning to the dashboard without
  submitting the order leaves its status as `pending_approval`; it is a limbo
  quote awaiting a decision, not an order.
4. The current `Quote` schema records creation, assignment, edits, email, and
  final approval timestamps, but it does not record a separate opened/viewed
  event or a customer-read receipt. An `assigned_at` value proves the quote
  was claimed by an employee, not the exact time its form was opened.
5. Pending approval quotes remain in employee quote history at
  `/employee/quote-history` but are excluded from employee order history at
  the standalone employee-order-history page until the order is approved.
6. Identifier contract: customer quote pages and the customer dashboard display
  `Quote.quote_number`; employee order/approval pages may display the separate
  `order_form_snapshot.order_number`. The latter must never replace the customer
  Quote ID.
7. The Order Form provides `Approve Order` and `Deny Order` actions. Denial
  changes both the quote and order snapshot to `denied`; denied records remain
  visible in both history pages but are sorted to the bottom.
8. The shared dashboard route selects `Admin_dashboard.html` for admin
  employees and `employee_dashboard.html` for standard employees. Both use
  the same `pending_queue` data from `app/portal.py`.

Connected files:
- `Cylinder_Quote_Web_Milestone_1/app/portal.py`
- `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/employee_dashboard.html`
- `Cylinder_Quote_Web_Milestone_1/app/Admin_Dashboard/Admin_dashboard.html`
- `Cylinder_Quote_Web_Milestone_1/tests/test_pending_approval_queue.py`

## 5. API Route Index

- `GET /api/health` - Health check.
- `GET /api/catalog` - Calculator catalog data.
- `POST /api/calculate` - Server-side cylinder calculation.
- `POST /api/quote/draft` - Validates and builds a quote draft.
- `POST /api/quotes` - Saves a new quote.
- `GET /api/quotes/<quote id>` - Loads a quote.
- `PATCH /api/quotes/<quote id>` - Updates a quote.
- `POST /api/quotes/<quote id>/order` - Submits an order request.
- `POST /api/quotes/<quote id>/approve` - Processes quote approval.
- `GET /api/quotes/<quote id>/documents/<document id>` - Retrieves a quote document.
- Customer/catalog API routes are implemented in `app/web.py` and `app/portal.py`; search there before adding a duplicate route.

## 6. Maintenance Rules for This Map

- Record the full repository-relative path whenever a file moves.
- Record the browser URL beside every user-facing page.
- Record the route function and connected JavaScript/CSS/backend files.
- Update the workflow section when a button, redirect, API route, or database destination changes.
- Treat `Cylinder_Quote_Web_Milestone_1/` as the active application. Files in `_archive/` are historical builders and are not active runtime code.
- Do not document an old path as active after a move. Keep historical paths only in a clearly marked archive note when needed.

## 7. Reference Documentation

- `AGENTS.md` - Project scope, protected pricing rules, and workflow constraints.
- `PROJECT_SPEC.md` - Current product and architecture specification.
- `docs/ARCHITECTURE_MAP.md` - Architecture notes.
- `docs/business-rules.md` - Business and pricing rules.
- `docs/Project_table_of_contents.md` - This maintained navigation map.
