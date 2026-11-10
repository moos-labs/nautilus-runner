#!/usr/bin/env python3
# -------------------------------------------------------------------------------------------------
#  Based on the NautilusTrader project's own example (LGPL-3.0):
#  examples/backtest/fx_ema_cross_audusd_ticks.py at release tag v1.231.0
#  https://nautechsystems.io -- Copyright (C) 2015-2026 Nautech Systems Pty Ltd.
# -------------------------------------------------------------------------------------------------
"""
NautilusTrader official example backtest, run end-to-end (v1.231.0).

This is the project's own example ``fx_ema_cross_audusd_ticks.py`` from
release v1.231.0 of the nautilus_trader GitHub repository, with only the
minimal adaptations needed to run it non-interactively from the pip
package in CI:

1. The interactive ``time.sleep(0.1)`` + ``input("Press Enter...")``
   pause in the original is removed (it would hang a CI runner forever).
2. The project's own packaged test data (``truefx/audusd-ticks.csv`` and
   ``short-term-interest.csv`` from ``tests/test_data`` at tag v1.231.0)
   is downloaded up front into the exact local directory that
   ``TestDataProvider`` checks first. Without this, the provider falls
   back to pulling the same files through the GitHub API via fsspec,
   which is anonymously rate-limited and unreliable in CI. The data is
   still the project's own sample data, from the project's own repo, at
   the tag matching the installed package version.
3. After ``engine.run()``, the engine's own reports (account, order
   fills, positions) are printed exactly as in the original AND saved
   under ``results/``; a summary quoting the account report's first and
   last rows is written to ``results/nautilus_result.md``. No figures
   are computed by this script beyond counting the rows of the engine's
   own fills/positions reports and reading the first/last balance rows
   of the engine's own account report.

Strategy: the project's own ``EMACross`` example strategy, imported from
the installed package (``nautilus_trader.examples.strategies.ema_cross``)
exactly as the original example does.
"""

import urllib.request
from decimal import Decimal
from pathlib import Path

import pandas as pd

import nautilus_trader
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.backtest.modules import FXRolloverInterestConfig
from nautilus_trader.backtest.modules import FXRolloverInterestModule
from nautilus_trader.examples.strategies.ema_cross import EMACross
from nautilus_trader.examples.strategies.ema_cross import EMACrossConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import QuoteTickDataWrangler
from nautilus_trader.test_kit.providers import TestDataProvider
from nautilus_trader.test_kit.providers import TestInstrumentProvider


RELEASE_TAG = "v1.231.0"
TEST_DATA_FILES = [
    "short-term-interest.csv",
    "truefx/audusd-ticks.csv",
]


def ensure_test_data() -> None:
    """
    Download the project's own packaged test data (tag v1.231.0) into the
    local directory TestDataProvider checks first:
    <site-packages>/tests/test_data/ (sibling of the nautilus_trader package).
    """
    package_parent = Path(nautilus_trader.__file__).resolve().parent.parent
    test_data_dir = package_parent / "tests" / "test_data"
    base_url = (
        "https://raw.githubusercontent.com/nautechsystems/nautilus_trader/"
        f"{RELEASE_TAG}/tests/test_data"
    )
    for rel_path in TEST_DATA_FILES:
        dest = test_data_dir / rel_path
        if dest.exists() and dest.stat().st_size > 0:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"{base_url}/{rel_path}"
        print(f"Downloading packaged test data: {url} -> {dest}")
        urllib.request.urlretrieve(url, dest)


