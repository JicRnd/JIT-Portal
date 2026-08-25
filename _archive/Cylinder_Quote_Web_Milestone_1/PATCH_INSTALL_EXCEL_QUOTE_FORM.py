#!/usr/bin/env python3
"""Install the workbook-faithful Quote Form into Cylinder Quote Web Milestone 1."""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path


HTML_BLOCK = r'''    <div id="quotePreviewView" class="view hidden">
      <div class="qf-toolbar">
        <button type="button" id="backToOrderEntryButton" class="preview-btn">Back to Order Entry</button>
        <button type="button" id="newQuoteButton" class="preview-btn primary">New Quote</button>
        <button type="button" id="saveQuoteButton" class="preview-btn primary">Save to Database</button>
        <span class="qf-toolbar-meta">Revision <strong id="pv_revision">—</strong> · Status <strong id="pv_status">—</strong> · <span id="pv_pricing_version">—</span> · Created by <span id="pv_created_by">—</span></span>
        <span id="previewErrorMessage" class="error" role="alert"></span>
      </div>

      <div class="excel-quote-sheet" aria-label="Cylinder Quote Form">
        <header class="xq-header">
          <div class="xq-logo-wrap">
            <img class="xq-logo" src="/static/quote_form_logo.png" alt="JIT Cylinders">
          </div>
          <h1>Quote Form</h1>
          <table class="xq-meta-table">
            <tr><th>Quote</th><td id="pv_quote_number">—</td></tr>
            <tr><th>Date</th><td id="pv_created_at">—</td></tr>
            <tr><th>Terms</th><td><input id="pv_terms" value="Net 30" aria-label="Terms"></td></tr>
          </table>
        </header>

        <section class="xq-customer">
          <div class="xq-customer-fields">
            <label>Customer</label><input id="pv_customer_name" type="text" autocomplete="off">
            <label>Address:</label><input id="pv_customer_address" type="text" autocomplete="off">
            <label>Phone/Email:</label><input id="pv_customer_contact" type="text" autocomplete="off">
            <label>Attn:</label><input id="pv_customer_attn" type="text" autocomplete="off">
          </div>

          <table class="xq-meta-table xq-side-table">
            <tr><th>Days:</th><td><input id="pv_days" type="number" min="0" value="30"></td></tr>
            <tr><th>Ref:</th><td><input id="pv_reference_notes" type="text"></td></tr>
            <tr><th>FOB</th><td><input id="pv_fob" value="Hartselle, AL"></td></tr>
          </table>
        </section>

        <section class="xq-grid">
          <div class="xq-head xq-desc-head">Description</div>
          <div class="xq-head xq-qty-head">Qty</div>
          <div class="xq-head xq-list-head">List</div>
          <div class="xq-head xq-discount-head">Discount</div>
          <div class="xq-head xq-net-head">Net Each</div>

          <div class="xq-label row-series">Series</div>
          <div class="xq-value row-series" id="pv_series_desc">—</div>
          <div class="xq-qty row-series"><input id="pv_quantity" type="number" min="1" value="1"></div>
          <div class="xq-list row-series" id="pv_quote_list_price">—</div>
          <div class="xq-discount row-series" id="pv_discount">—</div>
          <div class="xq-net row-series">
            <span id="pv_quote_net_each">—</span> -
            <span id="pv_net_days">30</span> Days
          </div>

          <div class="xq-label row-model">Model Code</div>
          <div class="xq-value row-model" id="pv_model_code">—</div>
          <div class="xq-label row-expedited">Expedited - Emergency</div>
          <div class="xq-wide-price row-expedited">
            <span id="pv_expedited_price">—</span>
            (<span id="pv_expedited_days">15</span> Days)
            &nbsp;
            <span id="pv_emergency_price">—</span> (NOW)
          </div>

          <div class="xq-label row-bore">Bore Size (&quot;)</div>
          <div class="xq-value row-bore" id="pv_bore">—</div>
          <div class="xq-label row-cares-price">JIT Foster Care Program*</div>
          <div class="xq-wide-price row-cares-price">
            <span id="pv_cares_price">—</span> -
            <span id="pv_cares_days">30</span> Days
          </div>

          <div class="xq-label row-mount">Mount</div>
          <div class="xq-value row-mount" id="pv_mount">—</div>

          <div class="xq-repair">
            <div class="xq-repair-title">Recommended Cylinder Repair Components</div>
            <label>Piston &amp; Rod Assembly<input id="pv_repair_assembly" value="N/A"></label>
            <label>Hyd Rod Low Friction Seal Kit<input id="pv_repair_rod_kit" value="N/A"></label>
            <label>Hyd Piston Low Friction Seal Kit<input id="pv_repair_piston_kit" value="N/A"></label>
            <label>Hyd Gland Low Friction Seal Kit<input id="pv_repair_gland_kit" value="N/A"></label>
            <label>Cylinder Weight<input id="pv_weight" placeholder="—"></label>
            <label>Push @ <span id="pv_pressure_push">0</span> PSI<span id="pv_push_lbs">0 lbs</span></label>
            <label>Pull @ <span id="pv_pressure_pull">0</span> PSI<span id="pv_pull_lbs">0 lbs</span></label>
          </div>

          <div class="xq-label row-rod">Rod Size (&quot;)</div>
          <div class="xq-value row-rod" id="pv_rod_diameter">—</div>

          <div class="xq-label row-cushions">Cushions</div>
          <div class="xq-value row-cushions" id="pv_cushion">—</div>

          <div class="xq-label row-ports">Ports</div>
          <div class="xq-value row-ports" id="pv_port_code">—</div>

          <div class="xq-label row-stroke">Stroke (&quot;)</div>
          <div class="xq-value row-stroke" id="pv_stroke">—</div>

          <div class="xq-label row-thread">Rod Thread</div>
          <div class="xq-value row-thread" id="pv_rod_style">—</div>

          <div class="xq-label row-seals">Seals</div>
          <div class="xq-value row-seals" id="pv_seal_code">—</div>

          <div class="xq-label row-includes">Includes:</div>
          <div class="xq-value xq-includes row-includes" id="pv_includes">—</div>

          <div class="xq-diagram">
            <div class="xq-cylinder-art" aria-hidden="true">
              <div class="xq-cap"><i></i><i></i><i></i><i></i></div>
              <div class="xq-barrel"></div>
              <div class="xq-rod"></div>
              <div class="xq-rod-end"></div>
              <span class="dim-tag dim-e">E</span>
              <span class="dim-tag dim-g">G</span>
              <span class="dim-tag dim-j">J</span>
              <span class="dim-tag dim-lb">LB</span>
              <span class="dim-tag dim-a">A</span>
              <span class="dim-tag dim-wf">WF</span>
            </div>

            <div class="xq-dimensions">
              <label>E = <input id="pv_dim_e" placeholder="—"></label>
              <label>G = <input id="pv_dim_g" placeholder="—"></label>
              <label>J = <input id="pv_dim_j" placeholder="—"></label>
              <label>LB = <input id="pv_dim_lb" placeholder="—"></label>
              <label>A = <input id="pv_dim_a" placeholder="—"></label>
              <label>WF = <input id="pv_dim_wf" placeholder="—"></label>
              <label>Other <input id="pv_dim_other"></label>
              <strong>Cylinder<br>Dimensions</strong>
            </div>
          </div>

          <div class="xq-comments">
            <label for="pv_comments">Comments:</label>
            <textarea id="pv_comments" rows="5"></textarea>
          </div>
        </section>

        <section class="xq-manual-section">
          <h2>Additional Quoted Items</h2>
          <div class="parts-header manual-header">
            <span>Ref</span>
            <span>Description</span>
            <span>Qty</span>
            <span>Unit Price</span>
            <span>Extended</span>
            <span>Show</span>
            <span>Note</span>
            <span></span>
          </div>
          <div id="previewManualItems" class="manual-items"></div>
          <button type="button" id="addManualItemButton" class="preview-btn secondary">+ Add Line Item</button>
        </section>

        <div class="xq-cares-banner">
          <img src="/static/quote_form_cares.png" alt="JIT Cares">
        </div>

        <footer class="xq-footer">
          <div>Quote is valid for 60 Days</div>
          <div>*Orders of $25K+ are subject to JIT Progress Payment Terms</div>
          <div>* For Emergency orders please call to verify achievable delivery.</div>
          <div class="xq-signature">
            <input id="pv_prepared_by" value="Matt McComb"><br>
            <input id="pv_prepared_title" value="Cylinder Application Eng.">
          </div>
          <div class="xq-terms">
            JIT Terms of Sale are available at www.jitindustries.com/terms.html
          </div>
        </footer>
      </div>
    </div>
'''


