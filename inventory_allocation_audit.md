# Inventory allocation audit

Source workbook: 2026 JIT Order Entry V3.xlsm

## Scope

- 847 populated Inventory rows
- 834 allocation formulas
- 60 length-based formulas
- 680 quantity or option formulas
- 94 helper-sheet or other formulas
- 13 populated rows without an allocation formula

## Excel processing sequence

1. Order Entry controls write selections and quantities into the Data sheet.
2. Every Inventory row evaluates its allocation formula in column E.
3. Inventory is sorted by Allocated, descending.
4. Rows with Allocated greater than 0.1 are copied from Inventory columns A:E into Order Form columns C:G.
5. Order Form Cost is replaced with Allocated multiplied by Unit Price.
6. Parts Total sums the extended Cost values.
7. On approval/shipment, remaining Inventory is calculated as On Hand minus Allocated.

## Main input drivers

- Data B2: cylinder quantity
- Data B3: series
- Data B4: bore
- Data B5: mount
- Data B6: rod diameter
- Data B7: cushion
- Data B8: stroke
- Data B10: seal material
- Data B11:B27: extensions and special options
- Data G9:G22: accessory quantities
- Data F26:G32: manually selected special parts and quantities

## Required HTML calculation model

Each generated part must contain part number, description, unit cost, on-hand quantity, allocated quantity, extended cost, and unit of measure. The Order Form Cost field must receive extended cost, not unit cost.

## Known source anomalies requiring a decision

- Eight of the nine stainless-steel tie-rod formulas omit the normal four-rod multiplier; TRSS031 includes it.
- Thirteen populated head rows have a hard-coded allocation of zero.
- The workbook only copies the first 31 allocated rows to the Order Form after sorting.
- Several formulas reference helper sheets, especially H and Acc, so those lookup tables must be ported rather than replaced with guessed part numbers.
