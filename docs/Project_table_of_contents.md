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

### 2.4.1 Employee Calculator Customer Search

- Employee entry URL: `http://127.0.0.1:5055/employee/quote-entry`.
- Route: `Cylinder_Quote_Web_Milestone_1/app/portal.py` function
  `employee_quote_entry()`.
- Employee wrapper: `Cylinder_Quote_Web_Milestone_1/app/Employee_/employee_calculator.html`.
- The customer input itself is in the shared template
  `Cylinder_Quote_Web_Milestone_1/app/templates/index.html`, element
  `#customer_name`, with the `#customerNameList` HTML datalist.
- Search JavaScript: `Cylinder_Quote_Web_Milestone_1/app/static/app.js`.
  `wireCustomerAutocomplete()` waits 250 ms after at least two characters are
  typed, then `searchCustomers()` requests `GET /api/customers/search?q=<text>`
  and fills the datalist with the returned customer names.
- Search route: `Cylinder_Quote_Web_Milestone_1/app/web.py`, function
  `search_customers()`. It searches only company name, legacy name, and POC for
  case-insensitive substring matches (`%query%`) anywhere in the typed character
  sequence, orders by customer name, and returns all matching contacts. Address,
  city/state/zip, shipping address, phone, email, and notes are not search fields.
- Customer data source: `Cylinder_Quote_Web_Milestone_1/Databases/Employee_Contacts.db`.
  `Customer` is bound to this database through `app/db.py`.
- Selection behavior: the browser displays the returned company name, POC, and
  legacy name values in the datalist. A selected contact is recognized only
  when the typed value exactly matches one of those returned names
  case-insensitively; then the contact phone and email are stored together in
  the quote's `Phone/Email` field, and the address is copied when the address
  field is blank.
- Quote-form handoff: the shared calculator includes the selected customer's
  phone in `customer_contact` when it creates the server-side quote draft, so
  both the customer and employee Quote Forms populate their `Phone/Email`
  field without requiring manual re-entry.
- Regression protection: `Cylinder_Quote_Web_Milestone_1/tests/test_customer_lookup.py`
  verifies substring matches across the three name fields and rejects matches
  found only in excluded contact fields. The JavaScript trigger
  and server-side query are the permanent owners of this behavior; do not restore
  one-character requests, a ten-result cap, or client-only filtering.
- The dashboard Customer Lookup dialog is a separate search surface from the JIT
  Crew Calculator Customer input. Its handlers are embedded in the employee and
  admin dashboard templates. Both wait for two characters and use the same
  three-name-field substring API, preserving the live-search behavior documented
  in the September 16 change log.
- Guardrail test: `tests/test_customer_lookup.py` verifies the API search fields
  and checks that all three search surfaces retain the two-character trigger.
- Source protection note: an application-level four-digit PIN cannot securely
  prevent repository edits because the code containing the PIN can also be edited.
  Protect this behavior with repository permissions, protected branches and
  required review, or a read-only policy outside the application.

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
- The form posts back to the current login path with fields `identity` and
  `password`; `identity` accepts an active employee's username or email,
  case-insensitively.
- A successful login clears the prior session, stores `user_id` and `role`,
  and redirects through `safe_next()` to the employee dashboard. A failed
  credential check stays on the login page with the message `The
  username/email or password did not match.`.

### 2.6.1 Employee Dashboard Runtime Diagnosis (2026-09-16)

- The shared route is `GET /employee/dashboard` in
  `Cylinder_Quote_Web_Milestone_1/app/portal.py`, protected by
  `require_role("employee")`.
- The route selects `Admin_dashboard.html` when the signed-in employee has
  `access_level == "admin"`; standard employees receive
  `employee_dashboard.html`. Both templates use the same dashboard data
  prepared by `employee_dashboard()`.
- Kane Whiteside's local database record was verified as user ID `2`, active,
  role `employee`, and access level `admin`. Replaying
  `GET /employee/dashboard` through the current source and local interpreter
  returned HTTP 200 and rendered the administrator dashboard.