CSS_BLOCK = r'''
/* Excel Quote Form replica v2 */
#quotePreviewView {
  min-height: 100vh;
  background: #d8d8d8;
  padding-bottom: 30px;
  font-family: "Century Gothic", CenturyGothic, Arial, sans-serif;
  color: #111;
}

.qf-toolbar {
  position: sticky;
  top: 0;
  z-index: 5;
  background: #efefef;
  box-shadow: 0 2px 5px #0002;
}

.excel-quote-sheet {
  width: 816px;
  min-height: 1056px;
  margin: 14px auto 30px;
  padding: 16px 18px 12px;
  background: #fff;
  box-shadow: 0 3px 15px #0004;
  font: 12px/1.2 "Century Gothic", CenturyGothic, Arial, sans-serif;
}

.excel-quote-sheet input,
.excel-quote-sheet textarea {
  font: inherit;
  color: #111;
  border: 0;
  background: #fffdf0;
  outline: 0;
}

.excel-quote-sheet input:hover,
.excel-quote-sheet textarea:hover {
  background: #fff8c9;
}

.excel-quote-sheet input:focus,
.excel-quote-sheet textarea:focus {
  background: #fff3a8;
  box-shadow: inset 0 0 0 1px #d5a000;
}

.xq-header {
  display: grid;
  grid-template-columns: 170px 1fr 190px;
  gap: 10px;
  align-items: center;
  min-height: 82px;
  border-bottom: 2px solid #111;
  padding-bottom: 6px;
}

.xq-logo-wrap {
  display: flex;
  align-items: center;
  height: 74px;
}

.xq-logo {
  display: block;
  max-width: 160px;
  max-height: 72px;
  object-fit: contain;
}

.xq-header h1 {
  margin: 0;
  text-align: center;
  font-size: 30px;
  line-height: 1;
  font-weight: 400;
}

.xq-meta-table {
  width: 100%;
  border-collapse: collapse;
}

.xq-meta-table th,
.xq-meta-table td {
  height: 24px;
  border: 1px solid #777;
  padding: 2px 5px;
}

.xq-meta-table th {
  width: 55px;
  text-align: right;
  font-weight: 400;
}

.xq-meta-table td {
  text-align: center;
}

.xq-meta-table input {
  width: 100%;
  height: 20px;
  text-align: center;
  padding: 1px 3px;
}

.xq-customer {
  display: grid;
  grid-template-columns: 1fr 190px;
  gap: 12px;
  margin: 8px 0 10px;
  align-items: start;
}

.xq-customer-fields {
  display: grid;
  grid-template-columns: 90px 1fr;
  gap: 3px 5px;
  align-items: center;
}

.xq-customer-fields label {
  text-align: right;
}

.xq-customer-fields input {
  height: 22px;
  border-bottom: 1px solid #aaa;
  padding: 2px 5px;
}

.xq-side-table input {
  width: 100%;
}

.xq-grid {
  display: grid;
  grid-template-columns: 104px 240px 46px 76px 88px 1fr;
  grid-template-rows: 25px repeat(11, 25px) 155px;
  position: relative;
  border-top: 1px solid #777;
  border-left: 1px solid #777;
}

.xq-grid > div {
  min-width: 0;
  border-right: 1px solid #aaa;
  border-bottom: 1px solid #aaa;
  padding: 5px 6px;
  background: #fff;
}

.xq-head {
  text-align: center;
  background: #f7f7f7 !important;
}

.xq-desc-head { grid-column: 1 / 3; }
.xq-qty-head { grid-column: 3; }
.xq-list-head { grid-column: 4; }
.xq-discount-head { grid-column: 5; }
.xq-net-head { grid-column: 6; }

.xq-label { grid-column: 1; }
.xq-value {
  grid-column: 2;
  font-size: 13px;
}

.xq-qty {
  grid-column: 3;
  text-align: center;
}

.xq-qty input {
  width: 100%;
  text-align: center;
}

.xq-list {
  grid-column: 4;
  text-align: center;
  font-size: 13px;
}

.xq-discount {
  grid-column: 5;
  text-align: center;
  font-size: 13px;
}

.xq-net {
  grid-column: 6;
  text-align: center;
  font-size: 13px;
}

.row-series { grid-row: 2; }
.row-model, .row-expedited { grid-row: 3; }
.row-bore, .row-cares-price { grid-row: 4; }
.row-mount { grid-row: 5; }
.row-rod { grid-row: 6; }
.row-cushions { grid-row: 7; }
.row-ports { grid-row: 8; }
.row-stroke { grid-row: 9; }
.row-thread { grid-row: 10; }
.row-seals { grid-row: 11; }
.row-includes { grid-row: 12; }

.xq-includes {
  white-space: normal;
  overflow: auto;
}

.xq-wide-price {
  grid-column: 4 / 7;
  text-align: center;
  font-size: 12px;
}

.xq-label.row-expedited,
.xq-label.row-cares-price {
  grid-column: 3 / 4;
  text-align: right;
  font-size: 10px;
  padding-left: 1px;
  padding-right: 4px;
}

.xq-repair {
  grid-column: 3 / 7;
  grid-row: 5 / 12 !important;
  padding: 0 !important;
  border: 1px solid #777 !important;
  display: grid;
  grid-template-columns: 1fr 112px;
  grid-auto-rows: 25px;
}

.xq-repair-title {
  grid-column: 1 / 3;
  text-align: center;
  font-weight: 700;
  padding: 5px;
  border-bottom: 1px solid #aaa;
}

.xq-repair label {
  grid-column: 1 / 3;
  display: grid;
  grid-template-columns: 1fr 112px;
  align-items: center;
  padding-left: 8px;
  border-bottom: 1px solid #ddd;
}

.xq-repair label input,
.xq-repair label > span:last-child {
  height: 23px;
  padding: 3px 5px;
  text-align: center;
  border-left: 1px solid #aaa;
}

.xq-diagram {
  grid-column: 3 / 7;
  grid-row: 13 / 14 !important;
  padding: 8px !important;
  display: grid;
  grid-template-columns: 1.35fr 1fr;
  gap: 8px;
  align-items: center;
}

.xq-cylinder-art {
  height: 115px;
  position: relative;
}

.xq-barrel {
  position: absolute;
  left: 43px;
  top: 38px;
  width: 145px;
  height: 42px;
  border: 2px solid #333;
  background: linear-gradient(#fff, #e8e8e8, #fff);
}

.xq-cap {
  position: absolute;
  left: 4px;
  top: 27px;
  width: 64px;
  height: 64px;
  border: 2px solid #333;
  border-radius: 50%;
  background: #fafafa;
  z-index: 2;
}

.xq-cap::after {
  content: "";
  position: absolute;
  inset: 12px;
  border: 1px solid #555;
  border-radius: 50%;
}

.xq-cap i {
  position: absolute;
  width: 5px;
  height: 5px;
  border: 1px solid #333;
  border-radius: 50%;
}

.xq-cap i:nth-child(1) { left: 28px; top: 4px; }
.xq-cap i:nth-child(2) { right: 4px; top: 28px; }
.xq-cap i:nth-child(3) { left: 28px; bottom: 4px; }
.xq-cap i:nth-child(4) { left: 4px; top: 28px; }

.xq-rod {
  position: absolute;
  left: 188px;
  top: 50px;
  width: 62px;
  height: 18px;
  border: 1px solid #333;
  background: #eee;
}

.xq-rod-end {
  position: absolute;
  left: 250px;
  top: 45px;
  width: 30px;
  height: 28px;
  border: 2px solid #333;
}

.dim-tag {
  position: absolute;
  font-size: 9px;
}

.dim-e { left: 31px; bottom: 2px; }
.dim-g { left: 68px; bottom: 2px; }
.dim-j { right: 3px; top: 53px; }
.dim-lb { left: 130px; bottom: 2px; }
.dim-a { right: 20px; bottom: 2px; }
.dim-wf { left: 135px; top: 7px; }

.xq-dimensions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px 8px;
  align-items: center;
}

.xq-dimensions label {
  display: flex;
  align-items: center;
  gap: 3px;
}

.xq-dimensions input {
  width: 65px;
  border-bottom: 1px solid #999;
  text-align: center;
}

.xq-dimensions strong {
  grid-column: 2;
  grid-row: 1 / 5;
  font-size: 23px;
  line-height: 1.05;
  text-align: center;
  font-weight: 400;
}

.xq-comments {
  grid-column: 1 / 3;
  grid-row: 13 / 14 !important;
  padding: 8px !important;
}

.xq-comments label {
  display: block;
  font-weight: 700;
  margin-bottom: 4px;
}

.xq-comments textarea {
  width: 100%;
  height: 112px;
  border: 1px solid #999;
  padding: 5px;
  resize: vertical;
}

.xq-manual-section {
  margin: 12px 0 8px;
  padding: 8px;
  border: 1px solid #999;
}

.xq-manual-section h2 {
  margin: 0 0 7px;
  font-size: 12px;
}

.xq-cares-banner {
  height: 77px;
  margin: 8px 0;
  overflow: hidden;
}

.xq-cares-banner img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.xq-footer {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px 12px;
  border-top: 1px solid #888;
  padding-top: 6px;
  font-size: 10px;
}

.xq-signature {
  grid-column: 2;
  grid-row: 2 / 4;
  text-align: right;
}

.xq-signature input {
  width: 170px;
  text-align: center;
  border-bottom: 1px solid #999;
}

.xq-terms {
  grid-column: 1 / 3;
  text-align: center;
  margin-top: 3px;
}

@media (max-width: 850px) {
  #quotePreviewView { overflow-x: auto; }
  .excel-quote-sheet { margin-left: 0; }
}

@media print {
  @page { size: letter portrait; margin: 0; }

  .qf-toolbar { display: none !important; }

  #quotePreviewView {
    background: #fff;
    padding: 0;
  }

  .excel-quote-sheet {
    width: 8.5in;
    min-height: 11in;
    margin: 0;
    box-shadow: none;
  }

  .excel-quote-sheet input,
  .excel-quote-sheet textarea {
    background: #fff !important;
    box-shadow: none !important;
  }

  .xq-manual-section button,
  .manual-remove,
  .manual-show {
    display: none !important;
  }
}
/* End Excel Quote Form replica v2 */
'''


