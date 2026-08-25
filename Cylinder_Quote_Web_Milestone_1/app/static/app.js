let catalog = null;
let currentQuote = null;
const $ = id => document.getElementById(id);
const PORTAL_MODE = document.body.dataset.portalMode || 'employee';
const CURRENT_USER_NAME = (document.body.dataset.currentUserName || '').trim();
const PREFILL_CUSTOMER_NAME = (document.body.dataset.prefillCustomerName || '').trim();
const PREFILL_CUSTOMER_ADDRESS = (document.body.dataset.prefillCustomerAddress || '').trim();
const ASSIGNED_PROMO_CODE = (document.body.dataset.assignedPromoCode || '').toUpperCase();
const ASSIGNED_PROMO_DISCOUNT = document.body.dataset.assignedDiscountPercent ? Number(document.body.dataset.assignedDiscountPercent) : null;

function fillSelect(el, values, labeler = x => x, includeBlank = false) {
  el.innerHTML = '';
  if (includeBlank) {
    const blank = document.createElement('option');
    blank.value = '';
    blank.textContent = '';
    el.appendChild(blank);
  }
  values.forEach(v => {
    const opt = document.createElement('option');
    if (typeof v === 'object') { opt.value = v.value; opt.textContent = v.label; }
    else { opt.value = v; opt.textContent = labeler(v); }
    el.appendChild(opt);
  });
}
function fmtMoney(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2}) : '—';
}
function fmtRoundedMoney(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.ceil(n).toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:0,maximumFractionDigits:0}) : '—';
}
const TIE_ROD_RATES = Object.freeze([
  {diameter:'0.25',price:7.00},
  {diameter:'0.312',price:7.50},
  {diameter:'0.375',price:8.00},
  {diameter:'0.5',price:8.50},
  {diameter:'0.625',price:9.00},
  {diameter:'0.75',price:12.00},
  {diameter:'0.875',price:14.00},
  {diameter:'1',price:18.00},
  {diameter:'1.125',price:23.00},
  {diameter:'1.25',price:25.00}
]);
function boolFromYN(id) { return String($(id).value || '').toUpperCase() === 'Y'; }
// Shows full "value - description" labels while the dropdown is open, but collapses
// the closed box to just the value so model codes stay standardized on plain numbers.
function setupShortDisplaySelect(el) {
  const fullLabels = new Map();
  Array.from(el.options).forEach(opt => fullLabels.set(opt.value, opt.textContent));
  function showFull() {
    Array.from(el.options).forEach(opt => { const full = fullLabels.get(opt.value); if (full !== undefined) opt.textContent = full; });
  }
  function showShortForSelected() {
    const opt = el.options[el.selectedIndex];
    if (opt && opt.value) opt.textContent = opt.value;
  }
  el.addEventListener('mousedown', showFull);
  el.addEventListener('focus', showFull);
  el.addEventListener('change', showShortForSelected);
  el.addEventListener('blur', showShortForSelected);
  showShortForSelected();
}
function updateMountsForSeries() {
  const s = $('series').value;
  const previous = $('mount').value;
  const mounts = s ? ((catalog.series_mounts || {})[s] || []) : [];
  fillSelect($('mount'), mounts, x => x, true);
  if (mounts.includes(previous)) $('mount').value = previous;
}
function updateBores() {
  const s = $('series').value;
  const bores = s ? Object.keys(catalog.series[s] || {}).sort((a,b)=>Number(a)-Number(b)) : [];
  fillSelect($('bore'), bores, x => x, true);
  updateRods();
}
function updateRods() {
  const s=$('series').value, b=$('bore').value;
  const rods=(s && b) ? Object.keys((catalog.series[s]||{})[b]||{}).sort((a,b)=>Number(a)-Number(b)) : [];
  fillSelect($('rod_diameter'), rods, x => x, true);
}
function wireTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const parent = btn.closest('.legacy-panel');
      parent.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
      parent.querySelectorAll('.tab-panel').forEach(x=>x.classList.remove('active'));
      btn.classList.add('active');
      $(btn.dataset.tab).classList.add('active');
    });
  });
}
function wireWholeNumberInputs() {
  ['rod_extension','extra_thread','legacy_post_discount_add','discount_pct'].forEach(id => {
    const el = $(id);
    if (!el) return;
    el.addEventListener('input', () => {
      if (el.value !== '') el.value = String(Math.round(Number(el.value)));
    });
  });
}
let customerSuggestions = [];
let customerSearchTimer = null;
function applyMatchedCustomerContact() {
  const typed = ($('customer_name').value || '').trim().toLowerCase();
  const match = customerSuggestions.find(c => c.name.toLowerCase() === typed);
  window.JIT_SELECTED_CUSTOMER_CONTACT = match ? (match.phone || '') : '';
  if (match && match.address && !$('customer_address').value) {
    $('customer_address').value = match.address;
  }
}
async function searchCustomers(term) {
  try {
    const res = await fetch(`/api/customers/search?q=${encodeURIComponent(term)}`);
    const body = await res.json();
    if (!body.ok) return;
    customerSuggestions = body.customers || [];
    const dl = $('customerNameList');
    dl.innerHTML = '';
    customerSuggestions.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      dl.appendChild(opt);
    });
    applyMatchedCustomerContact();
  } catch (e) { /* ignore transient errors while the user is still typing */ }
}
function wireCustomerAutocomplete() {
  const input = $('customer_name');
  if (!input) return;
  input.addEventListener('input', () => {
    applyMatchedCustomerContact();
    clearTimeout(customerSearchTimer);
    const term = input.value.trim();
    if (!term) { customerSuggestions = []; window.JIT_SELECTED_CUSTOMER_CONTACT = ''; return; }
    customerSearchTimer = setTimeout(() => searchCustomers(term), 250);
  });
}
function populateTieRodOptions() {
  const sel = $('tie_rod_diameter');
  if (!sel) return;
  sel.innerHTML = '';
  const blank = document.createElement('option');
  blank.value = ''; blank.textContent = '';
  sel.appendChild(blank);
  TIE_ROD_RATES.forEach(r => {
    const o = document.createElement('option');
    o.value = r.diameter; o.textContent = r.diameter; o.dataset.price = String(r.price);
    sel.appendChild(o);
  });
}
function updateTieRodCost() {
  const sel = $('tie_rod_diameter'), len = $('tie_rod_length'), cost = $('tie_rod_cost');
  if (!sel || !len || !cost) return;
  const opt = sel.options[sel.selectedIndex];
  const price = opt && opt.dataset.price ? Number(opt.dataset.price) : NaN;
  const length = Number(len.value);
  if (!Number.isFinite(price) || !Number.isFinite(length) || length <= 0) { cost.value = ''; return; }
  cost.value = fmtMoney(price * length);
}
function buildSpecialRows() {
  const host = $('specialParts');
  host.innerHTML = '';
  let dl = $('specialPartsList');
  if (!dl) {
    dl = document.createElement('datalist');
    dl.id = 'specialPartsList';
    catalog.special_parts.forEach(p => { const o = document.createElement('option'); o.value = p; dl.appendChild(o); });
    document.body.appendChild(dl);
  }
  for (let i=0;i<6;i++) {
    const row=document.createElement('div'); row.className='part-row special-row';
    const inp=document.createElement('input'); inp.type='text'; inp.className='special-part-name'; inp.setAttribute('list','specialPartsList'); inp.setAttribute('autocomplete','off');
    const desc=document.createElement('input'); desc.className='special-part-description'; desc.readOnly=true;
    const qty=document.createElement('input'); qty.type='number';qty.min='0';qty.step='1';qty.value='';qty.className='special-part-qty';
    const price=document.createElement('input'); price.className='special-part-price'; price.readOnly=true;
    inp.addEventListener('input',()=>{
      const detail=(catalog.special_part_details||{})[inp.value]||{};
      desc.value=detail.description||'';
      price.value=detail.price ? fmtMoney(detail.price) : '';
      if (inp.value && catalog.special_part_details && (inp.value in catalog.special_part_details) && !qty.value) qty.value = '1';
    });
    row.append(inp,desc,qty,price); host.appendChild(row);
  }
}
function addOrderEntryManualItemRow(item) {
  item = item || { part_number: '', description: '', quantity: '', unit_price: '', note: '' };
  const host = $('orderEntryManualItems');
  const row = document.createElement('div'); row.className = 'oe-manual-row';
  const ref = document.createElement('input'); ref.type = 'text'; ref.value = item.part_number || ''; ref.placeholder = 'Part #'; ref.className = 'manual-ref';
  const desc = document.createElement('input'); desc.type = 'text'; desc.value = item.description || ''; desc.placeholder = 'Description *'; desc.className = 'manual-desc';
  const qty = document.createElement('input'); qty.type = 'number'; qty.min = '0'; qty.step = '1'; qty.value = item.quantity || ''; qty.className = 'manual-qty';
  const unit = document.createElement('input'); unit.type = 'number'; unit.min = '0'; unit.step = '0.01'; unit.value = item.unit_price || ''; unit.className = 'manual-unit';
  const ext = document.createElement('input'); ext.type = 'text'; ext.readOnly = true; ext.value = ''; ext.className = 'manual-ext';
  const note = document.createElement('input'); note.type = 'text'; note.value = item.note || ''; note.placeholder = 'Note'; note.className = 'manual-note';
  const rm = document.createElement('button'); rm.type = 'button'; rm.textContent = '×'; rm.className = 'manual-remove'; rm.title = 'Remove line';
  function updateExt() { const q = Number(qty.value || 0), u = Number(unit.value || 0); ext.value = fmtMoney(q * u); }
  qty.addEventListener('input', updateExt); unit.addEventListener('input', updateExt);
  rm.addEventListener('click', () => { row.remove(); if (!host.children.length) addOrderEntryManualItemRow(); });
  row.append(ref, desc, qty, unit, ext, note, rm); host.appendChild(row);
}
function buildOrderEntryManualItems() {
  const host = $('orderEntryManualItems');
  host.innerHTML = '';
  addOrderEntryManualItemRow();
}
function resetQuoteForm() {
  $('customer_name').value = PREFILL_CUSTOMER_NAME;
  $('customer_address').value = PREFILL_CUSTOMER_ADDRESS;
  $('series').value = '';
  updateMountsForSeries();
  updateBores();
  $('stroke').value = '';
  $('rod_style').value = '';
  $('cushion').value = '';
  $('port_code').value = '';
  $('seal_code').value = '';
  $('dre_input').value = '';
  $('discount_pct').value = '';
  $('coupon_code').value = '';
  $('couponMessage').textContent = '';
  $('couponMessage').className = 'coupon-message';
  $('standard_rod_boot_qty').value = '';
  ['rod_extension','stop_tube','extra_thread','air_bleed_qty','prox_switch_qty','extra_port_qty','extra_tie_rod_qty','thick_head_qty','legacy_post_discount_add'].forEach(id => $(id).value = '');
  ['stainless_rod','chrome_bore','rod_gland_drain','brass_wiper','ultraox','transducer','prepped_for_transducer','sensor_cover','valve_manifold'].forEach(id => $(id).value = '');
  document.querySelectorAll('[data-accessory]').forEach(inp => inp.value = '');
  document.querySelectorAll('.special-row').forEach(row => {
    row.querySelector('.special-part-name').value = '';
    row.querySelector('.special-part-description').value = '';
    row.querySelector('.special-part-qty').value = '';
    row.querySelector('.special-part-price').value = '';
  });
  buildOrderEntryManualItems();
  $('pressure').value = '';
  $('xi_mt4').value = '';
  $('force_display').value = '';
  $('tie_rod_diameter').value = '';
  $('tie_rod_length').value = '';
  $('tie_rod_cost').value = '';
  $('quote_net_each').value = '$0.00';
  $('profit_display').value = '$0.00';
  $('errorMessage').textContent = '';
  const model = $('model_code'); if (model) model.textContent = '';
}
window.resetQuoteForm = resetQuoteForm;

