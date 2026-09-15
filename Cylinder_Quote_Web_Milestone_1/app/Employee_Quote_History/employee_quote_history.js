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

const search = document.getElementById("quoteHistorySearch");
const clearSearch = document.getElementById("clearEmployeeQuoteHistorySearchButton");

if (search && clearSearch) {
  clearSearch.addEventListener("click", () => {
    search.value = "";
    search.focus();
  });
}
