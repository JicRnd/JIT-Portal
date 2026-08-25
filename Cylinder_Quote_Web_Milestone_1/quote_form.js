(() => {
  "use strict";

  const editable = () => [...document.querySelectorAll(".editable")];
  const byId = (id) => document.getElementById(id);

  const aliases = {
    customer: "customer_name", company: "customer_name", customerCompany: "customer_name",
    address: "customer_address", city: "customer_city", state: "customer_state", zip: "customer_zip",
    contact: "contact_name", phone: "contact_phone", email: "contact_email",
    quoteNumber: "quote_number", quote_no: "quote_number", date: "quote_date",
    reference: "customer_reference", po: "customer_reference", customer_ref: "customer_reference",
    sales_rep: "salesperson", terms: "payment_terms", shipping: "shipping_terms",
    qty: "quantity", model: "model_code", modelCode: "model_code", part_number: "model_code",
    cylinder_description: "description", leadTime: "lead_time",
    list: "list_price", listPrice: "list_price", discount: "discount_percent",
    net: "net_each", netPrice: "net_each", price: "net_each",
    expedited: "expedited_net", emergency: "emergency_net",
    port: "ports", cushion: "cushions", seal: "seals", accessory: "options",
    push: "push_force", pull: "pull_force", closed: "closed_dimension", open: "open_dimension",
    special_parts: "special_order_parts", notes: "comments"
  };

  function flatten(value, prefix = "", result = {}) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return result;
    Object.entries(value).forEach(([key, item]) => {
      const joined = prefix ? `${prefix}_${key}` : key;
      if (item && typeof item === "object" && !Array.isArray(item)) flatten(item, joined, result);
      else result[key] = item;
      result[joined] = item;
    });
    return result;
  }

  function cleanNumber(value) {
    const number = Number(String(value ?? "").replace(/[^0-9.-]/g, ""));
    return Number.isFinite(number) ? number : 0;
  }

  function money(value) {
    return cleanNumber(value).toLocaleString("en-US", { style: "currency", currency: "USD" });
  }

  function updateExtended() {
    const qty = Math.max(0, cleanNumber(byId("quantity").value));
    [["net_each", "extended_price"], ["expedited_net", "expedited_extended"], ["emergency_net", "emergency_extended"]]
      .forEach(([source, target]) => { byId(target).textContent = money(cleanNumber(byId(source).value) * qty); });
  }

  function calculateNet(listId, discountId, netId) {
    const list = cleanNumber(byId(listId).value);
    const discount = cleanNumber(byId(discountId).value);
    if (list) byId(netId).value = money(list * (1 - discount / 100));
  }

  function populate(payload = {}) {
    const data = flatten(payload);
    Object.entries(data).forEach(([incomingKey, value]) => {
      if (value === undefined || value === null || typeof value === "object") return;
      const id = aliases[incomingKey] || incomingKey;
      const field = byId(id);
      if (field && field.matches("input, textarea")) field.value = value;
    });
    updateExtended();
    document.dispatchEvent(new CustomEvent("quote-form-populated", { detail: collect() }));
  }

  function collect() {
    const result = {};
    editable().forEach((field) => { if (field.id) result[field.id] = field.value; });
    result.extended_price = byId("extended_price").textContent;
    result.expedited_extended = byId("expedited_extended").textContent;
    result.emergency_extended = byId("emergency_extended").textContent;
    return result;
  }

  function clear() {
    editable().forEach((field) => { field.value = ""; });
    byId("quantity").value = "1";
    byId("payment_terms").value = "Net 30";
    updateExtended();
  }

  function loadFromPage() {
    const params = new URLSearchParams(location.search);
    const encoded = params.get("data") || params.get("quote");
    if (encoded) {
      try {
        const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/");
        populate(JSON.parse(decodeURIComponent(escape(atob(normalized)))));
        return;
      } catch (error) { console.warn("Quote data in the URL could not be read.", error); }
    }

    const direct = {};
    params.forEach((value, key) => { if (key !== "sample") direct[key] = value; });
    if (Object.keys(direct).length) { populate(direct); return; }

    for (const key of ["cylinderQuoteDraft", "quoteDraft", "currentQuote"]) {
      const saved = sessionStorage.getItem(key);
      if (!saved) continue;
      try { populate(JSON.parse(saved)); return; } catch (_) { /* try the next key */ }
    }
    if (params.get("sample") === "1") loadSample();
  }

  function loadSample() {
    populate({
      quote_number: "Q-10482", quote_date: new Date().toISOString().slice(0, 10), valid_through: "2026-09-16",
      customer_name: "Sample Industrial Customer", customer_address: "1250 Commerce Drive",
      customer_city: "Springfield", customer_state: "OH", customer_zip: "45502",
      contact_name: "Jordan Taylor", contact_phone: "(555) 014-2200", contact_email: "jordan@example.com",
      salesperson: "Inside Sales", customer_reference: "Replacement cylinder", payment_terms: "Net 30", shipping_terms: "FOB factory",
      quantity: 2, model_code: "H-MF1-4.00-18.00-2.00",
      description: "Heavy-duty hydraulic cylinder, H Series, MF1 mount, 4.00 in bore, 18.00 in stroke, 2.00 in rod, standard ports and seals.",
      lead_time: "6–8 weeks", list_price: "$3,280.00", discount_percent: "25%", net_each: "$2,460.00",
      expedited_net: "$2,829.00", emergency_net: "$3,198.00", series: "H", mount: "MF1", bore: "4.00 in",
      stroke: "18.00 in", rod: "2.00 in", ports: "SAE-12", cushions: "Both ends", seals: "Buna-N",
      options: "Rod boot", weight: "142 lb", push_force: "37,699 lb", pull_force: "28,274 lb",
      closed_dimension: "34.50 in", open_dimension: "52.50 in",
      comments: "Dimensions and performance values are based on the stated configuration. Verify mounting and port orientation before ordering."
    });
  }

  editable().forEach((field) => field.addEventListener("input", updateExtended));
  [["list_price", "discount_percent", "net_each"], ["expedited_list", "expedited_discount", "expedited_net"], ["emergency_list", "emergency_discount", "emergency_net"]]
    .forEach(([list, discount, net]) => byId(discount).addEventListener("change", () => { calculateNet(list, discount, net); updateExtended(); }));

  byId("load-sample").addEventListener("click", loadSample);
  byId("clear-form").addEventListener("click", clear);
  window.addEventListener("message", (event) => {
    const message = event.data;
    if (!message || typeof message !== "object") return;
    if (["CYLINDER_QUOTE_DATA", "POPULATE_QUOTE_FORM", "quote-data"].includes(message.type)) populate(message.payload || message.data || {});
  });
  document.addEventListener("cylinder-quote-data", (event) => populate(event.detail || {}));

  window.CylinderQuoteForm = { populate, collect, clear, loadSample };
  window.populateQuoteForm = populate;
  loadFromPage();
  if (window.opener) window.opener.postMessage({ type: "QUOTE_FORM_READY" }, "*");
})();