function payload() {
  const p = {
    series:$('series').value,bore:$('bore').value,rod_diameter:$('rod_diameter').value,mount:$('mount').value,
    stroke:$('stroke').value,cushion:$('cushion').value,port_code:$('port_code').value,seal_code:$('seal_code').value,
    rod_style:Number($('rod_style').value),discount:Number($('discount_pct').value||0)/100,
    dre:String($('dre_input').value||'').trim().toUpperCase()==='Y',
    standard_rod_boot_qty:$('standard_rod_boot_qty').value,
    rod_extension:$('rod_extension').value,stop_tube:$('stop_tube').value,extra_thread:$('extra_thread').value,
    air_bleed_qty:$('air_bleed_qty').value,prox_switch_qty:$('prox_switch_qty').value,extra_port_qty:$('extra_port_qty').value,
    extra_tie_rod_qty:$('extra_tie_rod_qty').value,thick_head_qty:$('thick_head_qty').value,
    legacy_post_discount_add:$('legacy_post_discount_add').value,
    stainless_rod:boolFromYN('stainless_rod'),chrome_bore:boolFromYN('chrome_bore'),rod_gland_drain:boolFromYN('rod_gland_drain'),
    brass_wiper:boolFromYN('brass_wiper'),ultraox:boolFromYN('ultraox'),transducer:boolFromYN('transducer'),
    prepped_for_transducer:boolFromYN('prepped_for_transducer'),sensor_cover:boolFromYN('sensor_cover'),valve_manifold:boolFromYN('valve_manifold'),
    accessory_quantities:{},special_parts:{}
  };
  document.querySelectorAll('[data-accessory]').forEach(inp=>{if(Number(inp.value)>0)p.accessory_quantities[inp.dataset.accessory]=inp.value;});
  document.querySelectorAll('.special-row').forEach(row=>{
    const n=row.querySelector('.special-part-name').value,q=row.querySelector('.special-part-qty').value;
    if(n&&Number(q)>0)p.special_parts[n]=q;
  });
  p.customer_name = $('customer_name').value;
  p.customer_address = $('customer_address').value;
  p.customer_contact = window.JIT_SELECTED_CUSTOMER_CONTACT || '';
  p.reference_notes = '';
  p.comments = '';
  p.manual_line_items = [];
  return p;
}
function manualItemsFromOrderEntry() {
  const items = [];
  document.querySelectorAll('#orderEntryManualItems .oe-manual-row').forEach(row => {
    const description = row.querySelector('.manual-desc').value.trim();
    if (!description) return;
    items.push({
      part_number: row.querySelector('.manual-ref').value.trim() || null,
      description,
      quantity: Number(row.querySelector('.manual-qty').value || 0),
      unit_price: Number(row.querySelector('.manual-unit').value || 0),
      note: row.querySelector('.manual-note').value.trim() || null
    });
  });
  return items;
}
function draftPayload() {
  const p = payload();
  return {
    ...p,
    manual_items: manualItemsFromOrderEntry(),
    customer_name: p.customer_name,
    customer_contact: '',
    customer_reference: '',
    comments: ''
  };
}
function showResult(r) {
  $('model_code').textContent=r.model_code;
  $('quote_net_each').value=fmtMoney(r.quote_net_each);
  $('dialog_net_each').textContent=fmtMoney(r.quote_net_each);
  ['quote_list_price','expedited_price','emergency_price','base_price','stroke_cushion','modifications','accessories','special_parts','position_sensing','va_total','dre_surcharge','pre_discount_subtotal','working_net_each'].forEach(k=>$(k).textContent=fmtMoney(r[k]));
  $('display_discount').textContent=(Number($('discount_pct').value||0)).toFixed(0)+'%';
  const box=$('warningsBox'), list=$('warnings'); list.innerHTML='';
  (r.warnings||[]).forEach(w=>{const li=document.createElement('li');li.textContent=w;list.appendChild(li);}); box.hidden=!(r.warnings||[]).length;
  const dlg=$('quoteResultDialog'); if (dlg.showModal) dlg.showModal();
}
let liveCalcTimer = null;
// Recalculates Net Each / Profit live as the cylinder spec (model code) is filled in, without opening the Quote dialog.
async function liveRecalculate() {
  const p = payload();
  if (!p.series || !p.bore || !p.rod_diameter || !p.mount || !p.stroke) {
    $('quote_net_each').value = '$0.00';
    $('profit_display').value = '$0.00';
    return;
  }
  try {
    const res = await fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(p)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) return;
    const r = body.result;
    $('quote_net_each').value = fmtMoney(r.quote_net_each);
    $('profit_display').value = fmtMoney(r.profit);
  } catch (e) { /* ignore transient errors while the user is still typing */ }
}
function scheduleLiveRecalculate() {
  clearTimeout(liveCalcTimer);
  liveCalcTimer = setTimeout(liveRecalculate, 300);
}
async function init() {
  wireTabs();
  try {
    const res=await fetch('/api/catalog'); if(!res.ok) throw new Error('Catalog request failed'); catalog=await res.json();
    fillSelect($('series'),Object.keys(catalog.series),x=>x,true);
    fillSelect($('cushion'),catalog.cushions,x=>x,true); fillSelect($('port_code'),catalog.port_codes,x=>x||'',true); fillSelect($('seal_code'),catalog.seal_codes,x=>x||'',true); fillSelect($('rod_style'),catalog.rod_styles,x=>x,true);
    setupShortDisplaySelect($('rod_style'));
    $('series').addEventListener('change',()=>{updateMountsForSeries();updateBores();}); $('bore').addEventListener('change',updateRods);
    $('dre_input').addEventListener('input',()=>{$('dre_input').value=$('dre_input').value.toUpperCase().replace(/[^Y]/g,'').slice(0,1);});
    updateMountsForSeries(); updateBores(); buildSpecialRows(); buildOrderEntryManualItems(); populateTieRodOptions(); resetQuoteForm(); wireWholeNumberInputs(); wireCustomerAutocomplete();

    // Task 1: Load existing quote if quote_id URL param is present
    const quoteIdParam = new URLSearchParams(window.location.search).get('quote_id');
    if (quoteIdParam) {
      try {
        const loadRes = await fetch('/api/quotes/' + encodeURIComponent(quoteIdParam));
        const loadBody = await loadRes.json();
        if (loadRes.ok && loadBody.ok && loadBody.quote) {
          const q = loadBody.quote;
          pendingQuotePayload = {
            ...(q.cylinder_inputs_snapshot || {}),
            discount: Number(q.discount || 0),
            customer_name: q.customer_name || '',
            customer_address: q.customer_address || '',
            customer_contact: q.customer_contact || '',
            manual_items: (q.manual_line_items || []).map(x => ({
              part_number: x.reference_part_number,
              description: x.description,
              quantity: x.quantity,
              unit_price: x.unit_price,
              note: x.internal_note
            }))
          };
          isEditingExistingQuote = true;
          renderQuotePreview(q);
          return;
        }
      } catch (loadErr) {
        // fall through to normal blank-start flow
      }
    }

    // Task 3: Auto-apply assigned promo code for customer mode
    if (PORTAL_MODE === 'customer' && ASSIGNED_PROMO_CODE) {
      $('coupon_code').value = ASSIGNED_PROMO_CODE;
      applyCouponCode();
    }

    $('tie_rod_diameter').addEventListener('change', updateTieRodCost);
    $('tie_rod_length').addEventListener('input', updateTieRodCost);
  } catch(e) { $('errorMessage').textContent=e.message; }
}

