let catalog = null;
let currentQuote = null;
const $ = id => document.getElementById(id);

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
function boolFromYN(id) { return String($(id).value || '').toUpperCase() === 'Y'; }
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
function buildSpecialRows() {
  const host = $('specialParts');
  host.innerHTML = '';
  for (let i=0;i<6;i++) {
    const row=document.createElement('div'); row.className='part-row special-row';
    const sel=document.createElement('select'); sel.className='special-part-name';
    const blank=document.createElement('option'); blank.value=''; blank.textContent=''; sel.appendChild(blank);
    catalog.special_parts.forEach(p=>{const o=document.createElement('option');o.value=p;o.textContent=p;sel.appendChild(o);});
    const desc=document.createElement('input'); desc.className='special-part-description'; desc.readOnly=true;
    const qty=document.createElement('input'); qty.type='number';qty.min='0';qty.step='1';qty.value='';qty.className='special-part-qty';
    const price=document.createElement('input'); price.className='special-part-price'; price.readOnly=true;
    sel.addEventListener('change',()=>{
      const detail=(catalog.special_part_details||{})[sel.value]||{};
      desc.value=detail.description||'';
      price.value=detail.price ? fmtMoney(detail.price) : '';
    });
    row.append(sel,desc,qty,price); host.appendChild(row);
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
  $('customer_name').value = '';
  $('customer_address').value = '';
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
  p.customer_contact = '';
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
  $('display_discount').textContent=(Number($('discount_pct').value||0)).toFixed(2)+'%';
  const box=$('warningsBox'), list=$('warnings'); list.innerHTML='';
  (r.warnings||[]).forEach(w=>{const li=document.createElement('li');li.textContent=w;list.appendChild(li);}); box.hidden=!(r.warnings||[]).length;
  const dlg=$('quoteResultDialog'); if (dlg.showModal) dlg.showModal();
}
async function init() {
  wireTabs();
  try {
    const res=await fetch('/api/catalog'); if(!res.ok) throw new Error('Catalog request failed'); catalog=await res.json();
    fillSelect($('series'),Object.keys(catalog.series),x=>x,true);
    fillSelect($('cushion'),catalog.cushions,x=>x,true); fillSelect($('port_code'),catalog.port_codes,x=>x||'',true); fillSelect($('seal_code'),catalog.seal_codes,x=>x||'',true); fillSelect($('rod_style'),catalog.rod_styles,x=>x,true);
    $('series').addEventListener('change',()=>{updateMountsForSeries();updateBores();}); $('bore').addEventListener('change',updateRods);
    $('dre_input').addEventListener('input',()=>{$('dre_input').value=$('dre_input').value.toUpperCase().replace(/[^Y]/g,'').slice(0,1);});
    updateMountsForSeries(); updateBores(); buildSpecialRows(); buildOrderEntryManualItems(); resetQuoteForm(); $('engineStatus').textContent='Catalog loaded';
  } catch(e) { $('engineStatus').textContent='Catalog unavailable'; $('errorMessage').textContent=e.message; }
}
$('addOrderEntryManualItemButton').addEventListener('click', () => addOrderEntryManualItemRow());
let pendingQuotePayload = null;

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
    const quoteLike = {
      id: null,
      quote_number: 'Not saved yet',
      revision: 1,
      status: 'Unsaved',
      pricing_version: d.pricing_engine_version || 'Pricing Engine v1.2',
      created_by: '',
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

/* JIT DEFAULTS: SERIES H / MOUNT MF1 */
async function applyJitDefaultSeriesMount() {
  const series = $('series');
  const mount = $('mount');
  if (!series || !mount) return;

  series.value = 'H';
  series.dispatchEvent(new Event('change', { bubbles: true }));

  // Allow dependent catalog options to refresh before selecting MF1.
  await new Promise(resolve => setTimeout(resolve, 150));

  mount.value = 'MF1';
  mount.dispatchEvent(new Event('change', { bubbles: true }));
}

Promise.resolve(init()).then(() => applyJitDefaultSeriesMount());

/* Quote Preview view support */
function showView(viewId) {
  document.querySelectorAll('.view').forEach(v => { v.classList.remove('active'); v.classList.add('hidden'); });
  const view = $(viewId);
  if (view) { view.classList.remove('hidden'); view.classList.add('active'); }
  queueOrderEntryScale();
}
function showOrderEntry() { currentQuote = null; resetQuoteForm(); showView('orderEntryView'); 
  setTimeout(() => applyJitDefaultSeriesMount(), 0);}
function formatDateTime(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleString(); } catch { return iso; } }

function renderQuotePreview(quote) {
  currentQuote = quote;
  $('pv_quote_number').textContent = quote.quote_number || '—';
  $('pv_revision').textContent = quote.revision || '1';
  $('pv_status').textContent = quote.status || '—';
  $('pv_pricing_version').textContent = quote.pricing_version || '—';
  $('pv_created_by').textContent = quote.created_by || '—';
  $('pv_created_at').textContent = formatDateTime(quote.created_at);
  $('pv_customer_name').value = quote.customer_name || '';
  $('pv_customer_address').value = quote.customer_address || '';
  $('pv_customer_contact').value = quote.customer_contact || '';
  $('pv_reference_notes').value = quote.reference_notes || '';
  $('pv_comments').value = quote.comments || '';

  const inputs = quote.cylinder_inputs_snapshot || {};
  $('pv_model_code').textContent = quote.model_code || '—';
  $('pv_series').textContent = inputs.series || '—';
  $('pv_mount').textContent = inputs.mount || '—';
  $('pv_bore').textContent = inputs.bore || '—';
  $('pv_stroke').textContent = inputs.stroke || '—';
  $('pv_rod_diameter').textContent = inputs.rod_diameter || '—';
  $('pv_rod_style').textContent = inputs.rod_style || '—';
  $('pv_cushion').textContent = inputs.cushion || '—';
  $('pv_port_code').textContent = inputs.port_code || '—';
  $('pv_seal_code').textContent = inputs.seal_code || '—';
  $('pv_dre').textContent = inputs.dre ? 'Y' : 'N';
  $('pv_discount').textContent = (Number(quote.discount || 0) * 100).toFixed(2) + '%';

  const bd = quote.price_breakdown_snapshot || {};
  ['quote_list_price','quote_net_each','expedited_price','emergency_price','base_price','stroke_cushion','modifications','accessories','special_parts','position_sensing','va_total','dre_surcharge','pre_discount_subtotal'].forEach(k => {
    const el = $('pv_' + k); if (el) el.textContent = fmtMoney(bd[k]);
  });
  renderManualItems(quote.manual_line_items || []);
  $('previewErrorMessage').textContent = '';
  if ($('approvalStatus')) $('approvalStatus').className = 'approval-status';
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
  $('saveQuoteButton').textContent = 'Saving...';

  try {
    const savePayload = {
      ...pendingQuotePayload,
      customer_name: $('pv_customer_name').value,
      customer_address: $('pv_customer_address').value,
      customer_contact: $('pv_customer_contact').value,
      reference_notes: $('pv_reference_notes').value,
      comments: $('pv_comments').value,
      manual_line_items: manualItemsFromPreview()
    };

    const res = await fetch('/api/quotes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(savePayload)
    });
    const body = await res.json();
    if (!res.ok || !body.ok) throw new Error(body.error || 'Database save failed');

    currentQuote = body.quote;
    renderQuotePreview(body.quote);
    $('previewErrorMessage').textContent =
      `Saved to database as ${body.quote.quote_number}.`;
  } catch (e) {
    $('previewErrorMessage').textContent = e.message || 'Database save failed';
  } finally {
    $('saveQuoteButton').disabled = false;
    $('saveQuoteButton').textContent = 'Save to Database';
  }
}