- During the browser 500 incident, three separate `run.py` Python processes
  (PIDs `34288`, `41212`, and `21544`) were simultaneously listening on port
  `5055`. This is a runtime/process-state finding, not a confirmed bad link or
  reproducible route/template exception. Stop the duplicate local Flask
  processes and start one instance before treating a later 500 as an
  application-code failure.

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
- Quote history URL: `http://127.0.0.1:5055/employee_quote_history/employee_quote_history.html`
- Quote history route: `app/Employee_Quote_History/Employee_quote_history_search.py` function `employee_quote_history_page()`.
- Quote history ordering: pending statuses (`accepted`, `pending_approval`,
  and `pending`) appear first, followed by approved quotes; each group remains
  newest first and oldest last. Approved quotes use the recorded `approved_at`
  timestamp written when the employee clicks `Approve Order`; quote ID is not
  used as the approval timestamp.
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
- The active administrator and employee dashboards now keep their shared table,
  search, empty-state, suggestion, status, modal, and responsive rules in
  their dedicated stylesheets. The active application has no remaining
  `portal_history.css` references. Archived build scripts and the separate
  `.kilo` worktree still contain historical references and were left untouched.
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
- The predicted-results popup directly below the employee dashboard search box is
  the `div#searchSuggestions` live suggestions container, styled by the
  `.suggestions` CSS class, in
  `Cylinder_Quote_Web_Milestone_1/app/Employee_dashboard/employee_dashboard.html`.
- The Customer Lookup dialog result table is vertically scrollable, allowing more
  than four customer results to be viewed within the popup.
- Employee order history and quote history also use a `search_box` wrapper with a
  page-specific `X` clear button that hides suggestions and returns focus to the input.
- Both history search boxes use the same live search suggestions popup pattern:
  `div#searchSuggestions` with the `.suggestions` class in
  `Cylinder_Quote_Web_Milestone_1/app/employee_order_history/employee_order_history.html`
  and
  `Cylinder_Quote_Web_Milestone_1/app/Employee_Quote_History/employee_quote_history.html`.
  Their page-specific JavaScript renders order or quote suggestion links into
  that container, and the matching page-specific CSS positions it below the form.
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

### 2.8.2 Quote Acceptance, Order Approval, and Duplicate-Record Trace

- Acceptance route: `Cylinder_Quote_Web_Milestone_1/app/portal.py`,
  `accept_pending_quote()` at `POST /employee/quotes/<quote_id>/accept`.
  It updates the existing `Quote` to `accepted`, assigns the employee, and
  synchronizes an existing linked `Order`; it does not create a quote.
- Acceptance redirect: the employee and administrator dashboard scripts route
  to `/employee/quote-entry?quote_id=<quote id>&accepted=1`. This opens the
  employee Quote Form. The `accepted=1` marker is removed after loading.
- Order submission route: `Cylinder_Quote_Web_Milestone_1/app/web.py`,
  `submit_order_for_approval()` at
  `POST /api/quotes/<quote_id>/order`. It updates the quote and creates an
  `Order` row only if no row exists for that `quote_id`.
- Approval route: `app/web.py`, `approve_internal_order()` at
  `POST /api/quotes/<quote_id>/order/approve`. It updates the same `Quote` to
  `approved` and updates or creates the linked `Order`; approval does not
  allocate a new quote number.
- Quote-number creation paths: `POST /api/quotes` creates a new quote, and
  `POST /api/quotes/<quote_id>/duplicate` deliberately creates a fresh quote
  with a new number. These are separate from acceptance and approval.
- Diagnostic distinction: Quote History reads `Quote` records while Order
  History reads `Order` records linked by `Order.quote_id`. A pending and an
  approved quote with different quote numbers proves a second quote record was
  created elsewhere in the workflow. Two order-history rows must be checked by
  `Order.id`, `Order.quote_id`, and
  `order_form_snapshot.order_number` before deciding whether they are duplicate
  database rows or two projections of one workflow.
- Detailed incident trace: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/Order_Form_Notes.txt`,
  section `Duplicate quote/order investigation - 9/16/2026`.

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
  - `Update Now` and `Order` are sibling `type="button"` controls with distinct
    IDs. Their inline click handlers stop propagation so clicking one does not
    also trigger a parent toolbar action for the other.
  - The rendered employee quote sheet is editable, including displayed labels, descriptions, names, prices, dimensions, and other visible quote text; this does not expose application source code.
  - These edits are captured as plain-text and field-value data under the quote's existing `order_form_snapshot`, restored when the quote is reopened, and carried into the order snapshot.
- Order form HTML: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.html`
  - Served by `/order-form` and `/order-approval`.
