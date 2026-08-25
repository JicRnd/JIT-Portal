# JIT Cylinder Quote HTML - Current Project Specification

## Mission
Continue the existing JIT Cylinder Quote web application without rewriting the verified pricing core.

The CURRENT build milestone has only three product goals:

1. finish/stabilize the existing OrderEntry-style HTML calculator;
2. build the editable spreadsheet-looking Quote Form HTML page and connect the calculator's Quote button to it;
3. build local SQLite persistence and a Save Quote action that saves the complete quote snapshot.

Nothing should be emailed, approved, transmitted, or sent to another system in this milestone.

Expected Windows workspace:

`C:\Users\Kane\Documents\Projects\Cylinder_Quote_To_HTML`

Expected current web app:

`Cylinder_Quote_Web_Milestone_1\`

This is a continuation project, not a greenfield rewrite.

---

## 1. Inspect and preserve the existing implementation
Before editing code:
- read `AGENTS.md`;
- inspect the current Flask application;
- inspect `cylinder_quote_engine/`;
- inspect the normalized pricing/engineering CSV data;
- run existing tests;
- inspect relevant Excel dissection/parity documentation when a business rule or field mapping is unclear.

The current Pricing Engine v1.2 is authoritative and protected.

Do not modify pricing logic merely to support the new workflow.

---

## 2. Architecture to preserve
Keep the current conceptual architecture:

`OrderEntry HTML -> Flask/API -> Pricing Engine v1.2 -> normalized pricing/engineering data`

Add only this local workflow around it:

`OrderEntry -> Quote button -> server recalculation -> editable Quote Form HTML -> Save Quote -> SQLite`

No outbound integrations belong in this milestone.

---

## 3. Finish/stabilize the OrderEntry calculator
Preserve the current approved OrderEntry replica.

### 3.1 Visual behavior
Keep the familiar Excel UserForm-like layout and relative geometry.

Maintain proportional whole-form scaling:
- one uniform scale factor;
- fit based on available browser width and height;
- font, controls, spacing, tabs, and buttons scale together;
- preserve proportions;
- keep the form inside the visible viewport;
- do not independently stretch individual controls.

Keep the pricing block visually separated from the Quote button.

### 3.2 Blank-slate behavior
A new page/new quote starts blank:
- Customer blank;
- Address blank;
- model-building fields blank;
- options/accessories/manual parts blank/zero as appropriate;
- Pressure blank;
- Discount blank;
- Net Each and Profit display `$0.00`;
- no previous quote configuration survives a new quote.

### 3.3 Field sequence
Maintain:
1. Series
2. Mount
3. Bore
4. Stroke
5. Rod
6. Style
7. Cushion
8. Ports
9. Seal
10. DRE (Y)

Must include:
- Seal `P`;
- Style `4 - Safety Coupler`;
- all other currently verified options.

### 3.4 Existing pricing features
Preserve current normalized behavior for:
- Series routing;
- model-code construction;
- DRE;
- stroke/cushion;
- discounts;
- W-series behavior;
- common modifications;
- position sensing;
- VA;
- standard accessories;
- rod boot;
- special parts;
- legacy compatibility rules already encoded in v1.2.

### 3.5 Manual special-order items
The Parts / Description / Qty / Price area must allow a manual item not present in the catalog.

Manual row should support:
- optional part/reference number;
- description;
- quantity;
- unit price;
- extended price;
- optional note if practical.

A manual item does NOT require a cylinder model code and must not be added automatically to the standard catalog.

Manual items must transfer to the Quote Form and save to the database.

---

## 4. Quote button
The existing Quote button becomes the transition to the customer quote form.

When clicked:
1. validate required calculator inputs;
2. perform/re-perform authoritative pricing on the server;
3. build a quote draft payload containing the full current calculator state;
4. transfer that draft into the Quote Form HTML page;
5. do not save automatically unless explicitly required by implementation architecture;
6. do not email, generate PDF, approve, transmit, or call an external service.

The server-calculated result is authoritative. Do not trust stale browser-only price values.

---

## 5. Editable Quote Form HTML
Build a second HTML page that closely resembles the existing Excel `Quote Form` screenshot/layout.

It should feel spreadsheet-like and familiar to existing users.

### 5.1 Header/customer section
Support fields such as:
- JIT branding/logo area;
- Quote # (assigned at save or draft allocation according to the isolated numbering service);
- Date;
- Terms;
- Customer;
- Address;
- Phone/Email;
- Attention;
- Days;
- Reference;
- FOB.

### 5.2 Main quote line
Support:
- Qty;
- Description;
- List;
- Discount;
- Net Each;
- Expedited;
- Emergency;
- any total needed for multiple/manual items.

### 5.3 Cylinder description
Support:
- Series;
- Model Code;
- Bore;
- Mount;
- Rod Size;
- Cushions;
- Ports;
- Stroke;
- Rod Thread/Style description;
- Seals;
- Includes/options/accessories/manual special-order items.

### 5.4 Engineering/display data
Where already supported by normalized data/engine logic, display:
- recommended repair components;
- cylinder weight;
- rated pressure;
- Push @ 100 PSI;
- Pull @ 100 PSI;
- cylinder/mount dimensions;
- comments;
- quote validity/terms footer.

Do not expose internal profit/cost information to the customer-facing quote unless current business behavior specifically calls for it.

### 5.5 Editable presentation fields
Before Save Quote, appropriate fields may be edited, including:
- Customer/contact/header fields;
- attention;
- reference;
- comments;
- descriptions;
- quantities;
- manual special-order line details.

If cylinder pricing override is allowed in the implementation, preserve both:
- original server-calculated value;
- manual override value.

Do not overwrite/delete the original calculation snapshot.

---

## 6. Local database persistence
Implement local SQLite persistence for Save Quote.

This milestone does NOT include a Quote History/search/retrieval interface.

The database is simply the durable store for saved quotes so later milestones can build retrieval on top of it.

### 6.1 SQLite requirements
Use:
- WAL mode;
- foreign keys;
- parameterized SQL or a maintained ORM;
- short transactions;
- uniqueness constraints as appropriate;
- no mutable shared global quote state.

Keep data access organized enough that future migration is possible, but do not implement PostgreSQL now.

### 6.2 Minimum quote persistence model
Use a coherent schema sufficient to save:
- quote ID;
- quote number;
- created/updated timestamps;
- customer/header snapshot;
- full cylinder input snapshot;
- model code;
- options/modifications/accessories;
- manual special-order items;
- pricing breakdown;
- pricing version;
- final displayed quote values;
- engineering/display snapshot used by Quote Form;
- comments/reference fields;
- original calculated values and override values if overrides are supported.

Exact table names are implementation choices.

Avoid unnecessary schema for features explicitly deferred below.

### 6.3 Saved quote snapshot rule
A saved quote must preserve what was saved at that moment.

Future changes to current pricing tables must not recalculate or mutate an already saved quote record.

---

## 7. Quote numbering
Generate quote numbers server-side and transactionally.

If the exact final JIT quote-number format cannot be proven from current source material, create an isolated quote-number service and use a temporary unique development format.

The format must be changeable later without rewriting quote persistence.

Concurrent saves must not allocate duplicate quote numbers.

---

## 8. Save Quote button
The Quote Form HTML page must have a `Save Quote` button.

On Save Quote:
1. validate current quote data server-side;
2. assign Quote # if not already assigned;
3. save the full snapshot transactionally;
4. save manual items and options;
5. save pricing version and original calculation values;
6. return a clear success message and saved Quote #;
7. remain on the Quote Form unless the UI has a clearly better non-destructive behavior.

Do NOT:
- email;
- create PDF;
- send HTTP requests to another device;
- approve anything;
- open/build Quote History.

A separate New Quote action may return to a blank OrderEntry form after a successful save, but do not automatically destroy the just-saved screen before the user can see that save succeeded.

---

## 9. Explicitly deferred / forbidden in this milestone
Do not implement or scaffold user-facing features for:
- qhistory / Quote History;
- quote search/retrieval page;
- quote re-open workflow;
- Data1;
- Raspberry Pi integration;
- Approval button;
- approval status/transmission logic;
- external HTTP POSTs;
- email;
- SMTP;
- recipient/contact email chooser;
- PDF generation;
- Playwright/Chromium PDF tooling;
- email/PDF logs;
- external customer synchronization;
- full login/authentication;
- PostgreSQL.

Do not add background services or network clients for deferred features.

---

## 10. No outbound-data rule
During this milestone the only network traffic created by the application should be local browser-to-local-Flask application traffic needed to use the calculator, Quote Form, and Save Quote action.

Do not transmit customer, pricing, or quote data to any external destination.

---

## 11. Tests
Preserve every existing pricing/web test.

Add milestone tests covering at least:
- blank startup;
- Seal P;
- Style 4 Safety Coupler;
- calculator field/catalog behavior;
- DRE/discount/accessory behavior remains intact;
- manual special-order item entry;
- Quote button creates Quote Form draft using authoritative server recalculation;
- Quote Form displays calculator/model/pricing data correctly;
- editable presentation fields do not mutate the protected pricing engine;
- Save Quote persists expected snapshot;
- manual items persist;
- unique transactional quote number allocation;
- concurrent quote-number allocation test where practical;
- saved quote pricing snapshot remains unchanged if current pricing fixture is modified later;
- no outbound HTTP/email/PDF feature is invoked in this workflow.

Run the full suite after each major phase.

Never delete or weaken existing pricing tests to make new work pass.

---

## 12. Recommended implementation phases
Proceed in this order unless inspection proves a small adjustment is necessary:

### Phase 1 - Baseline and calculator finish
- run tests;
- verify current OrderEntry behavior;
- fix only confirmed remaining calculator/UI issues;
- confirm Seal P and Style 4;
- confirm proportional scaling and blank slate;
- confirm manual-item input design.

### Phase 2 - Quote draft transfer
- define a clean server-side quote-draft representation outside the protected pricing engine;
- have Quote button rerun calculation server-side;
- transfer state into Quote Form route/template;
- add tests.

### Phase 3 - Quote Form HTML
- reproduce Excel Quote Form layout closely;
- populate current quote data;
- add allowed editable presentation fields;
- include manual items;
- add tests.

### Phase 4 - SQLite persistence
- initialize local database;
- implement quote-number service;
- implement transactional Save Quote;
- save complete snapshot/manual items;
- add tests including numbering concurrency.

### Phase 5 - polish/documentation
- clear user-facing validation/errors;
- preserve Windows startup workflow;
- update README with database path and startup steps;
- run all tests and report results.

Stop there. Do not continue into deferred systems.

---

## 13. Windows run experience
Preserve/update a simple launcher such as:

`RUN_CYLINDER_QUOTE.bat`

The expected final behavior for this milestone:
1. user starts the local Flask app;
2. browser opens OrderEntry calculator;
3. user configures quote;
4. Quote opens Quote Form HTML;
5. user reviews/edits allowed fields;
6. Save Quote stores the quote locally in SQLite;
7. user can start a New Quote and return to a blank calculator.

---

## 14. Completion report
At completion report:
- features completed;
- exact test pass/fail count;
- files created/changed;
- database file location;
- quote-number strategy/location;
- exact Windows startup instructions;
- any genuine business-rule TODOs still unresolved.

Do not claim email, PDF, Quote History, Data1, approval, or external transmission functionality. Those are deliberately deferred.
