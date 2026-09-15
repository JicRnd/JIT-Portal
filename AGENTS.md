# JIT Cylinder Quote HTML - Agent Instructions

## Project purpose
This repository is the active JIT Cylinder Quote web application. Maintain and extend the existing application according to the user's current requests while preserving verified pricing behavior, existing workflows, database integrity, and regression-tested functionality.

Current user instructions override older historical scope statements when they conflict. Existing implemented features are considered valid project scope unless the user explicitly asks to remove them.

Repository preservation rule: treat all content in GitHub and this repository
as user-owned. Never revert, reset, checkout, restore, overwrite, normalize,
or re-baseline repository content unless the user explicitly requests that
exact operation. Preserve tracked and untracked changes, including unrelated
changes.

Unrelated-change rule: do not modify unrelated work in any capacity. This
includes indirect cleanup, formatting, refactoring, renaming, imports, CSS,
templates, tests, documentation, configuration, generated files, or neighboring
pages. A file may change only when explicitly in the current request's scope or
when a direct dependency is proven necessary and reported before editing.

No unsolicited improvement rule: do not optimize, modernize, polish, simplify,
redesign, generalize, harden, or enhance anything unless the user directly asks
for that specific improvement. Implement the smallest exact requested change
and stop.

## Workspace root
Expected Windows project root:

`C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML`

The currently working Flask application is expected under:

