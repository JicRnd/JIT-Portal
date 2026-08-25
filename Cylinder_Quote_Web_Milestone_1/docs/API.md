# Milestone 1 API Contract

## GET /api/health
Returns engine availability.

## GET /api/catalog
Returns valid Series -> Bore -> Rod -> Mount combinations plus accessory names, special part numbers, cushions, ports, seals, and rod styles used by the browser form.

## POST /api/calculate
Accepts one quote configuration as JSON and returns the frozen Pricing Engine v1.2 `PriceBreakdown`.

Required fields: `series`, `bore`, `rod_diameter`, `mount`, `stroke`.

Optional fields include cushion, port/seal codes, rod style, discount, DRE, modification quantities/flags, position-sensing flags, accessories, special parts, and Standard Rod Boot quantity.

All currency/decimal results are returned as strings to avoid floating-point loss in JSON.