JS_RENDER = r'''function renderQuotePreview(quote) {
  currentQuote = quote;
  $('pv_quote_number').textContent = quote.quote_number || 'Not saved yet';
  $('pv_revision').textContent = quote.revision || '1';
  $('pv_status').textContent = quote.status || '—';
  $('pv_pricing_version').textContent = quote.pricing_version || '—';
  $('pv_created_by').textContent = quote.created_by || '—';
  $('pv_created_at').textContent = formatQuoteDate(quote.created_at);
  $('pv_customer_name').value = quote.customer_name || '';
  $('pv_customer_address').value = quote.customer_address || '';
  $('pv_customer_contact').value = quote.customer_contact || '';
  $('pv_reference_notes').value = quote.reference_notes || '';
  $('pv_comments').value = quote.comments || '';

  const inputs = quote.cylinder_inputs_snapshot || {};

  $('pv_series_desc').textContent = inputs.series
    ? `${inputs.series} Series Hydraulic Cylinder`
    : 'Hydraulic Cylinder';

  $('pv_model_code').textContent = quote.model_code || '—';
  $('pv_mount').textContent = inputs.mount || '—';
  $('pv_bore').textContent = inputs.bore || '—';
  $('pv_stroke').textContent = inputs.stroke || '—';
  $('pv_rod_diameter').textContent = inputs.rod_diameter || '—';
  $('pv_rod_style').textContent = inputs.rod_style || '—';
  $('pv_cushion').textContent = labelFor(CUSHION_LABELS, inputs.cushion);
  $('pv_port_code').textContent = inputs.port_code || '—';
  $('pv_seal_code').textContent = labelFor(SEAL_LABELS, inputs.seal_code);
  $('pv_discount').textContent =
    (Number(quote.discount || 0) * 100).toFixed(1) + '%';

  const manualDescriptions = (quote.manual_line_items || [])
    .map(item => item.description)
    .filter(Boolean);

  const selectedSpecialParts = Object.entries(inputs.special_parts || {})
    .map(([part, qty]) => `${part} (Qty ${qty})`);

  const includesList = [
    ...manualDescriptions,
    ...selectedSpecialParts
  ];

  $('pv_includes').textContent = includesList.length
    ? includesList.join(', ')
    : '—';

  const pressure = $('pressure') ? $('pressure').value : '';
  const forces = computePushPull(
    pressure,
    inputs.bore,
    inputs.rod_diameter
  );

  $('pv_pressure_push').textContent = pressure || '0';
  $('pv_pressure_pull').textContent = pressure || '0';
  $('pv_push_lbs').textContent =
    `${forces.push.toLocaleString('en-US')} lbs`;
  $('pv_pull_lbs').textContent =
    `${forces.pull.toLocaleString('en-US')} lbs`;

  const breakdown = quote.price_breakdown_snapshot || {};
  const standardNet = Number(breakdown.quote_net_each || 0);
  const days = Number($('pv_days').value || 30);

  $('pv_quote_list_price').textContent =
    fmtMoney(breakdown.quote_list_price);

  $('pv_quote_net_each').textContent =
    fmtMoney(standardNet);

  $('pv_expedited_price').textContent =
    fmtMoney(Math.ceil(standardNet * 1.35));

  $('pv_emergency_price').textContent =
    fmtMoney(Math.ceil(standardNet * 1.95));

  $('pv_cares_price').textContent =
    fmtMoney(standardNet * 1.05);

  $('pv_net_days').textContent = days || 30;
  $('pv_expedited_days').textContent =
    Math.max(1, Math.round((days || 30) / 2));
  $('pv_cares_days').textContent = days || 30;

  renderManualItems(quote.manual_line_items || []);
  $('previewErrorMessage').textContent = '';
  showView('quotePreviewView');
}

'''


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    input("Press Enter to close...")
    raise SystemExit(1)