- Order Form toolbar actions:
  - `Cancel` confirms the user wants to discard unsaved edits, then returns to
    `/employee/dashboard` without calling an order or quote API.
  - `Approve Order` sends the current editable form snapshot to
    `POST /api/quotes/<quote id>/order/approve`. The backend marks the quote and
    matching order `approved`, records the approving employee and timestamp,
    creates or updates the matching `Order.db` row, and the page redirects to
    `/employee_quote_history/employee_quote_history.html` after success. The
    employee quote-history page searches all non-deleted quotes in `Quote.db`,
    so the newly approved quote appears there with status `Approved`.
  - After approval, the quote no longer matches the employee or administrator
    dashboard `Pending Approvals` query because those queues accept only
    `accepted`/`pending_approval` records. The approved quote remains available
    through employee quote history and order history.
- Order form CSS: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.css`
  - Served at `/order-form.css`.
- Order form JavaScript: `Cylinder_Quote_Web_Milestone_1/app/Order_Form/order_form.js`
  - Served at `/order-form.js`.
  - Preserves each part's unit price for Order Form calculations and displays Cost as unit price multiplied by Allocated; ordinary one-per-cylinder parts use allocated quantity `1`.
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
  - The standalone quote-history page searches all quotes in `Quote.db` and is
    independent of employee ownership metadata.
  - Each order-history row has a confirmed `Delete` POST action at
    `/employee/order-history/<order_id>/delete`; it removes that order snapshot
    from the active list by moving it to recoverable Trash in
    `Order.db` while leaving the related quote record intact. The Trash view
    restores it through `/employee/order-history/<order_id>/restore`.
  - Each quote-history row has a confirmed `Delete` POST action at
    `/employee_quote_history/<quote_id>/delete`; it follows the existing audit
    convention by moving the quote to recoverable Trash as `canceled` and
    recording the deleting employee, timestamp, and previous status in
    `Quote.db`. The Trash view restores it through
    `/employee_quote_history/<quote_id>/restore`.
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

### 2.14 Dedicated Inventory Workflow

- Inventory source and normalization: `Cylinder_Quote_Web_Milestone_1/app/inventory_service.py`.
  XLSM and CSV imports use the workbook `Inventory` field when present; otherwise
  they derive quantity from `On Hand - Allocated`. Quantities are normalized with
  ceiling rounding to whole numbers.
- Dedicated persistence: `Cylinder_Quote_Web_Milestone_1/app/db.py` and
  `Cylinder_Quote_Web_Milestone_1/app/models_db.py` use `Inventory.db` and the
  `InventoryPart` model. Dedicated inventory quantities overlay matching Parts
  Catalog rows without writing fractional values to the legacy pricing catalog.
- Inventory administration routes: `Cylinder_Quote_Web_Milestone_1/app/portal.py`
  provides admin-only preview/apply import, search, and individual-edit actions.
- Parts Catalog controls: `Cylinder_Quote_Web_Milestone_1/app/Parts_catalog_page/parts_catalog.html`
  includes the Inventory Manager for CSV/XLSM import, preview/apply, search, and
  individual quantity updates. Existing price and catalog controls are preserved.
- Regression coverage: `Cylinder_Quote_Web_Milestone_1/tests/test_inventory_management.py`
  verifies rounding, preview/apply persistence, search, individual editing,
  unmatched imported parts, and dedicated-quantity display.

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

### 2.17 Order Form Allocation and On-Hand Mapping

- Workbook source: `Cylinder_Quote_Web_Milestone_1/2026 JIT Order Entry V3.xlsm`.
- Source sheet: `Order Form`, parts table rows `13:44`.
- Verified column mapping from `Order Form!C13:H44`:
  - `C` = Part #.
  - `D` = Description.
  - `E` = Cost.
  - `F` = On Hand.
  - `G` = Allocated.
  - `H` = allocation warning/selection flag.
- `Order Form!H13:H44` uses the same row-relative formula pattern:
  `IF(OR(Drow="Air REH Head", Drow="Air BEH Head", Drow="Hyd REH Head", Drow="Hyd BEH Head", Drow="Head", Drow="Barrel", Drow="Rod", Drow="Stainless Steel Rod", Drow="Tie Rod"), "X", IF(Grow>Frow, "X", ""))`.
  Built-in cylinder components therefore receive `X`; other parts receive `X` when allocated quantity exceeds on-hand quantity.
- Workbook source sheet: `Inventory`, row `1` headers and rows `2:1029` data.
  - `A` = Part Number.
  - `B` = Product Description.
  - `C` = Unit Price.
  - `D` = On Hand.
  - `E` = Allocated.
  - `F` = Start 2025.
  - `G` = On Order.
  - `H` = Inventory/available quantity.
- `Inventory!Hrow` is calculated as `Drow-Erow`.
- `Inventory!Erow` contains selector formulas that reference the current cylinder inputs on `Data` and helper values on `H`; the formula family varies by part. Examples verified during read-only analysis include tie rod, rod, barrel, tie-rod nuts, barrel seal, gland backup seal, rod wiper, rod seal, and piston seal rows.
- Cached formula values are available in the workbook for the current saved input state, but formulas must be reproduced as application rules or normalized data. The Flask application must not load the XLSM at runtime.

### 2.18 September 18, 2026 Scoped Findings

- The administrator dashboard shell now uses the same capped responsive width as the employee quote-history shell: `min(1200px, 96vw)`.
- The Order Form toolbar keeps Dashboard and Cancel first, then Email Customer, Add Part, Deny Order, and Hold, followed by the plain-text status and Approve Order. Toolbar controls are fixed to single-line labels so their widths do not change from text wrapping.
- The Order Form status is text-only; the prior pill outline, radius, and status background colors are removed. The status element remains `#orderStatus` so the existing status logic is not changed.
- Existing Order Form JavaScript already preserves part unit prices and recalculates displayed Cost as unit price multiplied by Allocated. The remaining cost-display investigation belongs to the Order Form data/API path, not the HTML/CSS presentation layer.
- The pending-approval queue, New Accept Request filtering, save/modify timestamp ordering, quote/order button isolation, and page load-time behavior are controlled by backend and JavaScript owners outside the isolated dashboard/history/order-form HTML/CSS edit set. These must be traced before editing so the verified pricing engine and existing user changes are not overwritten.
- The customer-search contract documented elsewhere in this table of contents remains protected: two-character minimum, case-insensitive substring matching, exact typed sequence, and only Company Name, POC, and legacy Customer Name as search fields. Contact/address fields are returned data, not search fields.

