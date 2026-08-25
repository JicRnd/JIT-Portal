from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} block, found {count}.")
    return text.replace(old, new, 1)


ORDER_HTML = dedent(r'''\
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>JIT Order Form</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='order_form.css') }}">
</head>
<body>
  <main class="order-page" data-quote-id="{{ quote_id }}">
    <div class="order-toolbar">
      <a href="/" class="toolbar-button">← Quote Entry</a>
      <span id="orderStatus" class="status-pill">Loading…</span>
      <span id="orderMessage" class="toolbar-message" role="status" aria-live="polite"></span>
      <button id="approveOrderButton" class="approve-button" type="button">Approve Order</button>
    </div>

    <form id="employeeOrderForm" class="order-sheet" autocomplete="off">
      <header class="order-header">
        <img src="{{ url_for('static', filename='quote_form_logo.png') }}" alt="JIT Cylinders" class="order-logo">
        <h1>Order Form</h1>
        <div class="order-meta">
          <label>Order # <input data-field="order_number"></label>
          <label>Date: <input data-field="order_date"></label>
          <label>Terms: <input data-field="terms"></label>
        </div>
      </header>

      <section class="address-grid">
        <div class="address-block ship-to">
          <span class="address-label">Ship To:</span>
          <div>
            <input data-field="ship_to_1" aria-label="Ship to line 1">
            <input data-field="ship_to_2" aria-label="Ship to line 2">
            <input data-field="ship_to_3" aria-label="Ship to line 3">
            <input data-field="ship_to_4" aria-label="Ship to line 4">
          </div>
        </div>

        <div class="shipping-fields">
          <label>PO # <input data-field="po_number"></label>
          <label>Tag <input data-field="tag"></label>
          <label>Ship <input data-field="ship_method"></label>
          <label>Ship Date <input data-field="ship_date"></label>
          <label>Contact <input data-field="contact"></label>
        </div>

        <div class="address-block bill-to">
          <span class="address-label">Bill To:</span>
          <div>
            <input data-field="bill_to_1" aria-label="Bill to line 1">
            <input data-field="bill_to_2" aria-label="Bill to line 2">
            <input data-field="bill_to_3" aria-label="Bill to line 3">
            <input data-field="bill_to_4" aria-label="Bill to line 4">
          </div>
        </div>
      </section>

      <section class="order-summary">
        <label>Cylinder Description
          <input data-field="cylinder_description">
        </label>
        <label>Qty
          <input data-field="quantity" type="number" min="0" step="1">
        </label>
        <label>Net
          <input data-field="net_each" type="number" min="0" step="0.01">
        </label>
        <label>Discount
          <input data-field="discount" type="number" min="0" step="0.01">
        </label>
        <label>Total
          <input data-field="order_total" type="number" min="0" step="0.01">
        </label>
      </section>

      <section class="order-body">
        <div class="cylinder-panel">
          <label>Description <input data-field="description"></label>
          <label>Model Code <input data-field="model_code"></label>
          <label>Bore Size (&quot;) <input data-field="bore"></label>
          <label>Mount <input data-field="mount"></label>
          <label>Rod Size (&quot;) <input data-field="rod_diameter"></label>
          <label>Cushions <input data-field="cushion"></label>
          <label>Ports <input data-field="ports"></label>
          <label>Stroke (&quot;) <input data-field="stroke"></label>
          <label>Rod Thread <input data-field="rod_thread"></label>
          <label>Seals <input data-field="seals"></label>

          <label class="includes-row">
            Includes:
            <textarea data-field="includes" rows="3"></textarea>
          </label>

          <div class="accessory-row">
            <label>Rod Clevis <input data-field="rod_clevis"></label>
            <label>Pivot Pin <input data-field="pivot_pin"></label>
          </div>

          <div class="assembly-fields">
            <label>Assembled By:
              <input data-field="assembled_by">
            </label>
            <label>Date Passed Test:
              <input data-field="date_passed_test">
            </label>
          </div>
        </div>

        <div class="parts-panel">
          <div class="parts-header">
            <span>Part #</span>
            <span>Description</span>
            <span>Cost</span>
            <span>On Hand</span>
            <span>Allocated</span>
          </div>

          <div id="orderPartsRows" class="parts-rows"></div>

          <div class="parts-total">
            <span>Parts Total</span>
            <input data-field="parts_total" type="number" step="0.01">
          </div>
        </div>
      </section>

      <section class="testing-panel">
        <div class="testing-title">Testing Data</div>

        <div class="testing-grid testing-head">
          <span>Part</span>
          <span>Bore / Diameter</span>
          <span>Length</span>
          <span>Thread</span>
          <span>Stop Tube/ET</span>
        </div>

        <div id="testingRows" class="testing-rows"></div>
      </section>
    </form>
  </main>

  <script src="{{ url_for('static', filename='order_form.js') }}"></script>
</body>
</html>
''')