const COUPON_DISCOUNTS = Object.freeze({
  '20OFF': 20
});

function applyCouponCode() {
  const code = String($('coupon_code').value || '').trim().toUpperCase();
  const message = $('couponMessage');
  $('coupon_code').value = code;

  if (!code) {
    message.textContent = 'Enter a coupon code.';
    message.className = 'coupon-message error';
    return;
  }

  let discount = COUPON_DISCOUNTS[code];
  if (discount === undefined && ASSIGNED_PROMO_CODE && code === ASSIGNED_PROMO_CODE && ASSIGNED_PROMO_DISCOUNT !== null) {
    discount = ASSIGNED_PROMO_DISCOUNT;
  }
  if (discount === undefined) {
    message.textContent = 'Coupon code not recognized.';
    message.className = 'coupon-message error';
    return;
  }

  $('discount_pct').value = String(discount);
  message.textContent = `${code} applied — ${discount}% off`;
  message.className = 'coupon-message success';
  scheduleLiveRecalculate();
}

$('applyCouponButton').addEventListener('click', applyCouponCode);
$('coupon_code').addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    event.preventDefault();
    applyCouponCode();
  }
});

$('addOrderEntryManualItemButton').addEventListener('click', () => addOrderEntryManualItemRow());
$('quoteForm').addEventListener('input', scheduleLiveRecalculate);
$('quoteForm').addEventListener('change', scheduleLiveRecalculate);
let pendingQuotePayload = null;
let isEditingExistingQuote = false;