if __name__ == "__main__":
    ensure_test_data()

    # Configure backtest engine
    config = BacktestEngineConfig(
        trader_id=TraderId("BACKTESTER-001"),
    )

    # Build the backtest engine
    engine = BacktestEngine(config=config)

    # Firstly, add a trading venue (multiple venues possible)
    # Create a fill model (optional)
    fill_model = FillModel(
        prob_fill_on_limit=0.2,
        prob_slippage=0.5,
        random_seed=42,
    )

    # Optional plug in module to simulate rollover interest,
    # the data is coming from packaged test data.
    provider = TestDataProvider()
    interest_rate_data = provider.read_csv("short-term-interest.csv")
    config = FXRolloverInterestConfig(interest_rate_data)
    fx_rollover_interest = FXRolloverInterestModule(config=config)

    # Add a trading venue (multiple venues possible)
    SIM = Venue("SIM")
    engine.add_venue(
        venue=SIM,
        oms_type=OmsType.HEDGING,  # Venue will generate position IDs
        account_type=AccountType.MARGIN,
        base_currency=USD,  # Standard single-currency account
        starting_balances=[Money(1_000_000, USD)],  # single-currency or multi-currency accounts
        fill_model=fill_model,
        modules=[fx_rollover_interest],
    )

    # Add instruments
    AUDUSD_SIM = TestInstrumentProvider.default_fx_ccy("AUD/USD", SIM)
    engine.add_instrument(AUDUSD_SIM)

    # Add data
    wrangler = QuoteTickDataWrangler(instrument=AUDUSD_SIM)
    ticks = wrangler.process(provider.read_csv_ticks("truefx/audusd-ticks.csv"))
    engine.add_data(ticks)

    # Configure your strategy
    strategy_config = EMACrossConfig(
        instrument_id=AUDUSD_SIM.id,
        bar_type=BarType.from_str("AUD/USD.SIM-100-TICK-MID-INTERNAL"),
        trade_size=Decimal(1_000_000),
        fast_ema_period=10,
        slow_ema_period=20,
        close_positions_on_stop=True,
    )
    # Instantiate and add your strategy
    strategy = EMACross(config=strategy_config)
    engine.add_strategy(strategy=strategy)

    # (Original example pauses here for an interactive "Press Enter" prompt;
    # removed for CI -- see module docstring.)

    # Run the engine (from start to end of data)
    engine.run()

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    # Optionally view reports
    with pd.option_context(
        "display.max_rows",
        100,
        "display.max_columns",
        None,
        "display.width",
        300,
    ):
        account_report = engine.trader.generate_account_report(SIM)
        fills_report = engine.trader.generate_order_fills_report()
        positions_report = engine.trader.generate_positions_report()

        print(account_report)
        print(fills_report)
        print(positions_report)

    # Save the engine's own reports verbatim as text files.
    (results_dir / "account_report.txt").write_text(
        account_report.to_string() + "\n", encoding="utf-8",
    )
    (results_dir / "order_fills_report.txt").write_text(
        fills_report.to_string() + "\n", encoding="utf-8",
    )
    (results_dir / "positions_report.txt").write_text(
        positions_report.to_string() + "\n", encoding="utf-8",
    )

    n_fills = len(fills_report)
    n_positions = len(positions_report)
    # The account report is the engine's own balance time series: quote its
    # first and last rows exactly as reported.
    first_balance = account_report.iloc[0]
    last_balance = account_report.iloc[-1]

    summary = f"""# NautilusTrader — official example backtest result

- **Example run:** the project's own `examples/backtest/fx_ema_cross_audusd_ticks.py`
  at release tag **v1.231.0** (the installed `nautilus_trader` version), with the
  minimal CI adaptations documented in `scripts/nautilus_example.py`.
- **Strategy:** the project's own example strategy `EMACross`
  (`nautilus_trader.examples.strategies.ema_cross`), fast EMA 10 / slow EMA 20,
  trade size 1,000,000, as configured in the official example.
- **Data:** the project's own packaged test data — TrueFX AUD/USD quote ticks
  (`tests/test_data/truefx/audusd-ticks.csv` at tag v1.231.0), loaded via
  `TestDataProvider.read_csv_ticks` and `QuoteTickDataWrangler`, exactly as in
  the official example; plus the packaged `short-term-interest.csv` used by the
  example's FX rollover interest module.
- **Instrument traded:** {AUDUSD_SIM.id} (venue SIM, margin account, USD base)

## Figures exactly as the engine reported them

- **Order fills (rows in the engine's own order fills report):** {n_fills}
- **Positions (rows in the engine's own positions report):** {n_positions}
- **Account report first row:** index `{first_balance.name}`, total = {first_balance["total"]} {first_balance["currency"]}
- **Account report last row:** index `{last_balance.name}`, total = {last_balance["total"]} {last_balance["currency"]}

## Engine account report (verbatim)

Full report saved in `account_report.txt`. First and last rows:

```text
{account_report.iloc[[0]].to_string()}
{account_report.iloc[[-1]].to_string()}
```

## Engine order fills report

Full report saved in `order_fills_report.txt` ({n_fills} rows).

## Engine positions report

Full report saved in `positions_report.txt` ({n_positions} rows).

All figures above are quoted exactly as the NautilusTrader BacktestEngine
reported them; nothing was recomputed by this script beyond counting the
rows of the engine's own fills/positions reports and reading the first/last
rows of the engine's own account report.
"""
    (results_dir / "nautilus_result.md").write_text(summary, encoding="utf-8")
    print(summary)

    # For repeated backtest runs make sure to reset the engine
    engine.reset()

    # Good practice to dispose of the object when done
    engine.dispose()
