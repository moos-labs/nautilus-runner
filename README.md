# nautilus-runner

Runs [NautilusTrader](https://nautechsystems.io) analyses via GitHub Actions —
commands supplied through the `COMMANDS` repository variable.

## Pattern

- `.github/workflows/run.yml` triggers on `workflow_dispatch` **only**.
- It sets up Python 3.11, installs `requirements.txt`, then runs a step named
  **"Run commands"** whose run line is exactly `run: ${{ vars.COMMANDS }}`.
- A final step always uploads `results/` as the `results` artifact
  (`actions/upload-artifact@v4`, `if: always()`).
- The `COMMANDS` repository variable for the pilot is:

  ```text
  mkdir -p results
  set -o pipefail; python scripts/nautilus_example.py 2>&1 | tee results/run.log
  ```

  To run something else, change the `COMMANDS` variable — no workflow edit
  needed. Scripts live in `scripts/` and write their outputs into `results/`.

## Pilot: NautilusTrader's own example backtest

`scripts/nautilus_example.py` runs the project's own example
`examples/backtest/fx_ema_cross_audusd_ticks.py` at release tag **v1.221.0**
(matching the pinned `nautilus_trader==1.221.0` in `requirements.txt`):

- Strategy: the project's own example strategy `EMACross`, imported from the
  installed package (`nautilus_trader.examples.strategies.ema_cross`) —
  fast EMA 10 / slow EMA 20 on 100-tick MID bars, trade size 1,000,000.
- Instrument: `AUD/USD.SIM` on a simulated margin venue, starting balance
  1,000,000 USD, with the example's `FillModel` (seed 42) and its
  FX rollover interest module.
- Data: the project's own packaged test data — TrueFX AUD/USD quote ticks
  (`tests/test_data/truefx/audusd-ticks.csv`) plus `short-term-interest.csv`,
  loaded via `TestDataProvider` and `QuoteTickDataWrangler` exactly as in
  the official example.

Outputs in `results/`:

- `nautilus_result.md` — summary quoting the engine's own reports
- `account_report.txt` — the engine's account report, verbatim
- `order_fills_report.txt` — the engine's order fills report, verbatim
- `positions_report.txt` — the engine's positions report, verbatim
- `run.log` — full console log of the run

## Honest notes (adaptations from the verbatim example)

0. **Version pinned to 1.221.0 because the pattern uses Python 3.11.**
   Newer releases (1.222.0+) declare `Requires-Python >=3.12`, so pip on
   the workflow's Python 3.11 cannot install them (verified: the first
   dispatch with 1.231.0 failed at the install step for exactly this
   reason). 1.221.0 is the newest release installable on Python 3.11, and
   its example differs from 1.231.0's only by one extra `FillModel`
   argument (`prob_fill_on_stop=0.95`), which this runner includes.

1. **Interactive prompt removed.** The original example pauses with
   `time.sleep(0.1)` + `input("Press Enter to continue...")`, which would
   hang a CI runner forever. That pause is removed; nothing else about the
   backtest setup was changed.
2. **Test data is pre-downloaded from the project's own repo.** When the
   packaged `tests/test_data` directory is absent (always the case for a
   pip install), `TestDataProvider` falls back to pulling the files through
   the GitHub API via fsspec, which is anonymously rate-limited (a local
   trial of the unmodified route failed with `403 rate limit exceeded`).
   The script therefore downloads the same two CSV files from
   `raw.githubusercontent.com/nautechsystems/nautilus_trader/v1.221.0/tests/test_data/`
   into the exact local directory the provider checks first. Same project,
   same files, same release tag as the installed package.
3. **Version matters.** NautilusTrader's API changes between releases
   (e.g. the current development branch renames `test_kit` to `testkit`
   and restructures the examples). This runner is pinned to v1.221.0 and
   its example, verified end-to-end before dispatch.
4. **No invented numbers.** Every figure in `nautilus_result.md` is quoted
   from the BacktestEngine's own reports; the script only counts the rows
   of the fills/positions reports and reads the first/last rows of the
   account report.