$('quoteForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('errorMessage').textContent = '';
  $('calculateButton').disabled = true;
  $('calculateButton').textContent = 'Opening...';
  try {
    pendingQuotePayload = draftPayload();
    const res = await fetch('/api/quote/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(pendingQuotePayload)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) throw new Error(body.error || 'Quote draft failed');

    const d = body.draft;
    // Quote ID is created when the Quote button is clicked:
    // first letter of Quote Entry customer name + mmddyyhhmm
    const quoteCustomerName = (pendingQuotePayload.customer_name
      || (d.presentation && d.presentation.customer_name)
      || '').trim();
    const quoteNumber = buildExcelQuoteNumber(quoteCustomerName, new Date());
    pendingQuotePayload.quote_number = quoteNumber;
    const quoteLike = {
      id: null,
      quote_number: quoteNumber,
      revision: 1,
      status: 'Unsaved',
      quantity: Math.max(1, Number(window.JIT_EDIT_QUANTITY || 1)),
      pricing_version: d.pricing_engine_version || 'Pricing Engine v1.2',
      created_by: CURRENT_USER_NAME,
      created_at: d.timestamp,
      customer_name: (d.presentation && d.presentation.customer_name) || pendingQuotePayload.customer_name || '',
      customer_address: pendingQuotePayload.customer_address || '',
      customer_contact: (d.presentation && d.presentation.customer_contact) || '',
      reference_notes: (d.presentation && d.presentation.customer_reference) || '',
      comments: (d.presentation && d.presentation.comments) || '',
      model_code: d.model_code,
      discount: Number(pendingQuotePayload.discount || 0),
      cylinder_inputs_snapshot: d.cylinder_inputs || {},
      price_breakdown_snapshot: d.price_breakdown || {},
      manual_line_items: (d.manual_items || []).map(x => ({
        reference_part_number: x.reference_part_number || x.part_number || null,
        description: x.description || '',
        quantity: x.quantity || 0,
        unit_price: x.unit_price || 0,
        internal_note: x.internal_note || x.note || null,
        show_on_customer_quote: x.show_on_customer_quote !== false
      }))
    };
    renderQuotePreview(quoteLike);
  } catch (e) {
    $('errorMessage').textContent = e.message;
  } finally {
    $('calculateButton').disabled = false;
    $('calculateButton').textContent = 'Quote';
  }
});

window.jitCalculatorReady = init();

