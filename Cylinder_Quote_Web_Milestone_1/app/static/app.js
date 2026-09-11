let catalog = null;
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
  for (let i=0;i<6;i++) {
    const row=document.createElement('div'); row.className='part-row special-row';
    const inp=document.createElement('select'); inp.className='special-part-name';
    const blank=document.createElement('option'); blank.value=''; blank.textContent=''; inp.appendChild(blank);
    catalog.special_parts.forEach(part => {
      const option=document.createElement('option'); option.value=part; option.textContent=part; inp.appendChild(option);
    });
    const desc=document.createElement('input'); desc.className='special-part-description'; desc.readOnly=true;
    const qty=document.createElement('input'); qty.type='number';qty.min='0';qty.step='1';qty.value='';qty.className='special-part-qty';
    const price=document.createElement('input'); price.className='special-part-price'; price.readOnly=true;
    inp.addEventListener('change',()=>{
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

    // Opening a saved quote (?quote_id=) is now handled by the dedicated Quote Form
    // page/route, so this calculator only ever loads blank or with a promo prefill.

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

$('quoteForm').addEventListener('submit', async e => {
  e.preventDefault();
  $('errorMessage').textContent = '';
  $('calculateButton').disabled = true;
  $('calculateButton').textContent = 'Opening...';
  try {
    const payload = draftPayload();
    const res = await fetch('/api/quote/draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) throw new Error(body.error || 'Quote draft failed');

    if (PORTAL_MODE === 'customer') {
      sessionStorage.setItem('jitQuoteDraft', JSON.stringify(payload));
      window.location.assign('/customer/quote-form?draft=1');
      return;
    }

    // Preserve the authoritative server draft for the employee Quote Form.
    sessionStorage.setItem('jitQuoteDraft', JSON.stringify({
      payload,
      draft: body.draft
    }));
    window.location.assign(`/${PORTAL_MODE}/quote-entry?draft=1`);
    return;
  } catch (e) {
    $('errorMessage').textContent = e.message;
  } finally {
    $('calculateButton').disabled = false;
    $('calculateButton').textContent = 'Quote';
  }
});

window.jitCalculatorReady = init();

/* OrderEntry Replica v1.2 proportional scaling */
function scaleOrderEntryToViewport() {
  const win = document.querySelector('.orderentry-window');
  if (!win) return;

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