#### 2.18.1 September 18 Behavior Diagnosis Before Fixes

- `app/portal.py:employee_dashboard()` currently sends all unassigned `new` or `pending_approval` quotes to New Accept Request. `app/quote_service.py:create_quote_snapshot()` currently creates both customer and employee quotes with `status="new"`; this is the confirmed owner of employee quotes appearing in the new-request queue.
- The same dashboard function limits Pending Approvals to assigned quotes and sorts by `created_at.asc()`. The requested newest-first saved/modified behavior requires `edited_at.desc()` with a created-time fallback.
- `app/Employee_quote_form/employee_quote_form.js:createNewOrder()` calls the shared `saveQuote(false, true)` path. That function PATCHes the quote before POSTing `/api/quotes/<id>/order`, confirming the current Order/Update coupling.
- `app/Order_Form/order_form.js:load()` waits serially for the quote, TieRod reference JSON, and engineering JSON. These independent loads are the confirmed local source of avoidable startup delay.
- The Inventory Manager markup has no formula column. Formula guidance must be display-only in that manager and must not be connected to calculator or Order Form allocation logic.
- Current customer search remains protected and correct: `app/web.py:search_customers()` searches only company name, legacy name, and POC by substring, while `app/static/app.js:wireCustomerAutocomplete()` waits for two characters.
- Focused pytest was blocked by the terminal using system Python without the application import path (`ModuleNotFoundError: No module named 'app'`).
- Implemented Order Form integration: `app/component_bom.py` enriches part rows from `Inventory.db` by matching `part_number`; `inventory_parts.inventory` populates `F` On Hand and `inventory_parts.allocated` populates `G` Allocated when present. Existing generated-part defaults remain as fallback when no Inventory.db row exists.
- `app/quote_service.py` exposes normalized `order_form_parts` rows in the quote JSON payload, covering generated, special, and manual parts. `app/Order_Form/order_form.js` renders that payload and uses Inventory.db values for catalog parts added through its search dialog.
- The existing `parts_catalog.html` inventory display remains an editor/source view and is not the allocation calculation engine.
- Regression coverage: `tests/test_order_form_inventory.py` verifies Inventory.db values reach catalog search results and generated quote Order Form payloads.