/* Quote Preview view support */
function setActiveViewStyles(viewId) {
  const pricingStyles = $('pricingCalculatorStylesheet');
  const quoteStyles = $('quoteFormStylesheet');
  const quoteIsOpen = viewId === 'quotePreviewView';
  if (pricingStyles) pricingStyles.disabled = quoteIsOpen;
  if (quoteStyles) quoteStyles.disabled = !quoteIsOpen;
}
function showView(viewId) {
  setActiveViewStyles(viewId);
  document.querySelectorAll('.view').forEach(v => { v.classList.remove('active'); v.classList.add('hidden'); });
  const view = $(viewId);
  if (view) { view.classList.remove('hidden'); view.classList.add('active'); }
  queueOrderEntryScale();
}
setActiveViewStyles('orderEntryView');
function showOrderEntry() { currentQuote = null; isEditingExistingQuote = false; resetQuoteForm(); showView('orderEntryView'); }
function formatDateTime(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleString(); } catch { return iso; } }
function buildExcelQuoteNumber(customerName, when) {
  const customer = String(customerName || '').trim();
  const match = customer.match(/[A-Za-z]/);
  const initial = match ? match[0].toUpperCase() : 'X';
  const d = when instanceof Date ? when : (when ? new Date(when) : new Date());
  const two = value => String(value).padStart(2, '0');
  // Format: first letter of Quote Entry name + mmddyyhhmm
  // Example: "A C" at 08/19/2026 12:42 -> A0819261242
  return initial
    + two(d.getMonth() + 1)
    + two(d.getDate())
    + two(d.getFullYear() % 100)
    + two(d.getHours())
    + two(d.getMinutes());
}
function formatQuoteDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const month = d.toLocaleString('en-US', { month: 'short' });
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${month}-${d.getDate()} (${hh}:${mm})`;
  } catch { return iso; }
}
/* Values below are determined from the cylinder quote entry selections using the Excel formulas/tables. */
function excelRoundUpPositive(value) {
  return Math.ceil(Math.max(Number(value) || 0, 0));
}
function computePushPull(pressure, bore, rod, isMetric) {
  const p = Number(pressure) || 0;
  const divisor = isMetric ? 25.4 : 1;
  const b = (Number(bore) || 0) / divisor;
  const r = (Number(rod) || 0) / divisor;
  const boreForce = ((b / 2) * (b / 2)) * 3.1416 * p;
  const rodForce = ((r / 2) * (r / 2)) * 3.1416 * p;
  return {
    push: excelRoundUpPositive(boreForce),
    pull: excelRoundUpPositive(boreForce - rodForce)
  };
}

const H_ASSEMBLY_PRICE = {
  '1.5|0.625':[161,308,9], '1.5|1':[192,339,11], '2|1':[192,353,12], '2|1.375':[224,385,13],
  '2.5|1':[204,386,13], '2.5|1.375':[247,429,14], '2.5|1.75':[279,461,17],
  '3.25|1.375':[253,463,17], '3.25|1.75':[307,517,19], '3.25|2':[328,538,21],
  '4|1.75':[315,561,21], '4|2':[378,624,24], '4|2.5':[419,665,26],
  '5|2':[431,703,29], '5|2.5':[496,768,33], '5|3':[554,826,37], '5|3.5':[615,887,42],
  '6|2.5':[672,1012,37], '6|3':[779,1119,42], '6|3.5':[869,1209,48], '6|4':[922,1262,54],
  '7|3':[898,1280,49], '7|3.5':[1008,1390,52], '7|4':[1090,1472,58], '7|4.5':[1110,1492,66], '7|5':[1127,1509,71],
  '8|3.5':[1164,1578,65], '8|4':[1299,1713,70], '8|4.5':[1385,1799,76], '8|5':[1474,1888,87], '8|5.5':[1606,2020,95],
  '10|4.5':[1896,2367,133], '10|5':[2142,2613,141], '10|5.5':[2239,2710,147], '10|7':[2664,3135,169],
  '12|5.5':[2925,3580,185], '12|7':[3763,4418,199], '12|8':[4122,4777,222],
  '14|8':[6598,7523,259], '14|10':[6598,7523,323], '16|8':[7569,8769,248], '16|10':[8988,10188,341],
  '18|8':[11324,12724,330], '18|10':[11827,13227,353], '20|10':[14167,15567,444]
};

/* Best-effort industry-standard labels for display only; not authoritative business data. */
const CUSHION_LABELS = { NC: 'Non Cushion', RE: 'Rod End', CE: 'Cap End', BE: 'Both Ends', ARE: 'Adj. Rod End', ACE: 'Adj. Cap End', ABE: 'Adj. Both Ends' };
const SEAL_LABELS = { P: 'Polyurethane', V: 'Viton', B: 'Buna-N' };
function labelFor(map, code) { return (code && map[code]) ? `${map[code]} (${code})` : (code || '—'); }

function renderQuotePreview(quote) {
  currentQuote = quote;
  $('pv_quote_number').textContent = quote.quote_number || 'Not saved yet';
  $('pv_status').textContent = quote.status || '—';
  $('saveQuoteButton').textContent = isEditingExistingQuote ? 'Update Quote' : 'Order Now';
  $('pv_created_by').textContent = quote.created_by || CURRENT_USER_NAME || '—';
  const createdByFooter = $('pv_created_by_footer');
  if (createdByFooter) createdByFooter.textContent = quote.created_by || CURRENT_USER_NAME || '—';
  $('pv_created_at').textContent = formatQuoteDate(quote.created_at);
  $('pv_customer_name').value = quote.customer_name || '';
  $('pv_customer_address').value = quote.customer_address || '';
  $('pv_customer_contact').value = quote.customer_contact || '';
  $('pv_customer_attn').value = quote.customer_attn || '';
  $('pv_reference_notes').value = quote.reference_notes || '';
  $('pv_comments').value = quote.comments || '';
  $('pv_special_instructions').value = quote.special_instructions || '';

  const inputs = quote.cylinder_inputs_snapshot || {};
  const series = String(inputs.series || '').toUpperCase();
  const bore = Number(inputs.bore || 0), rod = Number(inputs.rod_diameter || 0), stroke = Number(inputs.stroke || 0);
  const SERIES_LABELS = {
    H:'High Pressure Hydraulic Cylinder', HM:'Mill Duty Hydraulic Cylinder', MH:'High Pressure Hydraulic Mill Cylinder',
    A:'High Pressure Pneumatic Cylinder', LH:'Low Pressure Hydraulic Cylinder', VA:'Pneumatic Valve Actuator',
    IH:'High Pressure Metric Hydraulic Cylinder', IMH:'High Pressure Metric Mill Cylinder', IHM:'High Pressure Metric Mill Cylinder'
  };
  const MOUNT_LABELS = {MF1:'Rect Head Flange',MF2:'Rect Cap Flange',MF5:'Square Head Flange',MF6:'Square Cap Flange',MP1:'Fixed Cap Clevis',MP2:'Detachable Cap Clevis',MP3:'Pivot Eye',MPU3:'Self Aligning Eye',MS1:'Angle Foot',MS2:'Side Lugs',MS3:'Centerline Lug',MS4:'Side Tapped',MS7:'Foot Lug',MT1:'Head Trunnion',MT2:'Cap Trunnion',MT4:'Center Trunnion',MX0:'No Mount',MX1:'Extended Both Ends',MX2:'Extended Cap End',MX3:'Extended Head End',ME3:'Full Head Flange',ME4:'Full Cap Flange'};
  const H_DIMS = {1.5:[2.5,1.75,1.5,4.625],2:[3,1.75,1.5,4.625],2.5:[3.5,1.75,1.5,4.75],3.25:[4.5,2,1.75,5.5],4:[5,2,1.75,5.75],5:[6.5,2,1.75,6.25],6:[7.5,2.25,2.25,7.375],7:[8.5,2.75,2.75,8.5],8:[9.5,3,3,9.5],10:[12.625,3.688,3.688,12.125],12:[14.875,4.438,4.438,14.5],14:[17.125,4.875,4.875,15.625],16:[19.25,5.875,5.875,18.125],18:[22,6.875,6.875,21.125],20:[23.625,7.875,7.875,23.625]};
  const A_DIMS = {1.5:[2,1.5,1,3.625],2:[2.5,1.5,1,3.625],2.5:[3,1.5,1,3.75],3.25:[3.75,1.75,1.25,4.25],4:[4.5,1.75,1.25,4.25],5:[5.5,1.75,1.25,4.5],6:[6.5,2,1.5,5],7:[7.5,2,1.5,5.125],8:[8.5,2,1.5,5.125],10:[10.625,2.25,2,6.375],12:[12.75,2.25,2,6.875],14:[14.75,2.75,2.25,8.125]};
  const ROD_DIMS = {0.625:[0.75,1],1:[1.125,1.375],1.375:[1.625,1.625],1.75:[2,1.875],2:[2.25,2],2.5:[3,2.25],3:[3.5,2.25],3.5:[3.5,2.25],4:[4,2.25],4.5:[4.5,2.25],5:[5,2.25],5.5:[5.5,2.25],7:[7,3.5],8:[8,4.25],10:[10,4.5]};
  const H_WEIGHT = {'1.5|0.625':[9,.5],'1.5|1':[9.3,.6],'2|1':[13.2,.8],'2|1.375':[17.1,1],'2.5|1':[19.5,1.1],'2.5|1.375':[19.5,1.1],'2.5|1.75':[25.5,1.5],'3.25|1.375':[41,1.8],'3.25|1.75':[41,1.8],'3.25|2':[46,2.2],'4|1.75':[53,2.5],'4|2':[53,2.5],'4|2.5':[58,3.2],'5|2':[82,3.4],'5|2.5':[82,3.4],'5|3':[86,5.2],'5|3.5':[86,5.2],'6|2.5':[133,5.2],'6|3':[133,5.2],'6|3.5':[140,7.3],'6|4':[140,7.3],'7|3':[242,6.7],'7|3.5':[242,6.7],'7|4':[253,10.3],'7|4.5':[253,10.3],'7|5':[253,10.3],'8|3.5':[276,9],'8|4':[276,9],'8|4.5':[309,13],'8|5':[309,13],'8|5.5':[309,13]};
  const H_THREADS = {0.625:['7/16-20','1/2-20'],1:['3/4-16','7/8-14'],1.375:['1-14','1 1/4-12'],1.75:['1 1/4-12','1 1/2-12'],2:['1 1/2-12','1 3/4-12'],2.5:['1 7/8-12','2 1/4-12'],3:['2 1/4-12','2 3/4-12'],3.5:['2 1/2-12','3 1/4-12'],4:['3-12','3 3/4-12'],4.5:['3 1/4-12','4 1/4-12'],5:['3 1/2-12','4 3/4-12'],5.5:['4-12','5 1/4-12'],7:['5 1/2-12','6 1/2-12'],8:['5 3/4-12','7 1/2-12'],10:['7 1/4-12','9 1/2-12']};
  const ROD_SUFFIX = {0.625:'06',1:'10',1.375:'13',1.75:'17',2:'20',2.5:'25',3:'30',3.5:'35',4:'40',4.5:'45',5:'50',5.5:'55',7:'70',8:'80',10:'100'};
  const BORE_SUFFIX = {1.5:'15',2:'20',2.5:'25',3.25:'32',4:'40',5:'50',6:'60',7:'70',8:'80',10:'100',12:'120',14:'140',16:'160',18:'180',20:'200'};
  const ROD_LF_PRICE = {'06':51,'10':55,'13':76,'17':76,'20':88,'25':101,'30':142,'35':163,'40':204,'45':242,'50':303,'55':454,'70':908,'80':1362,'100':1967};
  const GLAND_LF_PRICE = {'06':221,'10':287,'13':378,'17':468,'20':573,'25':646,'30':930,'35':1021,'40':1199,'45':1749,'50':2330,'55':2779,'70':4003,'80':5294,'100':6587};
  const PISTON_LF_PRICE = {'15':62,'20':75,'25':88,'32':120,'40':144,'50':233,'60':358,'70':484,'80':554,'100':892,'120':1162,'140':1425,'160':1750,'180':2000,'200':2750};
  const ROD_POLY_PRICE = {'06':47,'10':50,'13':69,'17':69,'20':80,'25':92,'30':129,'35':148,'40':185,'45':220,'50':275,'55':413,'70':825,'80':1238,'100':1788};
  const GLAND_POLY_PRICE = {'06':158,'10':205,'13':270,'17':334,'20':409,'25':462,'30':664,'35':729,'40':857,'45':1249,'50':1664,'55':1985,'70':2859,'80':3782,'100':4705};
  const PISTON_POLY_PRICE = {'15':62,'20':75,'25':88,'32':120,'40':144,'50':233,'60':358,'70':484,'80':554,'100':892,'120':1162,'140':1425,'160':1750,'180':2000,'200':2750};
  const dim = (series === 'H' || series === 'HM' || series === 'MH') ? H_DIMS[bore] : A_DIMS[bore];
  const rodDim = ROD_DIMS[rod];
  const putInput = (id, value) => { const el=$(id); if(el) el.value=value; };
  $('pv_series_desc').textContent = SERIES_LABELS[series] || (series ? `${series} Series Cylinder` : 'Cylinder');
  $('pv_model_code').textContent = quote.model_code || '—';
  $('pv_mount').textContent = inputs.mount ? `${MOUNT_LABELS[String(inputs.mount).toUpperCase()] || String(inputs.mount)} (${String(inputs.mount).toUpperCase()})` : '—';
  $('pv_bore').textContent = inputs.bore || '—';
  $('pv_stroke').textContent = inputs.stroke || '—';
  $('pv_rod_diameter').textContent = inputs.rod_diameter || '—';
  const threadPair = H_THREADS[rod];
  const threadIndex = Number(inputs.rod_style) === 2 ? 1 : 0;
  const threadGender = Number(inputs.rod_style) === 3 ? 'Female' : 'Male';
  $('pv_rod_style').textContent = threadPair ? `${threadGender} ${threadPair[threadIndex]}` : (inputs.rod_style || '—');
  $('pv_cushion').textContent = labelFor(CUSHION_LABELS, inputs.cushion);
  $('pv_port_code').textContent = inputs.port_code || '—';
  $('pv_seal_code').textContent = labelFor(SEAL_LABELS, inputs.seal_code);
  $('pv_discount').textContent = (Number(quote.discount || 0) * 100).toFixed(1) + '%';
  $('pv_quantity').value = Math.max(1, Math.floor(Number(quote.quantity || 1)));

  const manualDescriptions = (quote.manual_line_items || []).map(x => x.description).filter(Boolean);
  const selectedSpecialParts = Object.entries(inputs.special_parts || {}).map(([part, qty]) => `${part} (Qty ${qty})`);
  const includesList = [...manualDescriptions, ...selectedSpecialParts];
  $('pv_includes').textContent = includesList.length ? includesList.join(', ') : '—';

  const pressure = ['H','HM','MH','IH','IMH','IHM'].includes(series) ? 3000 : (series === 'LH' ? 1500 : 100);
  const forces = computePushPull(pressure, inputs.bore, inputs.rod_diameter, ['IH','IMH','IHM'].includes(series));
  $('pv_pressure_push').textContent = pressure || '0';
  $('pv_pressure_pull').textContent = pressure || '0';
  $('pv_push_lbs').textContent = `${forces.push.toLocaleString('en-US')} lbs`;
  $('pv_pull_lbs').textContent = `${forces.pull.toLocaleString('en-US')} lbs`;

  if (dim) {
    putInput('pv_dim_e', `${dim[0]}"`); putInput('pv_dim_g', `${dim[1]}"`); putInput('pv_dim_j', `${dim[2]}"`);
    putInput('pv_dim_lb', `${Math.round((dim[3] + stroke) * 1000) / 1000}"`);
  } else { ['pv_dim_e','pv_dim_g','pv_dim_j','pv_dim_lb'].forEach(id => putInput(id, '—')); }
  putInput('pv_dim_a', rodDim ? `${Math.round((rodDim[0] + Number(inputs.extra_thread || 0)) * 1000) / 1000}" Male/Female` : '—');
  putInput('pv_dim_wf', rodDim ? `${Math.round((rodDim[1] + Number(inputs.rod_extension || 0)) * 1000) / 1000}"` : '—');
  putInput('pv_dim_extra_1', '0'); putInput('pv_dim_extra_2', '0');

  const weightRule = H_WEIGHT[`${bore}|${rod}`];
  putInput('pv_weight', weightRule ? `${Math.round((weightRule[0] + weightRule[1] * stroke) * 10) / 10}` : 'N/A');
  const rodSuffix = ROD_SUFFIX[rod], boreSuffix = BORE_SUFFIX[bore], discountFactor = 1 - Number(quote.discount || 0);
  const sealCode = String(inputs.seal_code || '').toUpperCase();
  const polySeal = sealCode === 'P';
  const lowFrictionSeal = sealCode === 'L';
  const rodPrices = polySeal ? ROD_POLY_PRICE : (lowFrictionSeal ? ROD_LF_PRICE : null);
  const glandPrices = polySeal ? GLAND_POLY_PRICE : (lowFrictionSeal ? GLAND_LF_PRICE : null);
  const pistonPrices = polySeal ? PISTON_POLY_PRICE : (lowFrictionSeal ? PISTON_LF_PRICE : null);
  const rodPartPrefix = polySeal ? 'KHR' : 'KHRL';
  const glandPartPrefix = polySeal ? 'KHG' : 'KHGL';
  const pistonPartPrefix = polySeal ? 'KHP' : 'KHPL';
  const putText = (id, value) => { const el=$(id); if(el) el.textContent=value; };
  putText('pv_repair_rod_label', rodSuffix && rodPrices ? `Hyd Rod ${polySeal ? 'Poly' : 'Low Friction'} Seal Kit ${rodPartPrefix}${rodSuffix}` : 'Hyd Rod Seal Kit');
  putText('pv_repair_piston_label', boreSuffix && pistonPrices ? `Hyd Piston ${polySeal ? 'Poly' : 'Low Friction'} Seal Kit ${pistonPartPrefix}${boreSuffix}` : 'Hyd Piston Seal Kit');
  putText('pv_repair_gland_label', rodSuffix && glandPrices ? `Hyd Gland ${polySeal ? 'Poly' : 'Low Friction'} Seal Kit ${glandPartPrefix}${rodSuffix}` : 'Hyd Gland Seal Kit');
  putInput('pv_repair_rod_kit', rodSuffix && rodPrices ? fmtRoundedMoney(rodPrices[rodSuffix] * discountFactor) : 'N/A');
  putInput('pv_repair_gland_kit', rodSuffix && glandPrices ? fmtRoundedMoney(glandPrices[rodSuffix] * discountFactor) : 'N/A');
  putInput('pv_repair_piston_kit', boreSuffix && pistonPrices ? fmtRoundedMoney(pistonPrices[boreSuffix] * discountFactor) : 'N/A');
  const assemblyRule = ['H','HM'].includes(series) ? H_ASSEMBLY_PRICE[`${bore}|${rod}`] : null;
  const assemblyLength = stroke + Number(inputs.rod_extension || 0) + Number(inputs.extra_thread || 0);
  const assemblyBase = assemblyRule ? (String(inputs.cushion || '').toUpperCase() === 'NC' ? assemblyRule[0] : assemblyRule[1]) : 0;
  const assemblyPrice = assemblyRule ? excelRoundUpPositive((assemblyBase + assemblyRule[2] * assemblyLength) * discountFactor) : null;
  putInput('pv_repair_assembly', assemblyPrice === null ? 'N/A' : fmtRoundedMoney(assemblyPrice));

  const bd = quote.price_breakdown_snapshot || {};
  const standardNet = Number(bd.quote_net_each || 0);
  const days = Number($('pv_days').value || 30);
  function updateCylinderQuantityPrices() {
    const quantityInput = $('pv_quantity');
    let quantity = Math.floor(Number(quantityInput.value));
    if (!Number.isFinite(quantity) || quantity < 1) quantity = 1;
    quantityInput.value = String(quantity);
    $('pv_quote_list_price').textContent = fmtRoundedMoney(Number(bd.quote_list_price || 0) * quantity);
    $('pv_quote_net_each').textContent = fmtRoundedMoney(standardNet * quantity);
    $('pv_expedited_price').textContent = fmtRoundedMoney(standardNet * 1.35 * quantity);
    $('pv_emergency_price').textContent = fmtRoundedMoney(standardNet * 1.95 * quantity);
    $('pv_cares_price').textContent = fmtRoundedMoney(standardNet * 1.05 * quantity);
  }
  $('pv_quantity').oninput = updateCylinderQuantityPrices;
  $('pv_quantity').onchange = updateCylinderQuantityPrices;
  updateCylinderQuantityPrices();
  $('pv_net_days').textContent = days || 30;
  $('pv_expedited_days').textContent = Math.max(1, Math.round((days || 30) / 2));
  $('pv_cares_days').textContent = days || 30;
  renderManualItems(quote.manual_line_items || []);
  $('previewErrorMessage').textContent = '';
  showView('quotePreviewView');
}

