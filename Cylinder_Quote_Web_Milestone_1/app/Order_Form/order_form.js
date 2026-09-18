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
  const cancelButton = document.getElementById('cancelOrderButton');
  const emailCustomerButton = document.getElementById('emailCustomerButton');
  const emailAttachmentDialog = document.getElementById('emailAttachmentDialog');
  const continueEmailButton = document.getElementById('continueEmailButton');
  const cancelEmailAttachmentButton = document.getElementById('cancelEmailAttachmentButton');
  const partsHost = document.getElementById('orderPartsRows');
  const testingHost = document.getElementById('testingRows');
  const addPartButton = document.getElementById('addPartButton');
  const addPartModal = document.getElementById('addPartModal');
  const addPartSearchInput = document.getElementById('addPartSearchInput');
  const addPartResults = document.getElementById('addPartResults');
  const closeAddPartModal = document.getElementById('closeAddPartModal');
  let loadedQuote = null;
  let tieRodReference = [];
  let mt4Reference = [];
  let hEngineeringReference = [];
  let barrelReference = [];
  let torqueReference = [];
  let weightReference = [];

  const money = n => Number(n || 0).toFixed(2);
  const amount = value => Number(String(value ?? '').replace(/[$,]/g, '')) || 0;
  const currency = value => {
    if (String(value ?? '').trim() === '') return '';
    return `$${amount(value).toFixed(2)}`;
  };
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
  const H_BARREL_ADDITIONS = {'1.5':1.563,'2':1.563,'2.5':1.688,'3.25':1.938,'4':2.188,'5':2.688,'6':3.063,'7':3.188,'8':3.688,'10':5.75,'12':7.125,'14':7.625};
  const H_TORQUE = {'1.5':30,'2':80,'2.5':80,'3.25':125,'4':125,'5':300,'6':550,'7':800,'8':1100,'10':1100};
  const H_WEIGHT = {'1.5|0.625':[9,.5],'1.5|1':[9.3,.6],'2|1':[13.2,.8],'2|1.375':[17.1,1],'2.5|1':[19.5,1.1],'2.5|1.375':[19.5,1.1],'2.5|1.75':[25.5,1.5],'3.25|1.375':[41,1.8],'3.25|1.75':[41,1.8],'3.25|2':[46,2.2],'4|1.75':[53,2.5],'4|2':[53,2.5],'4|2.5':[58,3.2],'5|2':[82,3.4],'5|2.5':[82,3.4],'5|3':[86,5.2],'5|3.5':[86,5.2],'6|2.5':[133,5.2],'6|3':[133,5.2],'6|3.5':[140,7.3],'6|4':[140,7.3],'7|3':[242,6.7],'7|3.5':[242,6.7],'7|4':[253,10.3],'7|4.5':[253,10.3],'7|5':[253,10.3],'8|3.5':[276,9],'8|4':[276,9],'8|4.5':[309,13],'8|5':[309,13],'8|5.5':[309,13]};
  const H_ROD_ADDITIONS = {
    '5|2|1|NC':8.73,'5|2|1|RE':8.73,'5|2|1|BE':10,'5|2|1|CE':10,
    '5|2|2|NC':8.73,'5|2|2|RE':8.73,'5|2|2|BE':10,'5|2|2|CE':10,
    '5|2|3|NC':6.48,'5|2|3|RE':6.48,'5|2|3|BE':7.75,'5|2|3|CE':7.75,
    '5|2|4|NC':8.23,'5|2|4|RE':8.23,'5|2|4|BE':9.5,'5|2|4|CE':9.5
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
  function normalizeDimension(raw) {
    const number = Number(raw);
    return Number.isFinite(number) ? String(number) : String(raw || '').trim();
  }
  function sumDimensions(...values) {
    const numbers = values.map(Number);
    return numbers.every(Number.isFinite) ? numbers.reduce((sum, number) => sum + number, 0) : '';
  }
  function displayNumber(raw, decimals = 3) {
    const number = Number(raw);
    if (!Number.isFinite(number)) return String(raw || '').trim();
    return number.toFixed(decimals).replace(/\.0+$|(?<=\.[0-9]*?)0+$/, '').replace(/\.$/, '');
  }
  function displayAllocated(item) {
    const category = String(item.allocation_category || '').toLowerCase();
    const decimals = category === 'length_based' ? 3 : 0;
    return displayNumber(item.allocated, decimals);
  }
  function engineeringOutputs(inputs, tieRod) {
    const series = String(inputs.series || '').toUpperCase();
    const engineeringSeries = series === 'LH' ? 'A' : series;
    const boreKey = normalizeDimension(inputs.bore);
    const rodKey = normalizeDimension(inputs.rod_diameter);
    const stroke = Number(inputs.stroke);
    const cushion = String(inputs.cushion || '').toUpperCase();
    const style = String(inputs.rod_style || '1');
    const isHFamily = ['H', 'HM'].includes(series);
    const extractedRodRule = hEngineeringReference.find(rule =>
      rule.families.includes(engineeringSeries) &&
      normalizeDimension(rule.bore) === boreKey &&
      normalizeDimension(rule.rod) === rodKey &&
      rule.cushions.includes(cushion) &&
      rule.rod_styles.includes(Number(style))
    );
    const rodAddition = extractedRodRule
      ? extractedRodRule.rod_length_addition
      : (isHFamily ? H_ROD_ADDITIONS[`${boreKey}|${rodKey}|${style}|${cushion}`] : undefined);
    const barrelRule = barrelReference.find(rule => normalizeDimension(rule.bore) === boreKey);
    const barrelAddition = barrelRule
      ? barrelRule.families[engineeringSeries]
      : (isHFamily ? H_BARREL_ADDITIONS[boreKey] : undefined);
    const tieRodAddition = tieRod && Number(tieRod.assembly_length);
    const length = addition => Number.isFinite(stroke) && Number.isFinite(Number(addition)) ? stroke + Number(addition) : '';
    const extractedWeightRule = weightReference.find(rule =>
      rule.families.includes(engineeringSeries) &&
      normalizeDimension(rule.bore) === boreKey &&
      normalizeDimension(rule.rod) === rodKey
    );
    const weightRule = extractedWeightRule
      ? [extractedWeightRule.weight_base, extractedWeightRule.weight_per_stroke]
      : (isHFamily ? H_WEIGHT[`${boreKey}|${rodKey}`] : null);
    const torqueRule = torqueReference.find(rule => normalizeDimension(rule.bore) === boreKey);
    const torque = torqueRule
      ? torqueRule.families[series] || ''
      : (isHFamily ? H_TORQUE[boreKey] || '' : '');
    return {
      rodLength: length(rodAddition),
      tieRodLength: length(tieRodAddition),
      barrelLength: length(barrelAddition),
      torque,
      weight: weightRule && Number.isFinite(stroke) ? weightRule[0] + weightRule[1] * stroke : ''
    };
  }
  function applyRodLengthToParts(parts, rodLength) {
    const lengthValue = Number(rodLength);
    if (!Number.isFinite(lengthValue)) return parts;
    return parts.map(item => {
      if (String(item.description || '').trim().toLowerCase() !== 'rod') return item;
      const currentAllocated = Number(item.allocated);
      const unitPrice = item.unit_price != null
        ? Number(item.unit_price)
        : (currentAllocated ? amount(item.cost) / currentAllocated : NaN);
      if (!Number.isFinite(unitPrice)) return item;
      return {
        ...item,
        allocated: displayNumber(lengthValue, 3),
        allocation_category: 'length_based',
        cost: money(unitPrice * lengthValue),
        unit_price: unitPrice
      };
    });
  }
  function parseTieRodReference(payload) {
    mt4Reference = Array.isArray(payload && payload.mt4_rules) ? payload.mt4_rules : [];
    if (Array.isArray(payload && payload.tie_rod_rules)) {
      return payload.tie_rod_rules;
    }
    const rows = Array.isArray(payload && payload.rows) ? payload.rows : [];
    return rows.flatMap(entry => {
      const cells = Object.fromEntries((entry.cells || []).map(cell => [cell.column, cell]));
      const formula = String(cells[15] && cells[15].formula || '');
      const boreMatch = formula.match(/Data!\$?B\$?4=([0-9.]+)/i);
      const rodMatch = formula.match(/Data!\$?B\$?6=([0-9.]+)/i);
      if (!boreMatch || !rodMatch) return [];
      const series = [...formula.matchAll(/Data!\$?B\$?3="([A-Z0-9]+)"/gi)].map(match => match[1].toUpperCase());
      return [{
        series,
        bore: normalizeDimension(boreMatch[1]),
        rod: normalizeDimension(rodMatch[1]),
        diameter: cells[7] && cells[7].value,
        rod_thread_length: cells[8] && cells[8].value,
        cap_thread_length: cells[9] && cells[9].value,
        through_rod: cells[12] && cells[12].value,
        through_cap: cells[13] && cells[13].value,
        assembly_length: cells[14] && cells[14].value,
        assembly_components: [4, 6, 10, 11, 12, 13].map(column => cells[column] && cells[column].value)
      }];
    });
  }
  async function loadTieRodReference() {
    try {
      const response = await fetch('/static/tierod_reference.json');
      if (!response.ok) return;
      tieRodReference = parseTieRodReference(await response.json());
    } catch (error) {
      tieRodReference = [];
    }
  }
  async function loadHEngineeringReference() {
    try {
      const response = await fetch('/static/sheet_h_engineering.json');
      if (!response.ok) return;
      const payload = await response.json();
      hEngineeringReference = Array.isArray(payload && payload.rod_addition_rules)
        ? payload.rod_addition_rules
        : [];
      barrelReference = Array.isArray(payload && payload.barrel_rules)
        ? payload.barrel_rules
        : [];
      torqueReference = Array.isArray(payload && payload.torque_rules)
        ? payload.torque_rules
        : [];
      weightReference = Array.isArray(payload && payload.weight_rules)
        ? payload.weight_rules
        : [];
    } catch (error) {
      hEngineeringReference = [];
      barrelReference = [];
      torqueReference = [];
      weightReference = [];
    }
  }
  function findTieRodReference(series, bore, rod, mount) {
    const normalizedSeries = String(series || '').toUpperCase();
    const normalizedBore = normalizeDimension(bore);
    const normalizedRod = normalizeDimension(rod);
    const normalizedMount = String(mount || '').toUpperCase();
    const reference = normalizedMount === 'MT4' ? mt4Reference : tieRodReference;
    const candidates = reference.filter(item =>
      normalizeDimension(item.bore) === normalizedBore &&
      (!item.series.length || item.series.includes(normalizedSeries)) &&
      (!item.rod || normalizeDimension(item.rod) === normalizedRod) &&
      (!item.mounts || item.mounts.includes(normalizedMount))
    );
    return candidates.find(item => item.rod && normalizeDimension(item.rod) === normalizedRod) || candidates[0];
  }
  function tieRodOutputs(reference) {
    if (!reference) return null;
    return {
      bore_diameter: reference.tie_rod_diameter,
      rod_end_thread_length: reference.rod_end_thread_length,
      cap_end_thread_length: reference.cap_end_thread_length,
      assembly_length: reference.assembly_length
    };
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
    const partNumber = String(item.part_number || '').trim();
    ['part_number','description','cost','on_hand','allocated'].forEach(key => {
      const input = document.createElement('input');
      input.dataset.partField = key;
      const rawValue = value(item, key, '');
      if (key === 'cost') {
        const allocated = Number(item.allocated || 1);
        const fallbackUnitPrice = allocated ? Number(rawValue || 0) / allocated : 0;
        const hasPrice = item.unit_price != null || String(rawValue).trim() !== '' || partNumber || String(item.description || '').trim() !== '';
        if (hasPrice) input.dataset.unitPrice = String(value(item, 'unit_price', fallbackUnitPrice));
      }
      input.value = partNumber && key === 'allocated' && (rawValue === '' || Number(rawValue) === 0)
        ? '1'
        : key === 'allocated'
          ? displayAllocated(item)
        : key === 'cost'
          ? currency(rawValue)
          : rawValue;
      if (key === 'cost' || key === 'on_hand' || key === 'allocated') input.inputMode = 'decimal';
      input.setAttribute('aria-label', key.replaceAll('_', ' '));
      row.appendChild(input);
    });
    partsHost.appendChild(row);
    return row;
  }

  function recalculatePartCosts() {
    partsHost.querySelectorAll('.part-row').forEach(row => {
      const cost = row.querySelector('[data-part-field="cost"]');
      const allocated = row.querySelector('[data-part-field="allocated"]');
      if (!cost || !allocated || cost.dataset.unitPrice == null || cost.dataset.unitPrice === '') return;
      cost.value = currency(Number(cost.dataset.unitPrice) * Number(allocated.value || 0));
    });
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
    row.id = `Row${testingHost.children.length + 1}`;
    const lastField = item.part === 'Barrel' ? 'weight' : 'stop_tube_et';
    ['part','bore_diameter','length','thread',lastField].forEach(key => {
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
    const partsTotal = [...partsHost.querySelectorAll('[data-part-field="cost"]')].reduce((sum, input) => sum + amount(input.value), 0);
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

  function openEmailAttachmentDialog() {
    if (emailAttachmentDialog) emailAttachmentDialog.showModal();
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
          cost: part.sell_price || part.unit_cost || '0',
          on_hand: part.on_hand || '0', allocated: part.allocated || '1'
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
    const generatedParts = (quote.generated_parts || []).map(item => ({...item}));
    const specialParts = Object.entries(inputs.special_parts || {}).map(([part, qty]) => ({
      part_number: part, description: `Quoted special part (Qty ${qty})`, cost: '0', on_hand: '0', allocated: String(qty || 0)
    }));
    const manualParts = (quote.manual_line_items || []).map(item => ({
      part_number: item.reference_part_number || '', description: item.description || '', cost: money(item.unit_price), on_hand: '0', allocated: String(item.quantity || 0)
    }));
    const includes = [...specialParts.map(x => x.part_number), ...manualParts.map(x => x.description)].filter(Boolean).join(', ');
    const description = inputs.series ? `${inputs.series} Series Cylinder` : 'Cylinder';
    const mount = String(value(inputs, 'mount') || '').toUpperCase();
    const tieRod = findTieRodReference(inputs.series, inputs.bore, inputs.rod_diameter, mount);
    const tieRodOutputsData = tieRodOutputs(tieRod);
    const engineering = engineeringOutputs(inputs, tieRod);
    const tieRodThread = tieRodOutputsData && (tieRodOutputsData.rod_end_thread_length || tieRodOutputsData.cap_end_thread_length)
      ? `${displayNumber(tieRodOutputsData.rod_end_thread_length)} - ${displayNumber(tieRodOutputsData.cap_end_thread_length)}`
      : '';
    const boreRod = inputs.bore && inputs.rod_diameter
      ? `${displayNumber(inputs.bore, 2)} - ${displayNumber(inputs.rod_diameter)}`
      : '';
    const rodStopTube = [value(inputs, 'stop_tube'), value(inputs, 'extra_thread')]
      .filter(item => item != null && String(item).trim() !== '' && Number(item) !== 0)
      .join(' + ');
    const orderParts = Array.isArray(quote.order_form_parts)
      ? quote.order_form_parts
      : [...generatedParts, ...manualParts, ...specialParts];
    const correctedOrderParts = applyRodLengthToParts(orderParts, engineering.rodLength);
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
      parts_total: '0.00',
      parts: correctedOrderParts,
      testing: [
        {part:'Rod',bore_diameter:boreRod,length:engineering.rodLength || value(inputs,'stroke'),thread:describedRodThread(value(inputs,'rod_diameter'), value(inputs,'rod_style')),stop_tube_et:rodStopTube || '-'},
        {part:'Tie Rod',bore_diameter:tieRodOutputsData ? displayNumber(tieRodOutputsData.bore_diameter) : '',length:engineering.tieRodLength || value(inputs,'tie_rod_length'),thread:tieRodThread,stop_tube_et:engineering.torque ? `Torque= ${engineering.torque} Ft/Lbs` : (mount === 'MT4' ? value(inputs,'stop_tube') : '-')},
        {part:'Barrel',bore_diameter:inputs.bore ? displayNumber(inputs.bore, 2) : '',length:engineering.barrelLength || value(inputs,'stroke'),thread:'Weight',weight:engineering.weight ? displayNumber(engineering.weight, 1) : '-'}
      ]
    };
  }

  function render(quote) {
    const generated = buildDefaults(quote);
    const data = {...generated, ...(quote.order_form_snapshot || {})};
    data.testing = generated.testing;
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
    recalculatePartCosts();
    recalculate();
    renderBarcode(data.order_number || quote.quote_number);
  }

  form.addEventListener('input', event => {
    if (event.target.matches('[data-part-field="part_number"]')) {
      const row = event.target.closest('.part-row');
      const partNumber = event.target.value.trim();
      const allocated = row.querySelector('[data-part-field="allocated"]');
      if (!partNumber) {
        row.querySelectorAll('input').forEach(input => { input.value = ''; });
      } else if (!allocated.value || Number(allocated.value) === 0) {
        allocated.value = '1';
      }
    }
    if (event.target.matches('[data-part-field="allocated"]')) {
      recalculatePartCosts();
      recalculate();
    } else if (event.target.matches('[data-field="quantity"],[data-field="net_each"],[data-part-field="cost"]')) recalculate();
  });

  emailCustomerButton.addEventListener('click', openEmailAttachmentDialog);
  continueEmailButton.addEventListener('click', () => {
    if (emailAttachmentDialog) emailAttachmentDialog.close();
    openCustomerEmail();
  });
  cancelEmailAttachmentButton.addEventListener('click', () => {
    if (emailAttachmentDialog) emailAttachmentDialog.close();
  });

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

  cancelButton.addEventListener('click', () => {
    if (!window.confirm('Cancel editing this order? Unsaved changes will be discarded.')) return;
    window.location.assign('/employee/dashboard');
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
      window.location.assign('/employee_quote_history/employee_quote_history.html');
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
      await Promise.all([loadTieRodReference(), loadHEngineeringReference()]);
      render(body.quote);
    } catch (error) {
      setMessage(error.message || 'Order could not be loaded.', true);
      statusEl.textContent = 'Error';
      approveButton.disabled = true;
    }
  }
  load();
})();