ORDER_CSS = dedent(r'''\
* {
  box-sizing: border-box;
}

html,
body {
  min-height: 100%;
  margin: 0;
  background: #d7dadd;
  color: #111;
  font-family: Arial, Helvetica, sans-serif;
}

body {
  overflow: auto;
  padding: 14px;
}

.order-page {
  width: min(1180px, 100%);
  margin: 0 auto;
}

.order-toolbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 54px;
  padding: 9px 12px;
  background: #eef1f3;
  border: 1px solid #8b9298;
  border-radius: 8px 8px 0 0;
  box-shadow: 0 3px 8px #0002;
}

.toolbar-button,
.approve-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 7px 14px;
  border: 1px solid #69747d;
  border-radius: 7px;
  background: linear-gradient(#fff, #e4e9ed);
  box-shadow: 0 3px 0 #69747d, 0 4px 6px #0002;
  color: #111;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.toolbar-button:active,
.approve-button:active {
  transform: translateY(3px);
  box-shadow: 0 0 0 #69747d, 0 1px 2px #0002;
}

.approve-button {
  margin-left: auto;
  background: linear-gradient(#f3fff3, #cceaca);
  border-color: #4f7d51;
  color: #14551a;
  box-shadow: 0 3px 0 #4f7d51, 0 4px 6px #0002;
}

.approve-button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
  box-shadow: none;
}

.status-pill {
  padding: 6px 11px;
  border-radius: 999px;
  background: #fff3c4;
  border: 1px solid #b49931;
  font-size: 13px;
  font-weight: 700;
  text-transform: capitalize;
}

.status-pill.approved {
  background: #daf0da;
  border-color: #548457;
  color: #195821;
}

.toolbar-message {
  font-size: 13px;
  color: #333;
}

.toolbar-message.error {
  color: #a51515;
  font-weight: 700;
}

.order-sheet {
  width: 100%;
  min-height: 1350px;
  margin: 0 auto 30px;
  padding: 12px;
  background: #fff;
  border: 1px solid #333;
  box-shadow: 0 6px 20px #0003;
  font-size: 14px;
}

.order-sheet input,
.order-sheet textarea {
  width: 100%;
  min-width: 0;
  border: 0;
  border-bottom: 1px solid #111;
  background: #fffdf0;
  padding: 2px 5px;
  font: inherit;
  outline: 0;
}

.order-sheet input:focus,
.order-sheet textarea:focus {
  background: #fff1a8;
  box-shadow: inset 0 0 0 1px #c89c00;
}

.order-header {
  display: grid;
  grid-template-columns: 190px 1fr 250px;
  min-height: 106px;
  align-items: start;
  border-bottom: 2px solid #111;
  position: relative;
}

.order-logo {
  width: 175px;
  max-height: 90px;
  object-fit: contain;
  object-position: left top;
}

.order-header h1 {
  align-self: start;
  margin: 14px 0 0;
  text-align: center;
  font-size: 32px;
  line-height: 1;
  font-weight: 700;
}

.order-meta {
  display: grid;
  gap: 2px;
}

.order-meta label {
  display: grid;
  grid-template-columns: 68px 1fr;
  align-items: center;
  text-align: right;
  gap: 6px;
}

.order-meta input {
  text-align: center;
}

.address-grid {
  display: grid;
  grid-template-columns: 37% 26% 37%;
  min-height: 132px;
  padding: 12px 22px 8px;
  border-bottom: 1px solid #111;
  gap: 18px;
}

.address-block {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 6px;
  align-items: start;
}

.address-label {
  padding-top: 3px;
}

.address-block input {
  display: block;
  height: 24px;
}

.shipping-fields {
  display: grid;
  align-content: start;
  gap: 2px;
}

.shipping-fields label {
  display: grid;
  grid-template-columns: 76px 1fr;
  align-items: center;
  text-align: right;
  gap: 6px;
}

.shipping-fields input {
  height: 22px;
}

.order-summary {
  display: grid;
  grid-template-columns: minmax(0, 2.2fr) 0.55fr 0.85fr 0.85fr 1fr;
  border: 1px solid #111;
  border-bottom: 0;
}

.order-summary label {
  display: grid;
  grid-template-rows: 25px 28px;
  text-align: center;
  font-weight: 700;
  border-right: 1px solid #111;
}

.order-summary label:last-child {
  border-right: 0;
}

.order-summary input {
  text-align: center;
  border-top: 1px solid #111;
  border-bottom: 1px solid #111;
  font-weight: 400;
}

.order-body {
  display: grid;
  grid-template-columns: 37% 63%;
  min-height: 870px;
  border: 1px solid #111;
}

.cylinder-panel {
  position: relative;
  display: grid;
  grid-template-columns: 120px 1fr;
  align-content: start;
  padding: 4px 7px;
  border-right: 1px solid #111;
}

.cylinder-panel > label {
  grid-column: 1 / 3;
  font-weight: 400;
}

.cylinder-panel > label:not(.includes-row) {
  display: grid;
  grid-template-columns: 120px 1fr;
  align-items: center;
}

.cylinder-panel label {
  min-height: 27px;
}

.cylinder-panel > label > input,
.cylinder-panel > label > textarea {
  height: 27px;
}

.includes-row {
  display: grid !important;
  grid-template-columns: 120px 1fr !important;
  align-items: start;
  font-weight: 700 !important;
}

.includes-row textarea {
  height: 70px !important;
  resize: vertical;
}

.accessory-row {
  grid-column: 1 / 3;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 6px;
}

.accessory-row label {
  display: grid;
  grid-template-columns: 95px 1fr;
  align-items: center;
}

.assembly-fields {
  position: absolute;
  left: 7px;
  right: 7px;
  bottom: 12px;
  display: grid;
  gap: 10px;
}

.assembly-fields label {
  display: grid;
  grid-template-columns: 130px 1fr;
  align-items: center;
}

.parts-panel {
  display: flex;
  flex-direction: column;
}

.parts-header,
.part-row {
  display: grid;
  grid-template-columns: 16% 34% 15% 17% 18%;
}

.parts-header {
  height: 30px;
  font-weight: 700;
  text-align: center;
}

.parts-header span,
.part-row input {
  border-right: 1px solid #111;
  border-bottom: 1px solid #111;
}

.parts-header span {
  padding: 6px 3px;
}

.parts-header span:last-child,
.part-row input:last-child {
  border-right: 0;
}

.part-row {
  min-height: 29px;
}

.part-row input {
  text-align: center;
  border-radius: 0;
}

.part-row input:nth-child(2) {
  text-align: left;
}

.parts-total {
  display: grid;
  grid-template-columns: 50% 15% 35%;
  margin-top: auto;
  border-top: 1px solid #111;
}

.parts-total span {
  grid-column: 1;
  text-align: right;
  padding: 7px;
  font-weight: 700;
}

.parts-total input {
  grid-column: 2;
  text-align: center;
  border: 0;
  border-left: 1px solid #111;
  border-right: 1px solid #111;
}

.testing-panel {
  display: grid;
  grid-template-columns: 37% 63%;
  min-height: 150px;
  border: 1px solid #111;
  border-top: 0;
}

.testing-title {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 8px;
  border-right: 1px solid #111;
  font-weight: 700;
  background: repeating-linear-gradient(
    90deg,
    #fff 0 3px,
    #111 3px 4px,
    #fff 4px 8px
  );
  background-size: 55% 46px;
  background-repeat: no-repeat;
  background-position: center 45px;
}

.testing-grid {
  display: grid;
  grid-template-columns: 16% 30% 14% 16% 24%;
}

.testing-head {
  height: 30px;
  font-weight: 700;
  text-align: center;
}

.testing-head span {
  padding: 6px 2px;
  border-right: 1px solid #111;
  border-bottom: 1px solid #111;
}

.testing-head span:last-child {
  border-right: 0;
}

.testing-rows {
  grid-column: 2;
}

.test-row {
  display: grid;
  grid-template-columns: 16% 30% 14% 16% 24%;
  min-height: 29px;
}

.test-row input {
  border-right: 1px solid #111;
  border-bottom: 1px solid #111;
  text-align: center;
}

.test-row input:last-child {
  border-right: 0;
}

@media (max-width: 850px) {
  body {
    padding: 0;
  }

  .order-page {
    min-width: 760px;
  }

  .order-toolbar {
    position: relative;
  }

  .order-sheet {
    box-shadow: none;
  }

  .toolbar-message {
    max-width: 280px;
  }

  .order-header {
    grid-template-columns: 170px 1fr 230px;
  }

  .address-grid {
    padding-left: 10px;
    padding-right: 10px;
    gap: 10px;
  }
}

@media print {
  body {
    padding: 0;
    background: #fff;
  }

  .order-toolbar {
    display: none;
  }

  .order-sheet {
    box-shadow: none;
    margin: 0;
    border: 0;
    min-height: 11in;
  }
}
''')