function renderManualItems(items) {
  const host = $('previewManualItems');
  host.innerHTML = '';
  if (!items.length) { addManualItemRow(); return; }
  items.forEach(item => addManualItemRow(item));
}

function addManualItemRow(item) {
  item = item || { reference_part_number: '', description: '', quantity: 1, unit_price: 0, show_on_customer_quote: true, internal_note: '' };
  const host = $('previewManualItems');
  const row = document.createElement('div'); row.className = 'manual-row';
  const ref = document.createElement('input'); ref.type = 'text'; ref.value = item.reference_part_number || ''; ref.placeholder = 'Part #'; ref.className = 'manual-ref';
  const desc = document.createElement('input'); desc.type = 'text'; desc.value = item.description || ''; desc.placeholder = 'Description'; desc.className = 'manual-desc';
  const qty = document.createElement('input'); qty.type = 'number'; qty.min = '0'; qty.step = '1'; qty.value = item.quantity || 0; qty.className = 'manual-qty';
  const unit = document.createElement('input'); unit.type = 'number'; unit.min = '0'; unit.step = '0.01'; unit.value = item.unit_price || 0; unit.className = 'manual-unit';
  const ext = document.createElement('input'); ext.type = 'text'; ext.readOnly = true; ext.value = fmtMoney((Number(item.quantity || 0) * Number(item.unit_price || 0))); ext.className = 'manual-ext';
  const show = document.createElement('input'); show.type = 'checkbox'; show.checked = item.show_on_customer_quote !== false; show.className = 'manual-show';
  const note = document.createElement('input'); note.type = 'text'; note.value = item.internal_note || ''; note.placeholder = 'Internal note'; note.className = 'manual-note';
  const rm = document.createElement('button'); rm.type = 'button'; rm.textContent = '×'; rm.className = 'manual-remove'; rm.title = 'Remove line';
  function updateExt() { const q = Number(qty.value || 0), u = Number(unit.value || 0); ext.value = fmtMoney(q * u); }
  qty.addEventListener('input', updateExt); unit.addEventListener('input', updateExt);
  rm.addEventListener('click', () => { row.remove(); if (!host.children.length) addManualItemRow(); });
  row.append(ref, desc, qty, unit, ext, show, note, rm); host.appendChild(row);
}

