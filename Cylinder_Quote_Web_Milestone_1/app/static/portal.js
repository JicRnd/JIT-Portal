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

const search = document.getElementById("globalSearch");
const suggestions = document.getElementById("searchSuggestions");
let searchTimer;

if (search && suggestions) {
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);

    const query = search.value.trim();

    if (query.length < 2) {
      suggestions.hidden = true;
      return;
    }

    searchTimer = setTimeout(async () => {
      try {
        const response = await fetch(
          "/portal/api/search?q="
          + encodeURIComponent(query)
        );

        const body = await response.json();

        suggestions.innerHTML = (
          body.results || []
        ).map((row) => {
          if (row.type === "customer") {
            return `
              <a href="/employee/dashboard?q=${encodeURIComponent(row.name)}">
                <small style="color:#666; margin-right:0.4rem;">Customer</small>
                <strong>${row.name}</strong>
                · ${row.address || "No address"}
              </a>
            `;
          }

          return `
            <a href="/employee_quote_form/employee_quote_form.html?quote_id=${row.id}">
              <strong>${row.quote_number}</strong>
              · ${row.customer || "No customer"}
              · ${row.model_code || "No model code"}
            </a>
          `;
        }).join("");

        suggestions.hidden = !body.results.length;

      } catch (error) {
        suggestions.hidden = true;
      }
    }, 220);
  });
}
