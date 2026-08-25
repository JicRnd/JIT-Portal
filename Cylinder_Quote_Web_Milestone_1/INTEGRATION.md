# Quote Form integration

The form is standalone and does not include email, PDF, Data1, approval, or quote history.

## Simplest Quote-button connection (same browser)

Before opening the form, save the calculator result in session storage:

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

sessionStorage.setItem('cylinderQuoteDraft', JSON.stringify(quoteData));
window.location.href = 'quote_form_output/quote_form.html';
```

## New-tab connection

```javascript
const quoteWindow = window.open('quote_form_output/quote_form.html', 'cylinderQuote');
window.addEventListener('message', (event) => {
  if (event.data?.type === 'QUOTE_FORM_READY') {
    quoteWindow.postMessage({ type: 'CYLINDER_QUOTE_DATA', payload: quoteData }, '*');
  }
});
```

## Direct function connection

When the form is embedded or its page is already open:

```javascript
window.populateQuoteForm(quoteData);
// or: window.CylinderQuoteForm.populate(quoteData)
```

Every editable field has a stable HTML id. The form accepts those ids directly and also common aliases such as
`customer`, `quoteNumber`, `qty`, `model`, `listPrice`, `netPrice`, `push`, `pull`, and `notes`.