#### 2.17.1 Exact Excel Inventory Allocation Flow (2026-09-17)

- The Excel allocation decision is made independently by each populated `Inventory!E` formula. The workbook does not first select parts by sorting a candidate list.
- The `Shipped_Click` macro sorts `Inventory!A1:J10000` by `Inventory!E2` in descending order after the row formulas calculate allocated quantities.
- The Order Form then reads only `Inventory` rows `2:32` after that sort. Positive allocated rows therefore become the first 31 displayed parts; rows beyond that display window are not transferred to the Order Form.
- Displayed extended cost is allocated quantity multiplied by the Inventory unit price. This is separate from the allocation decision itself.
- Confirmed `Data` inputs used by the Inventory allocation formulas:
  - `B2` cylinder quantity.
  - `B3` series.
  - `B4` bore.
  - `B5` mount.
  - `B6` rod diameter.
  - `B7` cushion configuration.
  - `B8` stroke.
  - `B10` seal material.
  - `B11:B27` optional features.
  - `G9:G22` accessory quantities.
  - `F26:G32` custom part-number/quantity pairs.
  - `B25` extra tie rod.
  - `B16` is labeled `UltraOx` on the Data sheet, while the VBA control that writes it is named `TextBoxSSTieRod`.
- Remaining implementation requirement: reproduce the Inventory column E selector formulas as application rules or normalized data, then apply the Excel sort and 31-row transfer behavior. `app/component_bom.py` still uses a fixed candidate list and does not yet provide complete formula parity.

#### 2.17.2 Order Form Parts Placement Investigation (2026-09-18)

- The current Order Form comparison sequence requested from the Excel `Order Form` sheet is: Tie Rod, Rod, Barrel, Tie Rod Nuts, Piston Seal, Barrel Seal, Gland Oring Backup Seal, Rod Wiper, Rod Seal, Piston ID Oring Seal, Gland Oring Seal, Gland, REH Head, BEH Head, Piston, and Mount.
- `app/component_bom.py` now preserves this generated-part sequence in the server payload and limits the displayed window without reordering by Allocated. Special and manual rows remain after generated rows in their existing order.
- Regression coverage is in `tests/test_order_form_inventory.py` for the sequence helper and the generated H 5-inch / 2-inch rod part list.
- This placement change does not change pricing, allocation quantities, unit costs, or engineering lengths.
- Open parity investigation: verify the exact workbook formulas/reference rows for Tie Rod Cost and Allocated and for Rod Price/Allocated before changing runtime calculations. The remembered relationship involving stroke, barrel/nut/gland dimensions, thread allowance, four tie rods, and unit price is only a lead and is not yet verified.

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

### 3.2.1 Inventory Baseline and Planned Integration Surface

- Workbook source: `Cylinder_Quote_Web_Milestone_1/2026 JIT Order Entry V3.xlsm`.
- Workbook sheet: `Inventory` (visible, range `A1:T1029`).
- Verified source columns on row 1:
  - `A` Part Number.
  - `B` Product Description.
  - `C` Unit Price.
  - `D` On Hand.
  - `E` Allocated.
  - `F` Start 2025.
  - `G` On Order.
  - `H` Inventory.
- Workbook behavior observed during read-only extraction:
  - `H` is calculated as `D-E` for the visible inventory quantity.
  - `E` contains selector formulas referencing the `Data` and `H` sheets to calculate allocation for the current cylinder inputs.
  - Cached values are present when the workbook is loaded with `data_only=True`; the workbook must remain a read-only source artifact and must not be loaded by the Flask application at runtime.
- Authoritative inventory database: `Cylinder_Quote_Web_Milestone_1/Databases/Inventory.db`.
  - Current table: `inventory_parts`.
  - Columns: `part_number`, `product_description`, `inventory`, `allocated`, `start_2025`, `on_order`, `updated_by`, `updated_at`, and `source_name`.
  - All inventory, on-hand, and allocation application work must use this database. Do not introduce a second inventory store or use `Pricing.db` as the inventory authority.
