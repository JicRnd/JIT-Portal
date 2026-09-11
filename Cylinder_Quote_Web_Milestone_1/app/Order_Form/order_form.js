(() => {
  const page = document.querySelector('.order-page');
  const quoteId = Number(page.dataset.quoteId || 0);
  const form = document.getElementById('employeeOrderForm');
  const statusEl = document.getElementById('orderStatus');
  const messageEl = document.getElementById('orderMessage');
  const approveButton = document.getElementById('approveOrderButton');
  const denyButton = document.getElementById('denyOrderButton');
  const holdButton = document.getElementById('holdOrderButton');
  const dashboardButton = document.getElementById('employeeDashboardButton');
  const emailCustomerButton = document.getElementById('emailCustomerButton');
  const partsHost = document.getElementById('orderPartsRows');
  const testingHost = document.getElementById('testingRows');
  const addPartButton = document.getElementById('addPartButton');
  const addPartModal = document.getElementById('addPartModal');
  const addPartSearchInput = document.getElementById('addPartSearchInput');
  const addPartResults = document.getElementById('addPartResults');
  const closeAddPartModal = document.getElementById('closeAddPartModal');
  let loadedQuote = null;

  const money = n => Number(n || 0).toFixed(2);
  const localDate = iso => {
    const d = iso ? new Date(iso) : new Date();
    return Number.isNaN(d.getTime()) ? String(iso || '') : d.toLocaleString('en-US');
  };
  const value = (obj, key, fallback = '') => obj && obj[key] != null ? obj[key] : fallback;
  const emailFromText = text => {
    const match = String(text || '').match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
    return match ? match[0] : '';
  };
  const MOUNT_LABELS = {
    MF1:'Rect Head Flange', MF2:'Rect Cap Flange', MF5:'Square Head Flange', MF6:'Square Cap Flange',
    MP1:'Fixed Cap Clevis', MP2:'Detachable Cap Clevis', MP3:'Pivot Eye', MPU3:'Self Aligning Eye',
    MS1:'Angle Foot', MS2:'Side Lugs', MS3:'Centerline Lug', MS4:'Side Tapped', MS7:'Foot Lug',
    MT1:'Head Trunnion', MT2:'Cap Trunnion', MT4:'Center Trunnion', MX0:'No Mount',
    MX1:'Extended Both Ends', MX2:'Extended Cap End', MX3:'Extended Head End',
    ME3:'Full Head Flange', ME4:'Full Cap Flange'
  };
  const CUSHION_LABELS = {NC:'Non Cushion',RE:'Rod End',CE:'Cap End',BE:'Both Ends',ARE:'Adjustable Rod End',ACE:'Adjustable Cap End',ABE:'Adjustable Both Ends'};
  const PORT_LABELS = {N:'NPT',S:'SAE',F:'Flange Port'};
  const SEAL_LABELS = {P:'Polyurethane',B:'Buna-N',V:'Viton',L:'Low Friction',C:'CIPR',H:'Viton High Load'};
  const ROD_THREADS = {
    '0.625':['7/16-20','1/2-20'], '1':['3/4-16','7/8-14'], '1.375':['1-14','1 1/4-12'],
    '1.75':['1 1/4-12','1 1/2-12'], '2':['1 1/2-12','1 3/4-12'], '2.5':['1 7/8-12','2 1/4-12'],
    '3':['2 1/4-12','2 3/4-12'], '3.5':['2 1/2-12','3 1/4-12'], '4':['3-12','3 3/4-12'],
    '4.5':['3 1/4-12','4 1/4-12'], '5':['3 1/2-12','4 3/4-12'], '5.5':['4-12','5 1/4-12'],
    '7':['5 1/2-12','6 1/2-12'], '8':['5 3/4-12','7 1/2-12'], '10':['7 1/4-12','9 1/2-12'],
    '12':['M10x1.25',''], '14':['M12x1.25',''], '18':['M14x1.5',''], '22':['M16x1.5',''],
    '25':['M20x1.5',''], '28':['M20x1.5',''], '36':['M27x2',''], '45':['M33x2',''],
    '56':['M42x2',''], '70':['M48x2',''], '90':['M64x3',''], '110':['M80x3',''], '140':['M100x3','']
  };
  const describedCode = (map, raw) => map[String(raw || '').toUpperCase()] || String(raw || '');
  function describedMount(raw) {
    const code = String(raw || '').toUpperCase();
    return code && MOUNT_LABELS[code] ? `${MOUNT_LABELS[code]} (${code})` : code;
  }
  function describedRodThread(rod, style) {
    const styleNumber = Number(style || 0);
    if (styleNumber === 4) return 'Safety Coupler';
    if (styleNumber === 5) return 'Special Threads';
    const pair = ROD_THREADS[String(rod || '')];
    const thread = pair && pair[styleNumber === 2 ? 1 : 0];
    if (!thread) return String(style || '');
    return `${styleNumber === 3 ? 'Female' : 'Male'} - ${thread}`;
  }
  const setMessage = (text, isError = false) => {
    messageEl.textContent = text || '';
    messageEl.classList.toggle('error', isError);
  };
  const setStatus = status => {
    statusEl.textContent = String(status || 'pending approval').replaceAll('_', ' ');
    statusEl.classList.toggle('approved', status === 'approved');
    approveButton.disabled = status === 'approved';
    approveButton.textContent = status === 'approved' ? 'Approved' : 'Approve Order';
    denyButton.disabled = status === 'approved' || status === 'denied';
    denyButton.textContent = status === 'denied' ? 'Denied' : 'Deny Order';
    holdButton.disabled = ['approved', 'denied', 'hold'].includes(status);
    holdButton.textContent = status === 'hold' ? 'On Hold' : 'Hold';
  };

  function splitAddress(customer, address) {
    const lines = [customer, ...String(address || '').split(/\r?\n|,/)].map(x => String(x || '').trim()).filter(Boolean);
    while (lines.length < 4) lines.push('');
    return lines.slice(0, 4);
  }

  function addPartRow(item = {}) {
    const row = document.createElement('div');
    row.className = 'part-row';
    ['part_number','description','cost','on_hand','allocated'].forEach(key => {
      const input = document.createElement('input');
      input.dataset.partField = key;
      input.value = value(item, key, key === 'cost' || key === 'on_hand' || key === 'allocated' ? '0' : '');
      if (key === 'cost' || key === 'on_hand' || key === 'allocated') input.inputMode = 'decimal';
      input.setAttribute('aria-label', key.replaceAll('_', ' '));
      row.appendChild(input);
    });
    partsHost.appendChild(row);
    return row;
  }

  function isBlankPartRow(row) {
    return [...row.querySelectorAll('input')].every(input => !Number(input.value) && !String(input.value || '').trim());
  }

  function insertPartAfterLastEntry(item) {
    const rows = [...partsHost.querySelectorAll('.part-row')];
    let lastFilledIndex = -1;
    rows.forEach((row, index) => { if (!isBlankPartRow(row)) lastFilledIndex = index; });
    const row = addPartRow(item);
    partsHost.removeChild(row);
    if (lastFilledIndex === -1) {
      partsHost.insertBefore(row, partsHost.firstChild);
    } else {
      partsHost.insertBefore(row, rows[lastFilledIndex].nextSibling);
    }
    const blankRows = [...partsHost.querySelectorAll('.part-row')].filter(isBlankPartRow);
    if (partsHost.children.length > 24 && blankRows.length) {
      partsHost.removeChild(blankRows[blankRows.length - 1]);
    }
    recalculate();
  }

  function addTestingRow(item = {}) {
    const row = document.createElement('div');
    row.className = 'test-row';
    ['part','bore_diameter','length','thread','stop_tube_et'].forEach(key => {
      const input = document.createElement('input');
      input.dataset.testField = key;
      input.value = value(item, key, '');
      input.setAttribute('aria-label', `Testing ${key.replaceAll('_', ' ')}`);
      row.appendChild(input);
    });
    testingHost.appendChild(row);
  }

  function collectRows(host, rowSelector, fieldAttribute) {
    return [...host.querySelectorAll(rowSelector)].map(row =>
      Object.fromEntries([...row.querySelectorAll('input')].map(input => [input.dataset[fieldAttribute], input.value]))
    );
  }

  function collectForm() {
    const fields = Object.fromEntries([...form.querySelectorAll('[data-field]')].map(input => [input.dataset.field, input.value]));
    fields.parts = collectRows(partsHost, '.part-row', 'partField');
    fields.testing = collectRows(testingHost, '.test-row', 'testField');
    return fields;
  }

  function recalculate() {
    const get = key => form.querySelector(`[data-field="${key}"]`);
    const qty = Number(get('quantity').value || 0);
    const net = Number(get('net_each').value || 0);
    get('order_total').value = money(qty * net);
    const partsTotal = [...partsHost.querySelectorAll('[data-part-field="cost"]')].reduce((sum, input) => sum + Number(input.value || 0), 0);
    get('parts_total').value = money(partsTotal);
    get('parts_ratio').value = `${Math.round(qty * net ? partsTotal / (qty * net) * 100 : 0)}%`;
  }

  const CODE39 = {
    '0':'nnnwwnwnn','1':'wnnwnnnnw','2':'nnwwnnnnw','3':'wnwwnnnnn','4':'nnnwwnnnw',
    '5':'wnnwwnnnn','6':'nnwwwnnnn','7':'nnnwnnwnw','8':'wnnwnnwnn','9':'nnwwnnwnn',
    'A':'wnnnnwnnw','B':'nnwnnwnnw','C':'wnwnnwnnn','D':'nnnnwwnnw','E':'wnnnwwnnn',
    'F':'nnwnwwnnn','G':'nnnnnwwnw','H':'wnnnnwwnn','I':'nnwnnwwnn','J':'nnnnwwwnn',
    'K':'wnnnnnnww','L':'nnwnnnnww','M':'wnwnnnnwn','N':'nnnnwnnww','O':'wnnnwnnwn',
    'P':'nnwnwnnwn','Q':'nnnnnnwwn','R':'wnnnnnwwn','S':'nnwnnnwwn','T':'nnnnwnwwn',
    'U':'wwnnnnnnw','V':'nwwnnnnnw','W':'wwwnnnnnn','X':'nwnnwnnnw','Y':'wwnnwnnnn',
    'Z':'nwwnwnnnn','-':'nwnnnnwnw','.':'wwnnnnwnn',' ':'nwwnnnwnn','$':'nwnwnwnnn',
    '/':'nwnwnnnwn','+':'nwnnnwnwn','%':'nnnwnwnwn','*':'nwnnwnwnn'
  };
  function renderBarcode(value) {
    const canvas = document.getElementById('orderBarcode');
    const text = document.getElementById('orderBarcodeText');
    if (!canvas || !text) return;
    const encoded = `*${String(value || 'ORDER').toUpperCase().replace(/[^0-9A-Z. $/+%-]/g, '')}*`;
    const context = canvas.getContext('2d');
    const narrow = 2, wide = 5, gap = 2;
    const modules = [...encoded].flatMap(character => [...(CODE39[character] || CODE39['-'])].map((kind, index) => ({
      width: kind === 'w' ? wide : narrow, dark: index % 2 === 0
    })).concat({width: gap, dark: false}));
    const total = modules.reduce((sum, module) => sum + module.width, 0);
    const scale = Math.max(1, Math.min(3, Math.floor((canvas.width - 8) / total)));
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = '#fff'; context.fillRect(0, 0, canvas.width, canvas.height);
    let x = Math.floor((canvas.width - total * scale) / 2);
    modules.forEach(module => {
      if (module.dark) { context.fillStyle = '#111'; context.fillRect(x, 2, module.width * scale, canvas.height - 4); }
      x += module.width * scale;
    });
    text.textContent = String(value || '');
  }

  function openCustomerEmail() {
    const contactInput = form.querySelector('[data-field="contact"]');
    const email = emailFromText((contactInput && contactInput.value) || (loadedQuote && loadedQuote.customer_contact) || '');
    if (!email) {
      setMessage('No customer email is available for this order.', true);
      return;
    }
    window.location.href = `mailto:${encodeURIComponent(email)}`;
  }

  let addPartSearchTimer = null;

  function renderAddPartResults(parts) {
    addPartResults.innerHTML = '';
    if (!parts.length) {
      const empty = document.createElement('div');
      empty.className = 'add-part-empty';
      empty.textContent = 'No matching parts found.';
      addPartResults.appendChild(empty);
      return;
    }
    parts.forEach(part => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'add-part-result';
      button.innerHTML = `<span>${part.part_number}</span><span>${part.description || ''}</span><span>${part.sell_price || part.unit_cost || ''}</span>`;
      button.addEventListener('click', () => {
        insertPartAfterLastEntry({
          part_number: part.part_number, description: part.description || '',
          cost: part.sell_price || part.unit_cost || '0', on_hand: '0', allocated: '1'
        });
        closeAddPart();
      });
      addPartResults.appendChild(button);
    });
  }

  async function runAddPartSearch(query) {
    try {
      const response = await fetch(`/api/catalog-parts/search?q=${encodeURIComponent(query)}`);
      const body = await response.json();
      renderAddPartResults(response.ok && body.ok ? body.parts : []);
    } catch (err) {
      renderAddPartResults([]);
    }
  }

  function openAddPart() {
    addPartModal.hidden = false;
    addPartSearchInput.value = '';
    addPartResults.innerHTML = '';
    addPartSearchInput.focus();
    runAddPartSearch('');
  }

  function closeAddPart() {
    addPartModal.hidden = true;
  }

  function buildDefaults(quote) {
    const inputs = quote.cylinder_inputs_snapshot || {};
    const bd = quote.price_breakdown_snapshot || {};
    const address = splitAddress(quote.customer_name, quote.customer_address);
    const generatedParts = (quote.generated_parts || []).map(item => ({
      ...item,
      allocated: String(Math.max(1, Number(quote.quantity || 1)))
    }));
    const specialParts = Object.entries(inputs.special_parts || {}).map(([part, qty]) => ({
      part_number: part, description: `Quoted special part (Qty ${qty})`, cost: '0', on_hand: '0', allocated: String(qty || 0)
    }));
    const manualParts = (quote.manual_line_items || []).map(item => ({
      part_number: item.reference_part_number || '', description: item.description || '', cost: money(item.unit_price), on_hand: '0', allocated: String(item.quantity || 0)
    }));
    const includes = [...specialParts.map(x => x.part_number), ...manualParts.map(x => x.description)].filter(Boolean).join(', ');
    const description = inputs.series ? `${inputs.series} Series Cylinder` : 'Cylinder';
    return {
      quote_number: quote.quote_number || '', ordered_by: quote.created_by || '', order_number: '', order_date: localDate(quote.created_at), terms: 'NET 30',
      ship_to_1: address[0], ship_to_2: address[1], ship_to_3: address[2], ship_to_4: address[3],
      bill_to_1: address[0], bill_to_2: address[1], bill_to_3: address[2], bill_to_4: address[3],
      po_number: quote.reference_notes || '', tag: '', ship_method: '',
      ship_date: '', contact: quote.customer_contact || '',
      cylinder_description: description, quantity: String(Math.max(1, Number(quote.quantity || 1))), net_each: money(bd.quote_net_each),
      discount: money(Number(quote.discount || 0) * 100), order_total: money(Number(bd.quote_net_each || 0) * Math.max(1, Number(quote.quantity || 1))),
      description, model_code: quote.model_code || '', bore: value(inputs, 'bore'), mount: describedMount(value(inputs, 'mount')),
      rod_diameter: value(inputs, 'rod_diameter'), cushion: describedCode(CUSHION_LABELS, value(inputs, 'cushion')), ports: describedCode(PORT_LABELS, value(inputs, 'port_code')),
      stroke: value(inputs, 'stroke'), rod_thread: describedRodThread(value(inputs, 'rod_diameter'), value(inputs, 'rod_style')), seals: describedCode(SEAL_LABELS, value(inputs, 'seal_code')),
      includes, rod_clevis: String(value(inputs, 'rod_clevis', 0)), pivot_pin: String(value(inputs, 'pivot_pin', 0)),
      assembled_by: '', date_passed_test: '', parts_total: '0.00',
      parts: [...generatedParts, ...manualParts, ...specialParts],
      testing: [
        {part:'Rod',bore_diameter:value(inputs,'rod_diameter'),length:value(inputs,'stroke'),thread:value(inputs,'rod_style'),stop_tube_et:value(inputs,'stop_tube')},
        {part:'Tie Rod',bore_diameter:'',length:value(inputs,'tie_rod_length'),thread:'',stop_tube_et:''},
        {part:'Barrel',bore_diameter:value(inputs,'bore'),length:value(inputs,'stroke'),thread:'',stop_tube_et:''}
      ]
    };
  }

  function render(quote) {
    const data = {...buildDefaults(quote), ...(quote.order_form_snapshot || {})};
    data.quote_number = quote.quote_number || '';
    form.querySelectorAll('[data-field]').forEach(input => { input.value = value(data, input.dataset.field, ''); });
    const metaSection = document.getElementById('orderMetaSection');
    if (metaSection) {
      metaSection.style.display = data.order_number ? '' : 'none';
    }
    partsHost.innerHTML = '';
    (data.parts || []).forEach(addPartRow);
    while (partsHost.children.length < 29) addPartRow();
    testingHost.innerHTML = '';
    const testingRows = (data.testing || []).filter(row =>
      Object.values(row || {}).some(field => String(field || '').trim())
    );
    testingRows.forEach(addTestingRow);
    while (testingHost.children.length < 3) addTestingRow();
    setStatus(quote.status);
    recalculate();
    renderBarcode(data.order_number || quote.quote_number);
  }

  form.addEventListener('input', event => {
    if (event.target.matches('[data-field="quantity"],[data-field="net_each"],[data-part-field="cost"]')) recalculate();
  });

  emailCustomerButton.addEventListener('click', openCustomerEmail);

  async function saveHold() {
    const response = await fetch(`/api/quotes/${quoteId}/order/hold`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({order_form: collectForm()})
    });
    const body = await response.json();
    if (!response.ok || !body.ok) throw new Error(body.error || 'Hold failed');
    loadedQuote = body.quote;
    setStatus(body.quote.status);
    return body.quote;
  }

  holdButton.addEventListener('click', async () => {
    holdButton.disabled = true;
    holdButton.textContent = 'Holding...';
    setMessage('');
    try {
      await saveHold();
      window.location.assign('/employee/dashboard');
    } catch (error) {
      holdButton.disabled = false;
      holdButton.textContent = 'Hold';
      setMessage(error.message || 'Hold failed', true);
    }
  });

  dashboardButton.addEventListener('click', async event => {
    if (!loadedQuote || ['approved', 'denied', 'hold'].includes(loadedQuote.status)) return;
    event.preventDefault();
    dashboardButton.setAttribute('aria-disabled', 'true');
    try {
      await saveHold();
    } catch (error) {
      setMessage(error.message || 'Could not save hold status', true);
      dashboardButton.removeAttribute('aria-disabled');
      return;
    }
    window.location.assign(dashboardButton.href);
  });

  addPartButton.addEventListener('click', openAddPart);
  closeAddPartModal.addEventListener('click', closeAddPart);
  addPartModal.addEventListener('click', event => { if (event.target === addPartModal) closeAddPart(); });
  addPartSearchInput.addEventListener('input', () => {
    clearTimeout(addPartSearchTimer);
    addPartSearchTimer = setTimeout(() => runAddPartSearch(addPartSearchInput.value), 250);
  });

  approveButton.addEventListener('click', async () => {
    approveButton.disabled = true;
    approveButton.textContent = 'Approving…';
    setMessage('');
    try {
      const response = await fetch(`/api/quotes/${quoteId}/order/approve`, {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({order_form: collectForm()})
      });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.error || 'Approval failed');
      setStatus(body.quote.status);
      setMessage(`Order ${body.quote.quote_number} approved and saved.`);
      window.location.assign('/employee/dashboard');
      return;
    } catch (error) {
      approveButton.disabled = false;
      approveButton.textContent = 'Approve Order';
      setMessage(error.message || 'Approval failed', true);
    }
  });

  denyButton.addEventListener('click', async () => {
    if (!window.confirm('Deny this order?')) return;
    denyButton.disabled = true;
    denyButton.textContent = 'Denying...';
    setMessage('');
    try {
      const response = await fetch(`/api/quotes/${quoteId}/order/deny`, {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({})
      });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.error || 'Denial failed');
      setStatus(body.quote.status);
      setMessage(`Order ${body.quote.quote_number} denied.`);
      window.location.assign('/employee/dashboard');
    } catch (error) {
      denyButton.disabled = false;
      denyButton.textContent = 'Deny Order';
      setMessage(error.message || 'Denial failed', true);
    }
  });

  async function load() {
    if (!quoteId) { setMessage('This approval link is missing a quote ID.', true); approveButton.disabled = true; return; }
    try {
      const response = await fetch(`/api/quotes/${quoteId}`);
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.error || 'Order not found');
      loadedQuote = body.quote;
      render(body.quote);
    } catch (error) {
      setMessage(error.message || 'Order could not be loaded.', true);
      statusEl.textContent = 'Error';
      approveButton.disabled = true;
    }
  }
  load();
})();
