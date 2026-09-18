document.querySelectorAll(".new-quote").forEach((button) => {
  button.addEventListener("click", () => {
    const modal = document.querySelector(".quote-modal");
    modal.hidden = false;
    modal.querySelector(".standard-choice").onclick = () => {
      location.href = button.dataset.standard;
    };
    modal.querySelector(".metric-choice").onclick = () => {
      location.href = button.dataset.metric;
    };
  });
});

document.querySelectorAll(".modal-close").forEach((button) => {
  button.addEventListener("click", () => {
    button.closest(".quote-modal").hidden = true;
  });
});

const quoteHistorySearch = document.getElementById("quoteHistorySearch");
const clearQuoteHistorySearchButton = document.getElementById("clearQuoteHistorySearchButton");
const quoteHistorySuggestions = document.getElementById("searchSuggestions");

function hideQuoteHistorySuggestions() {
  quoteHistorySuggestions.hidden = true;
  quoteHistorySuggestions.replaceChildren();
}

function renderQuoteHistorySuggestions(results) {
  quoteHistorySuggestions.replaceChildren();

  results.forEach((quote) => {
    const link = document.createElement("a");
    link.className = "quote-history-suggestion";
      link.href = `/employee/quote-entry?quote_id=${encodeURIComponent(quote.id || "")}`;

    const quoteNumber = document.createElement("strong");
    quoteNumber.className = "quote-history-suggestion-number";
    quoteNumber.textContent = quote.quote_number || "Quote";

    const customer = document.createElement("span");
    customer.className = "quote-history-suggestion-customer";
    customer.textContent = quote.customer || "No customer";

    const modelCode = document.createElement("span");
    modelCode.className = "quote-history-suggestion-model";
    modelCode.textContent = quote.model_code || "No model code";

    link.append(quoteNumber, customer, modelCode);
    quoteHistorySuggestions.append(link);
  });

  quoteHistorySuggestions.hidden = results.length === 0;
}

let quoteHistorySearchTimer;
quoteHistorySearch.addEventListener("input", () => {
  clearTimeout(quoteHistorySearchTimer);
  const query = quoteHistorySearch.value.trim();

  if (query.length < 2) {
    hideQuoteHistorySuggestions();
    return;
  }

  quoteHistorySearchTimer = setTimeout(async () => {
    try {
      const response = await fetch(
        `/employee_quote_history_search?q=${encodeURIComponent(query)}`
      );
      const body = await response.json();
      renderQuoteHistorySuggestions(body.results || []);
    } catch (error) {
      hideQuoteHistorySuggestions();
    }
  }, 220);
});

clearQuoteHistorySearchButton.addEventListener("click", () => {
  quoteHistorySearch.value = "";
  hideQuoteHistorySuggestions();
  quoteHistorySearch.focus();
});