- Current catalog storage: `Cylinder_Quote_Web_Milestone_1/Databases/Pricing.db`, table `catalog_parts`, currently includes an `inventory INTEGER` column and 1,201 catalog rows.
- Current parts catalog page: `Cylinder_Quote_Web_Milestone_1/app/Parts_catalog_page/parts_catalog.html`, served at `/parts-catalog`.
  - The Parts Catalog table has an Inventory column that is initially populated from `catalog_parts.inventory`.
  - The page has an Inventory visibility toggle, inline inventory editing, selected-part bulk inventory updates, and an inventory bulk-update modal.
  - Admin users double-click catalog data cells, including Vendors and Inventory Source, to edit them directly in the table; those edits use the existing row update endpoint. Non-admin users do not enter the inline editor.
  - Vendors, Price Location, and Inventory Source place their edit metadata on the full table cell, so admin users can double-click and enter values in empty cells.
  - Common Modifications and PH / VA Pricing table cells are admin-only double-click editors for text and numeric values. Blank numeric values still render as available price editors so every pricing cell can be edited.
- Current inventory editing backend:
  - `app/pricing_catalog_service.py` function `update_catalog_part()` validates non-negative whole-number inventory values and writes them to `catalog_parts.inventory`.
  - `app/pricing_catalog_service.py` function `update_catalog_inventory_bulk()` sets one validated inventory value for selected catalog rows.
  - `app/portal.py` route `POST /parts-catalog/parts/<row_id>` handles individual catalog-part edits.
  - `app/portal.py` route `POST /parts-catalog/inventory/bulk` handles selected-part bulk quantity updates.
- Not yet implemented: workbook/CSV inventory import, inventory search/edit page, inventory transaction history, or order-time inventory decrement tied to approved/created orders. These remain implementation scope items and are not yet active behavior.
- Scope lock for the allocation work: preserve existing code and add only the smallest directly required behavior. Do not refactor, replace, or modify unrelated pages, routes, pricing logic, or catalog behavior.

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
5. Pending approval quotes remain in the standalone employee quote history but
  are excluded from employee order history at
  the standalone employee-order-history page until the order is approved.
6. Identifier contract: customer quote pages and the customer dashboard display
  `Quote.quote_number`; employee order/approval pages may display the separate
  `order_form_snapshot.order_number`. The latter must never replace the customer
  Quote ID.
7. The Order Form provides `Approve Order` and `Deny Order` actions. Denial
  changes both the quote and order snapshot to `denied`; denied records remain
  visible in both history pages but are sorted to the bottom.
8. The employee and administrator dashboard `Pending Approvals` row `Open`
  action routes to `/order-form?quote_id=<quote id>`, where `Approve Order`
  changes the quote and matching order status to `approved`. It must not route
  to `/employee/quote-entry`, whose employee Quote Form has `Order` and `Hold`
  actions but no approval action.
9. The shared dashboard route selects `Admin_dashboard.html` for admin
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

## 8. Rod-Length Calculation Findings (2026-09-18)

- Workbook source: `Cylinder_Quote_Web_Milestone_1/2026 JIT Order Entry V3.xlsm`, Sheet `H`. The `~$2026 JIT Order Entry V3.xlsm` file is an Excel temporary lock file; it is not the calculation source.
- Sheet H rod allocation formula: `Inventory!E3` uses `Data!B2 * (Data!B8 + H!AD$7)` for the standard Rod row, where `Data!B2` is cylinder quantity and `Data!B8` is stroke.
- Sheet H rod addition formula: `H!AD7 = H!AS64 + H!BB50 + Data!B11 + Data!B27`. The Sheet H helper selectors provide the mount, cushion, and rod-style-dependent addition.
- The active Order Form script already loads the verified normalized Sheet H reference at `/static/sheet_h_engineering.json` for engineering output. `app/Order_Form/order_form.js` now applies `stroke + rod addition` to the existing Rod part row's Allocated value and recalculates its extended Cost using the preserved unit price.
- `Databases/Pricing.db` now contains the isolated `rod_length_rules` table. It stores 4,020 normalized Sheet H rows with family, bore, rod diameter, cushion, rod style, rod-length addition, source cell, helper cell, workbook, and sheet provenance. The existing Pricing.db tables were not changed.
- The runtime must continue to use normalized rule data and must not load the XLSM workbook.
