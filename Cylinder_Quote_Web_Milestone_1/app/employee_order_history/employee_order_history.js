const orderHistorySearch = document.getElementById("orderHistorySearch");
const clearOrderHistorySearchButton = document.getElementById("clearOrderHistorySearchButton");
const orderHistorySuggestions = document.getElementById("searchSuggestions");

function hideOrderHistorySuggestions() {
  orderHistorySuggestions.hidden = true;
  orderHistorySuggestions.replaceChildren();
}

function renderOrderHistorySuggestions(results) {
  orderHistorySuggestions.replaceChildren();

  results.forEach((order) => {
    const link = document.createElement("a");
    link.className = "order-history-suggestion";
    link.href = `/employee_order_history/employee_order_history.html?q=${encodeURIComponent(order.order_number || "")}`;

    const orderNumber = document.createElement("strong");
    orderNumber.className = "order-history-suggestion-order";
    orderNumber.textContent = order.order_number || "Order";

    const customer = document.createElement("span");
    customer.className = "order-history-suggestion-customer";
    customer.textContent = order.customer || "No customer";

    const modelCode = document.createElement("span");
    modelCode.className = "order-history-suggestion-model";
    modelCode.textContent = order.model_code || "No model code";

    link.append(orderNumber, customer, modelCode);
    orderHistorySuggestions.append(link);
  });

  orderHistorySuggestions.hidden = results.length === 0;
}

let orderHistorySearchTimer;
orderHistorySearch.addEventListener("input", () => {
  clearTimeout(orderHistorySearchTimer);
  const query = orderHistorySearch.value.trim();

  if (query.length < 2) {
    hideOrderHistorySuggestions();
    return;
  }

  orderHistorySearchTimer = setTimeout(async () => {
    try {
      const response = await fetch(
        `/employee/order-history-search?q=${encodeURIComponent(query)}`
      );
      const body = await response.json();
      renderOrderHistorySuggestions(body.results || []);
    } catch (error) {
      hideOrderHistorySuggestions();
    }
  }, 220);
});

clearOrderHistorySearchButton.addEventListener("click", () => {
  orderHistorySearch.value = "";
  hideOrderHistorySuggestions();
  orderHistorySearch.focus();
});

document.querySelectorAll(".new-quote").forEach((button) => {
  button.addEventListener("click", () => {
    const modal = document.querySelector(".quote-modal");
    modal.hidden = false;
    modal.querySelector(".standard-choice").onclick = () => {
      window.location.href = button.dataset.standard;
    };
    modal.querySelector(".metric-choice").onclick = () => {
      window.location.href = button.dataset.metric;
    };
  });
});

document.querySelectorAll(".modal-close").forEach((button) => {
  button.addEventListener("click", () => {
    button.closest(".quote-modal").hidden = true;
  });
});