`Cylinder_Quote_Web_Milestone_1\`

Inspect the repository before changing code.

## Read before editing
Before making meaningful changes:
1. Read this `AGENTS.md` completely.
2. Read `PROJECT_SPEC.md` completely.
3. Inspect the existing Flask app, pricing engine, normalized data, tests, README files, and relevant dissection/parity reports.
4. Search the project for an existing implementation before adding a new one.
5. Run the current test suite and record the baseline.

## Critical rule: protect Pricing Engine v1.2
The current pricing engine is the most protected component in this project.

It was built from a ten-section reverse engineering of the Excel workbook and has already undergone source-table extraction, normalization, Excel-to-Python parity work, accessory normalization, complete quote parity scenarios, and browser/API validation.

Do not rewrite, simplify, modernize, or remove compatibility behavior merely because a rule looks unusual.

If a change appears to affect pricing:
1. identify the existing rule and source;
2. add/update a regression test first when practical;
3. make the smallest change possible;
4. run all pricing tests;
5. do not proceed with a failing pricing suite.

## Pricing authority
The current verified pricing engine and current normalized pricing data are authoritative.

Historical order prices may reflect older price revisions or manual conditions. Do not alter current pricing merely because an old order differs.

## UI requirements already established
The OrderEntry-style web UI must preserve:
- Seal code `P`;
- Style `4 - Safety Coupler`;
- blank-slate startup;
- field sequence: Series, Mount, Bore, Stroke, Rod, Style, Cushion, Ports, Seal, DRE;
- familiar Excel OrderEntry spatial layout;
- proportional whole-form scaling based on both browser width and height;
- Discount / Net Each / Profit clearly separated from the Quote button.

Preserve user muscle memory. Do not redesign the calculator unless the current milestone specifically requires a usability correction.

## Browser/server boundary
Authoritative pricing remains server-side.

Preferred flow:

`OrderEntry HTML/JS -> Flask/API -> Pricing Engine v1.2 -> normalized data`

The new quote workflow for this milestone is:

`OrderEntry -> server-side recalculation -> Quote Form HTML -> local Save Quote database action`

Client-side JavaScript may improve responsiveness but is never the sole pricing authority.

## Manual special-order items
The Parts / Description / Qty / Price area must support user-entered items that do not exist in the model-code system or standard catalog.

A manual line item should support at least:
- optional reference/part number;
- description;
- quantity;
- unit price;
- extended price;
- optional internal note when practical.

Manual items must transfer from OrderEntry to the Quote Form HTML page and be saved with the quote.

Do not silently add one-off manual items to the permanent pricing catalog.

## Quote Form HTML
The Quote button should open/build an editable Quote Form HTML page that closely resembles the existing Excel Quote Form.

The quote page should be populated from the calculator's current server-validated calculation and current user-entered presentation fields.

Appropriate presentation fields may be editable before saving, including customer/contact/reference/comments/manual line descriptions and quantities.

If calculated cylinder pricing is manually overridden, preserve the original calculated value separately from the override rather than destroying it.

## Database scope
Use SQLite (or another persisted store only if explicitly requested). Use WAL mode, foreign keys, parameterized queries, and short transactions.

Saved quote data should include enough of the current quote snapshot to preserve what was saved, such as:
- quote identifier/number;
- created timestamp;
- customer/header fields;
- cylinder input snapshot;
- model code;
- options/accessories/manual items;
- pricing breakdown and pricing version;
- final displayed quote values;
- engineering/display values used on the Quote Form;
- comments/reference fields.

Future pricing changes must not alter previously saved quote values.

## Quote numbering
Generate quote numbers server-side and transactionally.

If the exact final JIT quote-number convention is not yet proven, isolate generation in one clearly named service/configuration and use a safe temporary unique sequence for development.

Do not scatter temporary numbering logic throughout the application.

## Explicitly OUT OF SCOPE right now
Do NOT build, scaffold, wire, or spend time on any of the following unless the user explicitly requests it:
- Data1;
- outbound HTTP transmission of quote data;
- email sending;
- SMTP configuration;
- email UI;
- PDF generation;
- Playwright/Chromium PDF setup;
- customer-contact synchronization with external systems;
- full user authentication/login system (SSO/OAuth/password reset);
- PostgreSQL migration;
- external integrations of any kind.

Do not create placeholders for these unless a tiny interface boundary is absolutely necessary for clean architecture. If such a boundary is added, it must contain no network behavior and no user-facing feature.

## No outbound data rule
For this milestone, the application must not send quote/customer data anywhere outside the local Flask application except normal browser requests between the local HTML UI and its local Flask server.

No external network calls are permitted as part of the feature work.

## Security and integrity
At minimum:
- validate server-side inputs;
- parameterize database access;
- never accept arbitrary filesystem paths from the browser;
- do not commit secrets;
- do not expose raw stack traces to normal users;
- log server errors with useful context;
- use transactional persistence for quote saves;
- avoid mutable global quote state shared across users.

## Testing requirements
Preserve all existing tests.

Add tests for the current milestone, including:
- blank startup;
- Seal P;
- Style 4 Safety Coupler;
- catalog cascading behavior;
- DRE;
- discounts;
- accessories/modifications;
- manual line items;
- Quote button produces Quote Form HTML using server-side recalculated values;
- Quote Form editable presentation fields;
- quote save;
- unique transactional quote numbering;
- saved pricing snapshot does not change when current pricing data changes in a test fixture;
- no outbound network behavior is invoked by calculator/quote/save workflow.

After each major phase, run the complete suite. Never weaken or remove pricing tests to make new work pass.

## Development discipline
Work autonomously on routine implementation decisions, but do not invent business rules.

If a business rule is genuinely unknown, isolate it behind a clearly named configuration/TODO and continue with everything else.

Keep Flask unless a real blocker is discovered.

Do not rewrite working code merely for stylistic preference.

### Mandatory scope lock for every change
Treat each user request as a closed change scope. Before editing, write down the
exact files and symbols the request permits. Edit only those files and symbols.
Do not make “helpful” responsive, formatting, cleanup, naming, CSS, template,
or duplicate-removal changes unless the user explicitly includes them.

Before the first edit, capture the current status/diff and state the allowed
file list. After every edit, inspect the diff/status again. If any file outside
the allowed list changed, stop immediately and report it; do not continue with
the requested work until the scope is resolved.

For a request naming one page or one behavior, default to one file unless a
direct route, test, or style dependency is proven necessary. A visual issue on
one component does not authorize changes to shared styles or neighboring pages.

Never replace or regenerate a whole file to make a local change. Preserve
unrelated existing changes, and ask before reverting, normalizing, or
re-baselining any file.

## Windows run experience
This application is developed on Windows with Python approximately 3.11.

Preserve/update a simple run experience such as:

`RUN_CYLINDER_QUOTE.bat`

The user should be able to launch the local calculator in a browser without manually starting several services.