function manualItemsFromPreview() {
  const out = [];
  document.querySelectorAll('#previewManualItems .manual-row').forEach(row => {
    const desc = row.querySelector('.manual-desc').value.trim();
    if (!desc) return;
    out.push({
      reference_part_number: row.querySelector('.manual-ref').value.trim() || null,
      description: desc,
      quantity: Number(row.querySelector('.manual-qty').value || 0),
      unit_price: Number(row.querySelector('.manual-unit').value || 0),
      show_on_customer_quote: row.querySelector('.manual-show').checked,
      internal_note: row.querySelector('.manual-note').value.trim() || null
    });
  });
  return out;
}

async function saveQuote() {
  if (!currentQuote || !pendingQuotePayload) return;

  $('previewErrorMessage').textContent = '';
  $('saveQuoteButton').disabled = true;
  $('saveQuoteButton').textContent = 'Submitting...';

  try {
    const savePayload = {
      ...pendingQuotePayload,
      customer_name: $('pv_customer_name').value,
      customer_address: $('pv_customer_address').value,
      customer_contact: $('pv_customer_contact').value,
      reference_notes: $('pv_reference_notes').value,
      comments: $('pv_comments').value,
      special_instructions: $('pv_special_instructions').value,
      quantity: Math.max(1, Math.floor(Number($('pv_quantity').value || 1))),
      manual_line_items: manualItemsFromPreview()
    };

    const existingQuoteId = new URLSearchParams(window.location.search).get('quote_id') || (currentQuote && currentQuote.id);
    const res = await fetch(existingQuoteId ? `/api/quotes/${existingQuoteId}` : '/api/quotes', {
      method: existingQuoteId ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(savePayload)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) throw new Error(body.error || 'Database save failed');

    currentQuote = body.quote;
    const orderResponse = await fetch(`/api/quotes/${body.quote.id}/order`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
    });
    const orderBody = await orderResponse.json();
    if (!orderResponse.ok || !orderBody.ok) throw new Error(orderBody.error || 'Order approval request failed');
    currentQuote = orderBody.quote;
    if (PORTAL_MODE === 'customer') {
      window.location.assign('/customer/history');
      return;
    }
    window.location.assign(orderBody.approval_url);
    return;
  } catch (e) {
    $('previewErrorMessage').textContent = e.message || 'Database save failed';
  } finally {
    $('saveQuoteButton').disabled = false;
    $('saveQuoteButton').textContent = 'Order Now';
  }
}

