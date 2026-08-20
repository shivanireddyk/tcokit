# tcokit

Total cost of ownership modelling for medium and heavy duty vehicles, with the
policy levers that actually decide the answer.

[![CI](https://github.com/shivanireddyk/tcokit/actions/workflows/ci.yml/badge.svg)](https://github.com/shivanireddyk/tcokit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A fleet operator deciding whether to buy an electric truck, and a transport
ministry deciding what it would take to make them, are asking the same question
with different levers. Neither decides on emissions. They decide on whether the
numbers work.

This library answers that question and shows its working.

## The question it answers

```bash
pip install -e ".[dev]"
python demo.py
```

```
Class 8 battery electric tractor is MORE EXPENSIVE over the period
Region: United States, national average    Policy: No policy support

  Purchase price                      $350,000
  Charging infrastructure             $120,000
  Energy                              $179,804
  Maintenance                          $61,808
  Electricity demand charges           $63,212
  Residual value                      -$26,688
  Net present cost                    $839,442
  Cost per mile                         1.049

  Difference                          $180,841
  Breakeven                   not within period

  Smallest purchase incentive that would flip this: $181,000
```

That last line is the point. "It costs more" is not useful to a policymaker.
"It costs $180,841 more, and $181,000 of purchase support closes the gap" is
something a ministry can act on.

Switch the policy on and the same vehicles in the same region cross over in
**year 6**, with diesel price and electric purchase price both flagged as
assumptions that would change the recommendation on their own.

## Three design decisions

**Parameters are data, not code.** Fuel prices, incentives and vehicle figures
live in YAML. A new country is a new file, not a new codebase:

```yaml
region:
  name: Colombia, Bogota to Cartagena corridor
  diesel_price_per_gallon: "3.20"
  electricity_price_per_kwh: "0.11"

policy:
  name: Import duty relief only
  purchase_incentive: "25000"
```

Three scenarios ship with the library: a US Class 8 baseline, the same case
with vouchers, a feebate and a carbon tax, and a Colombian freight corridor.
Running the first two against each other isolates what policy alone does,
because everything except the policy block is identical, and there is a test
asserting exactly that.

**Decimal, never float.** A diesel price of $3.85 is not representable in
binary. Over ten years of discounted cash flows that error compounds, and
"small" is not a property you want to explain when two runs of the same
scenario differ. Floats are rejected at the boundary, in the API and in the
scenario files, where `3.85` raises and `"3.85"` is accepted.

**Units are a correctness problem.** Diesel is priced per gallon and consumed
in miles per gallon, so cost per mile is a quotient. Electricity is priced per
kilowatt hour and consumed in kilowatt hours per mile, so it is a product.
Those are reciprocal, and inverting one produces a plausible wrong number:
$0.16/kWh at 2.0 kWh/mile is 32 cents a mile, not 8. There is a test named for
that mistake.

## Policy levers

Each is applied at a different point in the cash flow, which is why they cannot
be collapsed into one subsidy figure:

| Lever | Where it lands |
|---|---|
| Purchase incentive | Year 0 capital, undiscounted |
| Charger cost share | Year 0 infrastructure capital |
| Feebate | Fee on diesel purchase, rebate on electric |
| Road user charge | Per mile, annually, targetable by powertrain |
| Carbon tax | Per gallon burned, so it never touches the electric case |

A purchase incentive is worth its full face value; a per-mile charge is worth
less than its undiscounted sum. That asymmetry is usually the whole argument.

Incentives are capped at the capital they offset. Without that cap an
over-generous lever shows the operator being paid to accept the truck, which is
not a result anyone would recognise.

## Sensitivity, because one number is never the answer

`tornado()` varies each input above and below its stated value, holds the rest,
and orders the results by how far the answer moves. It flags any input whose
range **changes the recommendation**, not just its size.

Levers set to zero are omitted rather than reported with a swing of zero: a
lever that is switched off is a different finding from one that does not matter.

`incentive_to_breakeven()` searches for the smallest purchase incentive that
flips the decision. It steps rather than solving algebraically because the
incentive cap makes the relationship piecewise.

## Reading a result

Nothing returns a bare number. Every result carries its component lines, its
year by year cash flow, and the cumulative discounted series that produces the
breakeven year. `as_record()` returns the same thing as JSON, with money as
strings so it survives a round trip.

When the vehicles never cross over, `breakeven_year` is `None` and the report
says so in words. Extrapolating past the horizon the user asked about would be
inventing a number.

## Testing

69 tests, 97% line coverage, run on Python 3.10 through 3.12.

The ones that carry weight are the unit reciprocal, the incentive cap, the
carbon tax touching diesel only, the road user charge targeting one powertrain,
breakeven returning `None` honestly, and a test asserting that the two US
scenarios differ **only** in their policy block.

One test documents a real numerical detail: at a zero discount rate, ten
divisions summed and one multiplication agree to about 1e-22 of a dollar rather
than bit for bit. The test asserts equality to the cent, which is the honest
claim and the precision anyone relies on.

```bash
pytest -q
pytest --cov=tcokit --cov-report=term-missing
```

## Scope, and what the numbers are not

The shipped figures are order-of-magnitude public reference values chosen to
demonstrate the model. **They are not sourced analysis.** Before using output
for anything real, replace them with cited figures and record the source beside
each line. The contribution here is the engine and its discipline; the inputs
are the analyst's responsibility, and the scenario files say so.

Deliberately out of scope for this version: battery degradation and replacement,
resale markets modelled beyond a residual fraction, grid emissions accounting,
depot versus opportunity charging profiles, and multi-vehicle fleet rollout.
Each is real and each would need its own data before it earned a place here.

## License

MIT. See [LICENSE](LICENSE).