def replace_between(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = text.find(start_marker)

    if start < 0:
        fail(f"Could not find expected start marker: {start_marker}")

    end = text.find(end_marker, start)

    if end < 0:
        fail(f"Could not find expected end marker: {end_marker}")

    return text[:start] + replacement + text[end:]


def main() -> None:
    root = Path(__file__).resolve().parent

    html_path = root / "app" / "templates" / "index.html"
    css_path = root / "app" / "static" / "styles.css"
    js_path = root / "app" / "static" / "app.js"
    workbook_path = root / "2026 Cylinder Quote V4.xlsm"

    required_files = (
        html_path,
        css_path,
        js_path,
        workbook_path,
    )

    for path in required_files:
        if not path.exists():
            fail(f"Required project file was not found: {path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / f"backup_before_excel_quote_form_{timestamp}"
    backup.mkdir()

    for path in (html_path, css_path, js_path):
        shutil.copy2(path, backup / path.name)

    html = html_path.read_text(encoding="utf-8")

    html = replace_between(
        html,
        '    <div id="quotePreviewView" class="view hidden">',
        '  </main>\n\n  <dialog id="quoteResultDialog"',
        HTML_BLOCK,
    )

    html_path.write_text(html, encoding="utf-8")

    css = css_path.read_text(encoding="utf-8")

    css_start = css.find("/* Excel Quote Form replica v2")

    if css_start >= 0:
        css_end = css.find(
            "/* End Excel Quote Form replica v2 */",
            css_start,
        )

        if css_end >= 0:
            css = (
                css[:css_start]
                + css[
                    css_end
                    + len("/* End Excel Quote Form replica v2 */"):
                ]
            )

    css_path.write_text(
        css.rstrip() + "\n" + CSS_BLOCK.strip() + "\n",
        encoding="utf-8",
    )

    js = js_path.read_text(encoding="utf-8")

    js = replace_between(
        js,
        "function renderQuotePreview(quote) {",
        "function renderManualItems(items) {",
        JS_RENDER,
    )

    js_path.write_text(js, encoding="utf-8")

    with zipfile.ZipFile(workbook_path) as workbook:
        assets = {
            "xl/media/image26.png":
                root / "app" / "static" / "quote_form_logo.png",

            "xl/media/image29.png":
                root / "app" / "static" / "quote_form_cares.png",
        }

        for member, destination in assets.items():
            if member not in workbook.namelist():
                fail(f"Workbook artwork was not found: {member}")

            destination.write_bytes(workbook.read(member))

    print()
    print("SUCCESS")
    print(
        "The Excel-style Quote Form is installed and connected "
        "to the existing Quote button."
    )
    print(
        "Pricing Engine v1.2 and pricing data were not modified."
    )
    print(f"Backup created: {backup.name}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(str(exc))