(function () {
  const mode =
    document.body.dataset.portalMode || "employee";

  const quoteId =
    new URLSearchParams(location.search)
      .get("quote_id");

  if (!quoteId) {
    return;
  }

  async function setSelect(name, value) {
    const element = document.getElementById(name);

    if (!element || value == null) {
      return;
    }

    element.value = String(value);

    element.dispatchEvent(
      new Event("change", {
        bubbles: true,
      })
    );

    await new Promise((resolve) => {
      setTimeout(resolve, 0);
    });
  }

  (async () => {
    try {
      if (window.jitCalculatorReady) {
        await window.jitCalculatorReady;
      }

      const response = await fetch(
        "/portal/api/quotes/"
        + encodeURIComponent(quoteId)
      );

      const body = await response.json();

      if (!response.ok || !body.ok) {
        throw new Error(
          body.error
          || "Saved quote could not be opened"
        );
      }

      const quote = body.quote;
      window.JIT_EDIT_QUANTITY = Math.max(
        1,
        Number(quote.quantity || 1)
      );
      const inputs =
        quote.cylinder_inputs_snapshot || {};

      const customer =
        document.getElementById("customer_name");

      const address =
        document.getElementById("customer_address");

      if (customer) {
        customer.value =
          quote.customer_name || "";
      }

      if (address) {
        address.value =
          quote.customer_address || "";
      }

      await setSelect(
        "series",
        inputs.series
      );

      await setSelect(
        "mount",
        inputs.mount
      );

      await setSelect(
        "bore",
        inputs.bore
      );

      await setSelect(
        "rod_diameter",
        inputs.rod_diameter
      );

      const stroke =
        document.getElementById("stroke");

      if (stroke) {
        stroke.value = inputs.stroke || "";
      }

      await setSelect(
        "rod_style",
        inputs.rod_style
      );

      await setSelect(
        "cushion",
        inputs.cushion
      );

      await setSelect(
        "port_code",
        inputs.port_code
      );

      await setSelect(
        "seal_code",
        inputs.seal_code
      );

      if (mode === "employee") {
        const discount =
          document.getElementById("discount_pct");

        if (discount) {
          discount.value =
            Number(inputs.discount || 0) * 100;
        }
      }

      document.title =
        "Edit " + quote.quote_number;

    } catch (error) {
      alert(error.message);
    }
  })();
})();