ORDER_JS = dedent(r'''\
(() => {
  const page = document.querySelector('.order-page');
  const quoteId = Number(page.dataset.quoteId || 0);
  const form = document.getElementById('employeeOrderForm');
  const statusEl = document.getElementById('orderStatus');
  const messageEl = document.getElementById('orderMessage');
  const approveButton = document.getElementById('approveOrderButton');
  const partsHost = document.getElementById('orderPartsRows');
  const testingHost = document.getElementById('testingRows');

  const money = n => Number(n || 0).toFixed(2);

  const localDate = iso => {
    const d = iso ? new Date(iso) : new Date();
    return Number.isNaN(d.getTime())
      ? String(iso || '')
      : d.toLocaleString('en-US');
  };

  const value = (obj, key, fallback = '') =>
    obj && obj[key] != null ? obj[key] : fallback;

  const setMessage = (text, isError = false) => {
    messageEl.textContent = text || '';
    messageEl.classList.toggle('error', isError);
  };

  const setStatus = status => {
    statusEl.textContent = String(status || 'pending approval')
      .replaceAll('_', ' ');

    statusEl.classList.toggle('approved', status === 'approved');
    approveButton.disabled = status === 'approved';
    approveButton.textContent =
      status === 'approved' ? 'Approved' : 'Approve Order';
  };

  function splitAddress(customer, address) {
    const lines = [
      customer,
      ...String(address || '').split(/\r?\n|,/)
    ]
      .map(x => String(x || '').trim())
      .filter(Boolean);

    while (lines.length < 4) {
      lines.push('');
    }

    return lines.slice(0, 4);
  }

  function addPartRow(item = {}) {
    const row = document.createElement('div');
    row.className = 'part-row';

    [
      'part_number',
      'description',
      'cost',
      'on_hand',
      'allocated'
    ].forEach(key => {
      const input = document.createElement('input');
      input.dataset.partField = key;

      input.value = value(
        item,
        key,
        key === 'cost' || key === 'on_hand' || key === 'allocated'
          ? '0'
          : ''
      );

      if (
        key === 'cost' ||
        key === 'on_hand' ||
        key === 'allocated'
      ) {
        input.inputMode = 'decimal';
      }

      input.setAttribute('aria-label', key.replaceAll('_', ' '));
      row.appendChild(input);
    });

    partsHost.appendChild(row);
  }

  function addTestingRow(item = {}) {
    const row = document.createElement('div');
    row.className = 'test-row';

    [
      'part',
      'bore_diameter',
      'length',
      'thread',
      'stop_tube_et'
    ].forEach(key => {
      const input = document.createElement('input');
      input.dataset.testField = key;
      input.value = value(item, key, '');
      input.setAttribute(
        'aria-label',
        `Testing ${key.replaceAll('_', ' ')}`
      );
      row.appendChild(input);
    });

    testingHost.appendChild(row);
  }

  function collectRows(host, rowSelector, fieldAttribute) {
    return [...host.querySelectorAll(rowSelector)].map(row =>
      Object.fromEntries(
        [...row.querySelectorAll('input')].map(input => [
          input.dataset[fieldAttribute],
          input.value
        ])
      )
    );
  }

  function collectForm() {
    const fields = Object.fromEntries(
      [...form.querySelectorAll('[data-field]')].map(input => [
        input.dataset.field,
        input.value
      ])
    );

    fields.parts = collectRows(
      partsHost,
      '.part-row',
      'partField'
    );

    fields.testing = collectRows(
      testingHost,
      '.test-row',
      'testField'
    );

    return fields;
  }

  function recalculate() {
    const get = key =>
      form.querySelector(`[data-field="${key}"]`);

    const qty = Number(get('quantity').value || 0);
    const net = Number(get('net_each').value || 0);

    get('order_total').value = money(qty * net);

    const partsTotal = [
      ...partsHost.querySelectorAll('[data-part-field="cost"]')
    ].reduce(
      (sum, input) => sum + Number(input.value || 0),
      0
    );

    get('parts_total').value = money(partsTotal);
  }

  function buildDefaults(quote) {
    const inputs = quote.cylinder_inputs_snapshot || {};
    const bd = quote.price_breakdown_snapshot || {};
    const address = splitAddress(
      quote.customer_name,
      quote.customer_address
    );

    const specialParts = Object.entries(
      inputs.special_parts || {}
    ).map(([part, qty]) => ({
      part_number: part,
      description: `Quoted special part (Qty ${qty})`,
      cost: '0',
      on_hand: '0',
      allocated: String(qty || 0)
    }));

    const manualParts = (
      quote.manual_line_items || []
    ).map(item => ({
      part_number: item.reference_part_number || '',
      description: item.description || '',
      cost: money(item.unit_price),
      on_hand: '0',
      allocated: String(item.quantity || 0)
    }));

    const includes = [
      ...specialParts.map(x => x.part_number),
      ...manualParts.map(x => x.description)
    ]
      .filter(Boolean)
      .join(', ');

    const description = inputs.series
      ? `${inputs.series} Series Cylinder`
      : 'Cylinder';

    return {
      order_number: quote.quote_number || '',
      order_date: localDate(quote.created_at),
      terms: 'NET 30',

      ship_to_1: address[0],
      ship_to_2: address[1],
      ship_to_3: address[2],
      ship_to_4: address[3],

      bill_to_1: address[0],
      bill_to_2: address[1],
      bill_to_3: address[2],
      bill_to_4: address[3],

      po_number: quote.reference_notes || '',
      tag: quote.customer_name || '',
      ship_method: 'UPS Ground - Collect',
      ship_date: new Date().toLocaleDateString('en-US'),
      contact: quote.customer_contact || '',

      cylinder_description: description,
      quantity: '1',
      net_each: money(bd.quote_net_each),
      discount: money(Number(quote.discount || 0) * 100),
      order_total: money(bd.quote_net_each),

      description,
      model_code: quote.model_code || '',
      bore: value(inputs, 'bore'),
      mount: value(inputs, 'mount'),
      rod_diameter: value(inputs, 'rod_diameter'),
      cushion: value(inputs, 'cushion'),
      ports: value(inputs, 'port_code'),
      stroke: value(inputs, 'stroke'),
      rod_thread: value(inputs, 'rod_style'),
      seals: value(inputs, 'seal_code'),
      includes,

      rod_clevis: String(value(inputs, 'rod_clevis', 0)),
      pivot_pin: String(value(inputs, 'pivot_pin', 0)),
      assembled_by: '',
      date_passed_test: '',
      parts_total: '0.00',

      parts: [
        ...manualParts,
        ...specialParts
      ],

      testing: [
        {
          part: 'Rod',
          bore_diameter: value(inputs, 'rod_diameter'),
          length: value(inputs, 'stroke'),
          thread: value(inputs, 'rod_style'),
          stop_tube_et: value(inputs, 'stop_tube')
        },
        {
          part: 'Tie Rod',
          bore_diameter: '',
          length: value(inputs, 'tie_rod_length'),
          thread: '',
          stop_tube_et: ''
        },
        {
          part: 'Barrel',
          bore_diameter: value(inputs, 'bore'),
          length: value(inputs, 'stroke'),
          thread: '',
          stop_tube_et: ''
        }
      ]
    };
  }

  function render(quote) {
    const data = {
      ...buildDefaults(quote),
      ...(quote.order_form_snapshot || {})
    };

    form.querySelectorAll('[data-field]').forEach(input => {
      input.value = value(data, input.dataset.field, '');
    });

    partsHost.innerHTML = '';

    (data.parts || []).forEach(addPartRow);

    while (partsHost.children.length < 24) {
      addPartRow();
    }

    testingHost.innerHTML = '';

    (data.testing || []).forEach(addTestingRow);

    while (testingHost.children.length < 4) {
      addTestingRow();
    }

    setStatus(quote.status);
    recalculate();
  }

  form.addEventListener('input', event => {
    if (
      event.target.matches(
        '[data-field="quantity"],' +
        '[data-field="net_each"],' +
        '[data-part-field="cost"]'
      )
    ) {
      recalculate();
    }
  });

  approveButton.addEventListener('click', async () => {
    approveButton.disabled = true;
    approveButton.textContent = 'Approving…';
    setMessage('');

    try {
      const response = await fetch(
        `/api/quotes/${quoteId}/order/approve`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            order_form: collectForm()
          })
        }
      );

      const body = await response.json();

      if (!response.ok || !body.ok) {
        throw new Error(
          body.error || 'Approval failed'
        );
      }

      setStatus(body.quote.status);
      setMessage(
        `Order ${body.quote.quote_number} approved and saved.`
      );
    } catch (error) {
      approveButton.disabled = false;
      approveButton.textContent = 'Approve Order';
      setMessage(
        error.message || 'Approval failed',
        true
      );
    }
  });

  async function load() {
    if (!quoteId) {
      setMessage(
        'This approval link is missing a quote ID.',
        true
      );
      approveButton.disabled = true;
      return;
    }

    try {
      const response = await fetch(
        `/api/quotes/${quoteId}`
      );

      const body = await response.json();

      if (!response.ok || !body.ok) {
        throw new Error(
          body.error || 'Order not found'
        );
      }

      render(body.quote);
    } catch (error) {
      setMessage(
        error.message || 'Order could not be loaded.',
        true
      );

      statusEl.textContent = 'Error';
      approveButton.disabled = true;
    }
  }

  load();
})();
''')


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python BUILD_INTERNAL_ORDER_FORM.py "
            "<project-folder>"
        )

    project = Path(sys.argv[1]).resolve()
    app_dir = project / "app"

    required = [
        app_dir / "web.py",
        app_dir / "models_db.py",
        app_dir / "db.py",
        app_dir / "quote_service.py",
        app_dir / "email_service.py",
        app_dir / "static" / "app.js",
    ]

    if not all(path.is_file() for path in required):
        raise SystemExit(
            "The selected folder is not the Cylinder Quote "
            "project folder."
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = (
        project /
        f"backup_before_internal_order_form_{stamp}"
    )

    (backup / "app" / "templates").mkdir(parents=True)
    (backup / "app" / "static").mkdir(parents=True)

    for path in required:
        target = backup / path.relative_to(project)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    optional_backup_files = [
        app_dir / "templates" / "order_approval.html",
        app_dir / "static" / "approval.css",
        project / ".env.example",
    ]

    for path in optional_backup_files:
        if path.exists():
            target = backup / path.relative_to(project)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

    models_path = app_dir / "models_db.py"
    models = models_path.read_text(encoding="utf-8")

    models = replace_once(
        models,
        (
            "    special_instructions: Mapped[str | None] = "
            "mapped_column(Text, nullable=True)\n"
        ),
        (
            "    special_instructions: Mapped[str | None] = "
            "mapped_column(Text, nullable=True)\n"
            "    order_form_snapshot: Mapped[dict | None] = "
            "mapped_column(JSON, nullable=True)\n"
        ),
        "order snapshot model field",
    )

    models_path.write_text(models, encoding="utf-8")

    db_path = app_dir / "db.py"
    db = db_path.read_text(encoding="utf-8")

    old_db_migration = '''        if "special_instructions" not in quote_columns:
            connection.exec_driver_sql("ALTER TABLE quotes ADD COLUMN special_instructions TEXT")
'''

    new_db_migration = '''        if "special_instructions" not in quote_columns:
            connection.exec_driver_sql("ALTER TABLE quotes ADD COLUMN special_instructions TEXT")

        required_quote_columns = {
            "customer_address": "TEXT",
            "customer_contact": "TEXT",
            "comments": "TEXT",
            "revision": "INTEGER NOT NULL DEFAULT 1",
            "discount": "NUMERIC",
            "model_code": "VARCHAR(120)",
            "cylinder_inputs_snapshot": "JSON",
            "price_breakdown_snapshot": "JSON",
        }

        for column_name, column_type in required_quote_columns.items():
            if column_name not in quote_columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE quotes ADD COLUMN {column_name} {column_type}"
                )

        if "order_form_snapshot" not in quote_columns:
            connection.exec_driver_sql(
                "ALTER TABLE quotes ADD COLUMN order_form_snapshot JSON"
            )
'''

    db = replace_once(
        db,
        old_db_migration,
        new_db_migration,
        "database migration",
    )

    db_path.write_text(db, encoding="utf-8")

    service_path = app_dir / "quote_service.py"
    service = service_path.read_text(encoding="utf-8")

    service = replace_once(
        service,
        (
            '        "special_instructions": '
            'quote.special_instructions,\n'
        ),
        (
            '        "special_instructions": '
            'quote.special_instructions,\n'
            '        "order_form_snapshot": '
            'quote.order_form_snapshot,\n'
        ),
        "quote JSON order snapshot",
    )

    service_path.write_text(service, encoding="utf-8")

    email_path = app_dir / "email_service.py"
    email_text = email_path.read_text(encoding="utf-8")

    email_insert = dedent(r'''

    def send_order_approval_email(
        quote: Quote,
        approval_url: str,
        recipient: str,
        *,
        sent_by_user,
    ) -> EmailLog:
        """Email an internal link to the editable Order Form."""
        recipients = validate_recipients([recipient])
        subject = (
            f"Order approval requested: {quote.quote_number}"
        )

        if not is_email_configured():
            return EmailLog(
                quote=quote,
                revision=quote.revision,
                recipients=recipients,
                subject=subject,
                sent_by_user_id=sent_by_user.id,
                status="not_configured",
                error_message=(
                    "Email is not configured in this environment"
                ),
                document_id=None,
            )

        from_address = os.environ.get(
            "SMTP_FROM_ADDRESS", ""
        ).strip()

        host = os.environ.get("SMTP_HOST", "").strip()
        port = _smtp_port()
        use_tls = _env_bool("SMTP_USE_TLS", default=True)

        username = (
            os.environ.get("SMTP_USERNAME") or ""
        ).strip() or None

        password = os.environ.get("SMTP_PASSWORD") or ""

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = from_address
            msg["To"] = recipient

            msg.set_content(
                f"Order {quote.quote_number} is ready "
                f"for in-house review.\n\n"
                f"Open the editable Order Form:\n"
                f"{approval_url}\n"
            )

            with smtplib.SMTP(host, port) as server:
                if use_tls:
                    server.starttls()

                if username:
                    server.login(username, password)

                server.send_message(msg)

            return EmailLog(
                quote=quote,
                revision=quote.revision,
                recipients=recipients,
                subject=subject,
                sent_by_user_id=sent_by_user.id,
                status="sent",
                document_id=None,
            )

        except (smtplib.SMTPException, OSError) as exc:
            logger.exception(
                "Failed to send order approval email "
                "for quote %s",
                quote.quote_number,
            )

            return EmailLog(
                quote=quote,
                revision=quote.revision,
                recipients=recipients,
                subject=subject,
                sent_by_user_id=sent_by_user.id,
                status="failed",
                error_message=str(exc),
                document_id=None,
            )
    ''').rstrip() + "\n"

    email_marker = (
        "\ndef email_log_to_json("
        "email_log: EmailLog) -> dict[str, Any]:\n"
    )

    email_text = replace_once(
        email_text,
        email_marker,
        email_insert + email_marker,
        "order approval email function",
    )

    email_path.write_text(email_text, encoding="utf-8")

    web_path = app_dir / "web.py"
    web = web_path.read_text(encoding="utf-8")

    web = replace_once(
        web,
        "import logging\n",
        "import logging\nimport os\n",
        "web os import",
    )

    web = replace_once(
        web,
        "    send_quote_email,\n",
        (
            "    send_order_approval_email,\n"
            "    send_quote_email,\n"
        ),
        "order email import",
    )

    old_route = '''    @app.get("/order-approval")
    def order_approval():
        return render_template(
            "order_approval.html",
            quote_number=(request.args.get("quote") or "Pending Quote").strip(),
        )
'''

    new_route = '''    @app.get("/order-approval")
    @app.get("/order-form")
    def order_approval():
        return render_template(
            "order_form.html",
            quote_id=(request.args.get("quote_id") or "").strip(),
        )
'''

    web = replace_once(
        web,
        old_route,
        new_route,
        "order form page route",
    )

    api_block_source = dedent('''
    @app.post("/api/quotes/<int:quote_id>/order")
    def submit_order_for_approval(quote_id: int):
        payload = request.get_json(silent=True) or {}
        current_user = get_or_create_current_user(request)

        recipient = (
            os.environ.get("ORDER_APPROVAL_RECIPIENT")
            or "kane@jitindustries.com"
        ).strip()

        with get_session() as session:
            quote = get_quote(session, quote_id)

            if quote is None:
                return jsonify({
                    "ok": False,
                    "error": "Quote not found",
                }), 404

            order_form = payload.get("order_form")

            if order_form is not None:
                if not isinstance(order_form, dict):
                    return jsonify({
                        "ok": False,
                        "error": "order_form must be an object",
                    }), 400

                quote.order_form_snapshot = order_form

            quote.status = "pending_approval"
            quote.edited_by_user_id = current_user.id
            quote.edited_at = utc_now()

            session.add(quote)
            session.flush()

            configured_base = (
                os.environ.get("ORDER_APPROVAL_BASE_URL")
                or ""
            ).strip().rstrip("/")

            base_url = (
                configured_base
                or request.url_root.rstrip("/")
            )

            approval_url = (
                f"{base_url}/order-approval?"
                f"quote_id={quote.id}"
            )

            email_log = send_order_approval_email(
                quote,
                approval_url,
                recipient,
                sent_by_user=current_user,
            )

            session.add(email_log)

            if email_log.status == "sent":
                quote.emailed_by_user_id = current_user.id
                quote.emailed_at = utc_now()

            session.commit()

            return jsonify({
                "ok": True,
                "quote": quote_to_json(quote),
                "approval_url": approval_url,
                "approval_recipient": recipient,
                "email_log": email_log_to_json(email_log),
            })

    @app.post(
        "/api/quotes/<int:quote_id>/order/approve"
    )
    def approve_internal_order(quote_id: int):
        payload = request.get_json(silent=True) or {}
        order_form = payload.get("order_form")

        if not isinstance(order_form, dict):
            return jsonify({
                "ok": False,
                "error": "order_form must be an object",
            }), 400

        current_user = get_or_create_current_user(request)

        with get_session() as session:
            quote = get_quote(session, quote_id)

            if quote is None:
                return jsonify({
                    "ok": False,
                    "error": "Quote not found",
                }), 404

            quote.order_form_snapshot = order_form
            quote.status = "approved"
            quote.approved_by_user_id = current_user.id
            quote.approved_at = utc_now()
            quote.edited_by_user_id = current_user.id
            quote.edited_at = utc_now()

            session.add(quote)
            session.commit()

            return jsonify({
                "ok": True,
                "quote": quote_to_json(quote),
            })
    ''').strip("\n")

    api_block = "\n".join(
        "    " + line if line else line
        for line in api_block_source.splitlines()
    )

    api_marker = (
        '\n    @app.post('
        '"/api/quotes/<int:quote_id>/approve")\n'
    )

    web = replace_once(
        web,
        api_marker,
        "\n" + api_block + api_marker,
        "internal order API routes",
    )

    web_path.write_text(web, encoding="utf-8")

    app_js_path = app_dir / "static" / "app.js"
    app_js = app_js_path.read_text(encoding="utf-8")

    old_success = '''    currentQuote = body.quote;
    renderQuotePreview(body.quote);
    $('previewErrorMessage').textContent =
      `Order saved to database as ${body.quote.quote_number}.`;
'''

    new_success = '''    currentQuote = body.quote;

    const orderResponse = await fetch(
      `/api/quotes/${body.quote.id}/order`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({})
      }
    );

    const orderBody = await orderResponse.json();

    if (!orderResponse.ok || !orderBody.ok) {
      throw new Error(
        orderBody.error ||
        'Order approval request failed'
      );
    }

    currentQuote = orderBody.quote;
    renderQuotePreview(orderBody.quote);

    const emailStatus =
      orderBody.email_log &&
      orderBody.email_log.status;

    $('previewErrorMessage').textContent =
      emailStatus === 'sent'
        ? `Order ${orderBody.quote.quote_number} saved. Approval link emailed to ${orderBody.approval_recipient}.`
        : `Order ${orderBody.quote.quote_number} saved and is pending approval. Email was not sent because SMTP email is not configured.`;
'''

    app_js = replace_once(
        app_js,
        old_success,
        new_success,
        "Order Now approval request",
    )

    app_js_path.write_text(app_js, encoding="utf-8")

    template_path = (
        app_dir / "templates" / "order_form.html"
    )

    css_path = (
        app_dir / "static" / "order_form.css"
    )

    js_path = (
        app_dir / "static" / "order_form.js"
    )

    template_path.write_text(
        ORDER_HTML.lstrip("\\\r\n"),
        encoding="utf-8",
    )

    css_path.write_text(
        ORDER_CSS.lstrip("\\\r\n"),
        encoding="utf-8",
    )

    js_path.write_text(
        ORDER_JS.lstrip("\\\r\n"),
        encoding="utf-8",
    )

    env_path = project / ".env.example"

    env_text = (
        env_path.read_text(encoding="utf-8")
        if env_path.exists()
        else ""
    )

    env_text += (
        "\n# Internal Order Form approval email\n"
        "ORDER_APPROVAL_RECIPIENT="
        "kane@jitindustries.com\n"
        "# Set this to an address reachable by employees.\n"
        "# Example: http://192.168.1.50:5055\n"
        "# ORDER_APPROVAL_BASE_URL="
        "http://127.0.0.1:5055\n"
    )

    env_path.write_text(
        env_text,
        encoding="utf-8",
    )

    print(
        f"Internal Order Form installed in: {project}"
    )

    print(
        f"Backup: {backup}"
    )


if __name__ == "__main__":
    main()