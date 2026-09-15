---
name: excel-workbook-analysis
description: "Use when analyzing an Excel or XLSM workbook to reproduce workbook behavior in the application, including reading sheets, formulas, cached values, named ranges, lookup tables, hidden calculation areas, cross-sheet dependencies, engineering outputs, and converting verified results into normalized runtime data without loading Excel at runtime."
---

# Excel Workbook Analysis

Use this skill when a workbook is the authoritative source for a business rule, engineering calculation, display value, lookup table, or form output.

## Core rule

Treat the workbook as a read-only source artifact. Extract and verify its behavior, then reproduce the needed behavior in application code or normalized data. Do not add the workbook, Excel automation, cell-address lookups, or formula evaluation as a runtime dependency unless the user explicitly requests that architecture.

## Required workflow

1. Identify the exact workbook and the application surface that must reproduce it.
2. Read the workbook with `openpyxl` using `keep_vba=True` for `.xlsm` files.
3. Load it twice:
   - `data_only=False` to inspect formulas and source structure;
   - `data_only=True` to inspect cached/displayed results when available.
4. Record the workbook sheet names, including hidden sheets when relevant.
5. Start from the visible output cell or form row and trace its dependencies backward.
6. Inspect only the controlling ranges first. Expand to neighboring rows, columns, tables, or sheets when a formula references them.
7. For every important output, record:
   - visible sheet and cell/range;
   - exact formula;
   - source input cells;
   - lookup table or selector conditions;
   - cached result, if present;
   - equivalent application field and runtime representation.
8. Compare at least one known workbook scenario against the application using the same inputs.
9. Normalize the result into JSON, CSV, Python data, or application constants as appropriate.
10. Add or update a focused regression check for the extracted scenario.

## Practical inspection pattern

Use a read-only Python command similar to this for targeted inspection:

```python
import openpyxl

path = r"path\to\workbook.xlsm"
formulas = openpyxl.load_workbook(path, keep_vba=True, data_only=False)
values = openpyxl.load_workbook(path, keep_vba=True, data_only=True)

print(formulas.sheetnames)
for sheet_name, cells in {
    "Order Form": ["E49", "G48"],
    "H": ["AC7", "AD7", "AE7"],
    "Data": ["AN1", "D27"],
}.items():
    for address in cells:
        print(
            sheet_name,
            address,
            "formula=", formulas[sheet_name][address].value,
            "cached=", values[sheet_name][address].value,
        )
```

When inspecting a range, print only non-empty cells with coordinates and values. For a large sheet, search formulas for references to the known input cells or output cells before dumping more data.

## Dependency tracing

For a visible form output, trace in this order:

- visible output cell;
- formula references to another sheet or helper cell;
- selector rows that choose a matching bore, rod, mount, series, cushion, or style;
- source tables containing constants;
- input cells and their labels.

Pay special attention to formulas that use:

- `IF`, `IFERROR`, `OR`, and `AND` selector gates;
- `SUM` across hidden helper rows;
- `VLOOKUP`, `XLOOKUP`, `INDEX`, and `MATCH`;
- `CONCATENATE` or `&` display formatting;
- hidden columns or far-right helper tables;
- named ranges and defined names;
- workbook formulas whose cached values are absent because openpyxl does not calculate Excel formulas.

A formula's cell address is provenance, not an application API. Preserve the rule and meaning, not the address.

## Cached values and formula limitations

`openpyxl` does not calculate formulas. A missing cached value is not proof that the workbook output is blank. When cached values are absent:

- inspect the formula and its precedents;
- inspect equivalent populated rows or lookup tables;
- use a known workbook scenario and calculate the result independently;
- do not silently substitute zero;
- report when a result depends on Excel recalculation or an unavailable external link.

If LibreOffice, Excel automation, or another recalculation tool is available, use it only for validation of a copy or a temporary read-only artifact. Do not make it part of the application runtime without explicit approval.

## Normalization guidance

Prefer semantic fields such as:

```json
{
  "series": ["H", "HM"],
  "bore": 5,
  "rod": 2,
  "mounts": ["MX0"],
  "rod_length_addition": 8.73,
  "barrel_length_addition": 2.688,
  "tie_rod_length_addition": 8,
  "torque_ft_lbs": 300,
  "weight_base": 82,
  "weight_per_stroke": 3.4
}
```

Keep source provenance in extracted data when useful, but do not require the runtime code to know the source cell. Separate:

- selector inputs;
- engineering numeric outputs;
- display formatting;
- source/provenance metadata.

For display outputs, preserve workbook conventions such as decimal precision, dash-for-blank behavior, units, thread text, and concatenated labels.

## Validation checklist

Before finishing workbook-derived work:

- verify the workbook path and sheet names;
- verify formula text and cached values separately;
- verify the relevant selector conditions;
- verify at least one exact known scenario;
- verify normalized data parses successfully;
- run JavaScript syntax, Python tests, or the narrowest available executable check;
- confirm the application does not load the workbook at runtime;
- mention unresolved formulas or incomplete rule families instead of inventing values.

## Scope discipline

Do not rewrite the pricing engine or unrelated workbook logic. Keep extraction and application changes limited to the requested output surface. If the workbook contains multiple product families, normalize one verified family at a time and keep unsupported families explicit rather than applying a guessed fallback.
