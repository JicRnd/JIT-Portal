# Quote Form integration

The form is standalone and does not include email, PDF, Data1, approval, or quote history.

## Canonical form routes

The customer calculator does not build or populate a customer quote form.
The only customer quote-form template is:

`app/customer_quote_form/customer_quote_form.html`

It is served by `/customer/quote-form`. The employee quote form remains the separate
`app/Employee_quote_form/employee_quote_forms.html` template.

The calculator may calculate and validate a quote without navigating to either form.
For an employee handoff, the existing employee route may use session storage:

```javascript
const quoteData = {
  customer_name: document.querySelector('#customer_name')?.value,
  quantity: 1,
  model_code: calculatedResult.model_code,
  description: calculatedResult.description,
  list_price: calculatedResult.list_price,
  net_each: calculatedResult.net_price,
  series: calculatedResult.series,
  mount: calculatedResult.mount,
  bore: calculatedResult.bore,
  stroke: calculatedResult.stroke,
  rod: calculatedResult.rod
};

sessionStorage.setItem('jitQuoteDraft', JSON.stringify(quoteData));
window.location.href = '/employee/quote-entry?draft=1';
```