$('saveQuoteButton').addEventListener('click', saveQuote);
$('addManualItemButton').addEventListener('click', () => addManualItemRow());
$('backToOrderEntryButton').addEventListener('click', showOrderEntry);
$('newQuoteButton').addEventListener('click', () => {
  pendingQuotePayload = null;
  showOrderEntry();
});


/* OrderEntry Replica v1.2 proportional scaling */
function scaleOrderEntryToViewport() {
  const win = document.querySelector('.orderentry-window');
  if (!win) return;

  // offsetWidth/offsetHeight are the unscaled design dimensions.
  const designWidth = win.offsetWidth;
  const designHeight = win.offsetHeight;
  if (!designWidth || !designHeight) return;

  const edge = 10;
  const availableWidth = Math.max(1, window.innerWidth - edge * 2);
  const availableHeight = Math.max(1, window.innerHeight - edge * 2);
  const scale = Math.min(availableWidth / designWidth, availableHeight / designHeight);

  const renderedWidth = designWidth * scale;
  const renderedHeight = designHeight * scale;
  const left = Math.max(edge, (window.innerWidth - renderedWidth) / 2);
  const top = Math.max(edge, (window.innerHeight - renderedHeight) / 2);

  win.style.transform = `scale(${scale})`;
  win.style.left = `${left}px`;
  win.style.top = `${top}px`;
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