async function employeeSaveQuote() {
  if (!currentQuote || !pendingQuotePayload) return;

  const button = $('employeeSaveButton');
  if (!button) return;

  $('previewErrorMessage').textContent = '';
  button.disabled = true;
  button.textContent = 'Saving...';

  try {
    const savePayload = {
      ...pendingQuotePayload,
      customer_name: $('pv_customer_name').value,
      customer_address: $('pv_customer_address').value,
      customer_contact: $('pv_customer_contact').value,
      reference_notes: $('pv_reference_notes').value,
      comments: $('pv_comments').value,
      special_instructions: $('pv_special_instructions').value,
      quantity: Math.max(1, Math.floor(Number($('pv_quantity').value || 1))),
      manual_line_items: manualItemsFromPreview()
    };

    const existingQuoteId = new URLSearchParams(window.location.search).get('quote_id') || (currentQuote && currentQuote.id);
    const res = await fetch(existingQuoteId ? `/api/quotes/${existingQuoteId}` : '/api/quotes', {
      method: existingQuoteId ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(savePayload)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) throw new Error(body.error || 'Database save failed');

    currentQuote = body.quote;
    window.JIT_EDIT_QUANTITY = body.quote.quantity || 1;
    renderQuotePreview(body.quote);
    $('previewErrorMessage').textContent = `Quote ${body.quote.quote_number} saved.`;
  } catch (e) {
    $('previewErrorMessage').textContent = e.message || 'Database save failed';
  } finally {
    button.disabled = false;
    button.textContent = 'Save';
  }
}

async function verifyQuote() {
  if (!currentQuote) return;

  const button = $('verifyQuoteButton');
  const messageEl = $('verifyMessage');
  if (!button || !messageEl) return;

  messageEl.textContent = '';
  messageEl.classList.remove('verify-ok', 'verify-mismatch');
  button.disabled = true;
  button.textContent = 'Verifying...';

  try {
    const inputsSnapshot = currentQuote.cylinder_inputs_snapshot || {};
    const displayed = currentQuote.price_breakdown_snapshot || {};

    const res = await fetch('/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(inputsSnapshot)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) throw new Error(body.error || 'Verification failed');

    const fresh = body.result;
    const fieldsToCheck = [
      'base_price', 'stroke_cushion', 'modifications', 'accessories', 'special_parts',
      'position_sensing', 'va_total', 'dre_surcharge', 'pre_discount_subtotal',
      'discount_amount', 'working_net_each', 'list_price', 'quote_list_price',
      'quote_net_each', 'expedited_price', 'emergency_price'
    ];

    const mismatches = [];
    if ((fresh.model_code || '') !== (displayed.model_code || '')) {
      mismatches.push(`Model Code: shown ${displayed.model_code || '—'}, recalculated ${fresh.model_code || '—'}`);
    }
    fieldsToCheck.forEach(field => {
      const shown = Number(displayed[field] || 0);
      const recalculated = Number(fresh[field] || 0);
      if (Math.abs(shown - recalculated) > 0.005) {
        mismatches.push(`${field}: shown ${fmtMoney(shown)}, recalculated ${fmtMoney(recalculated)}`);
      }
    });

    if (mismatches.length) {
      messageEl.textContent = 'Mismatch found — ' + mismatches.join('; ');
      messageEl.classList.add('verify-mismatch');
    } else {
      messageEl.textContent = 'Verified: all prices match Pricing Engine v1.2.';
      messageEl.classList.add('verify-ok');
    }
  } catch (e) {
    messageEl.textContent = e.message || 'Verification failed';
    messageEl.classList.add('verify-mismatch');
  } finally {
    button.disabled = false;
    button.textContent = 'Verify';
  }
}

$('saveQuoteButton').addEventListener('click', saveQuote);
const employeeSaveButton = $('employeeSaveButton');
if (employeeSaveButton) employeeSaveButton.addEventListener('click', employeeSaveQuote);
const verifyQuoteButton = $('verifyQuoteButton');
if (verifyQuoteButton) verifyQuoteButton.addEventListener('click', verifyQuote);
$('addManualItemButton').addEventListener('click', () => addManualItemRow());
$('backToOrderEntryButton').addEventListener('click', showOrderEntry);
$('newQuoteButton').addEventListener('click', () => {
  pendingQuotePayload = null;
  showOrderEntry();
});



let quoteZoomLevel = 1;
const QUOTE_ZOOM_MIN = 0.5;
const QUOTE_ZOOM_MAX = 2;
const QUOTE_ZOOM_STEP = 0.1;

function applyQuoteZoom() {
  const preview = $('quotePreviewView');
  const sheet = document.querySelector('.excel-quote-sheet');
  const level = $('quoteZoomLevel');
  if (!preview || !sheet) return;

  const edge = 14;
  const worksheetWidth = 816;
  const availableWidth = Math.max(1, preview.clientWidth - edge * 2);
  const widthFitScale = availableWidth / worksheetWidth;
  const effectiveScale = widthFitScale * quoteZoomLevel;
  sheet.style.width = `${worksheetWidth}px`;
  sheet.style.zoom = String(effectiveScale);
  if (level) level.textContent = `${Math.round(quoteZoomLevel * 100)}%`;
}

function changeQuoteZoom(direction) {
  const next = quoteZoomLevel + direction * QUOTE_ZOOM_STEP;
  quoteZoomLevel = Math.min(QUOTE_ZOOM_MAX, Math.max(QUOTE_ZOOM_MIN, Math.round(next * 10) / 10));
  applyQuoteZoom();
}

const quoteZoomOutButton = $('quoteZoomOutButton');
const quoteZoomInButton = $('quoteZoomInButton');
if (quoteZoomOutButton) quoteZoomOutButton.addEventListener('click', () => changeQuoteZoom(-1));
if (quoteZoomInButton) quoteZoomInButton.addEventListener('click', () => changeQuoteZoom(1));

/* OrderEntry Replica v1.2 proportional scaling */
function scaleOrderEntryToViewport() {
  const win = document.querySelector('.orderentry-window');
  const preview = $('quotePreviewView');
  if (!win) return;

  const previewIsOpen = preview && !preview.classList.contains('hidden');
  if (previewIsOpen) {
    // Quote Form fills the available width and grows downward. The preview
    // scrolls vertically instead of shrinking the entire sheet to screen height.
    win.classList.add('preview-mode');
    win.style.transform = 'none';
    win.style.left = '0px';
    win.style.top = '0px';
    win.style.width = '100%';
    applyQuoteZoom();
    return;
  }

  win.classList.remove('preview-mode');
  win.style.width = '';
  const sheet = document.querySelector('.excel-quote-sheet');
  if (sheet) { sheet.style.zoom = ''; sheet.style.width = ''; }

  // Order Entry keeps its fixed design proportions and scales uniformly.
  const designWidth = win.offsetWidth;
  const designHeight = win.offsetHeight;
  if (!designWidth || !designHeight) return;

  const edge = 10;
  const availableWidth = Math.max(1, window.innerWidth - edge * 2);
  const availableHeight = Math.max(1, window.innerHeight - edge * 2);
  const scale = Math.min(availableWidth / designWidth, availableHeight / designHeight);
  const renderedWidth = designWidth * scale;
  const renderedHeight = designHeight * scale;

  win.style.transform = `scale(${scale})`;
  win.style.left = `${Math.max(edge, (window.innerWidth - renderedWidth) / 2)}px`;
  win.style.top = `${Math.max(edge, (window.innerHeight - renderedHeight) / 2)}px`;
}

let orderEntryScaleFrame = 0;
function queueOrderEntryScale() {
  cancelAnimationFrame(orderEntryScaleFrame);
  orderEntryScaleFrame = requestAnimationFrame(scaleOrderEntryToViewport);
}

window.addEventListener('resize', queueOrderEntryScale);
window.addEventListener('load', queueOrderEntryScale);

const orderEntryWindow = document.querySelector('.orderentry-window');
if (orderEntryWindow && 'ResizeObserver' in window) {
  new ResizeObserver(queueOrderEntryScale).observe(orderEntryWindow);
}
queueOrderEntryScale();
