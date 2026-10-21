# deliverable-check · Pre-delivery checks

> Three checkers for three kinds of deliverable that look fine and are not:
> **does the proposal hold up**, **how much of the draft is AI slop and how much did it really change**,
> **is the spreadsheet safe to send before someone sums the wrong column**.

Everything here is a **re-runnable measurement**, not a score.

| Tool | Question it answers | Output |
|---|---|---|
| [`tools/measure_proposals.py`](tools/measure_proposals.py) | How much skeleton, evidence and assertion does this proposal carry? | Baseline JSON + [report](docs/proposal-baseline.md) |
| [`tools/measure_ai_flavor.py`](tools/measure_ai_flavor.py) | Which markers actually decline across drafts? What did 21 versions change? | Marker density + [rework curve](docs/ai-flavor.md) |
| [`tools/audit_data.py`](tools/audit_data.py) | Will this spreadsheet be summed wrong downstream? | Blocking/warning list + [report](docs/data-audit.md), `exit 1` for CI |

---

## Quick start

```bash
python3 tools/measure_proposals.py --out docs/proposal-baseline.json <proposal-dir>
python3 tools/measure_ai_flavor.py  --out docs/ai-flavor.json <dir-with-versions>
python3 tools/audit_data.py 交付表.xlsx --key-col 订单号
```

`audit_data` needs `openpyxl`; the other two use the standard library only.

---

## Three findings, measured on a real corpus

1. **The proposal's information lives in tables.** Across 34 full proposals: median 3,517 CJK chars,
   12 H2 sections, **182 table rows**, **82.5 numbers per 1,000 chars** — yet only **32%** define acceptance
   metrics and **6%** state any pricing.
2. **Rework concentrates in the first 30% of versions.** One design document went through 21 versions and grew
   141%; the first six edits averaged 5.1%, the last fourteen only 1.7%. Past version 8, line-editing buys little.
3. **"Ban the em dash" is wrong.** Across those 21 versions em-dash density rose **49%**, while buzzword density
   fell **45%** and mean sentence length fell **36%**. Calibrate the rule against data, not fashion.

---

## What the spreadsheet audit catches

On a deliberately dirty workbook ([generated, not committed](tools/make_dirty_fixture.py)):

```
⛔ 2 subtotal/total rows inside the detail area
⛔ 6 cells are thousand-separated text numbers
⛔ "Amount" column sums to 2.76x the true value
⛔ "Amount" total row disagrees with the detail sum by 20,500.50
   verdict: not deliverable      (exit code 1)
```

On a real P&L workbook it reports **zero blockers** — summary layouts are downgraded rather than flagged.
Not crying wolf matters as much as not missing the wolf.

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

25 cases: the three accident classes, clean-workbook silence, ratio-column skipping, marker counting,
version ordering and rework math.

---

## Limits

- The proposal baseline is **our own corpus** (6 projects), not an industry sample; versions are not deduplicated.
- The AI-flavor tool reports **signals**, not "does this read human". The experience layer cannot be measured —
  it has to be supplied by a person.
- The spreadsheet audit covers `.xlsx` only and only mechanically decidable defects.

---

## Related

- **[devflow-kit](https://github.com/darkknight110/devflow-kit)** — makes "must pass gates before delivery" a process; this tool's `exit 1` plugs straight in.
- **[md-to-office](https://github.com/darkknight110/md-to-office)** — turns the proposal into Word/PDF with real diagrams instead of ASCII art.

MIT.
