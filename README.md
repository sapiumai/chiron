# Chiron

Chiron is an internal, single-operator stock analysis tool built on a fork
of [TradingAgents](https://github.com/TauricResearch/TradingAgents) — a
multi-agent LLM pipeline that runs Market, Sentiment, News, and Fundamentals
analysts through a Bull/Bear debate into a Portfolio Manager recommendation.

TradingAgents serves Swing-trading well on its own, but every analysis
recomputes from scratch on each run and it has no visibility into chart
patterns or into how a macro/sector event ripples into a stock whose own
news doesn't mention it. Chiron closes both gaps, so the same pipeline can
serve Day-trading alongside Swing:

- **Persistent, change-keyed cache** — a Postgres-backed cache behind every
  Analysis Domain (Price, Chart, Earnings, News, Graph), invalidated only
  when the underlying data actually changed, not on a fixed schedule.
- **Chart / Candlestick Pattern Analyst** — a new Analyst Node reading the
  Price Domain's cached OHLCV data for technical/candlestick signals.
- **Entity-Relationship Graph Analyst** — a new Analyst Node that propagates
  macro/commodity/sector signals to individual stocks via a curated mapping
  (e.g. oil → PETR4.SA), even when a stock's own news stays silent on the
  event.
- **Per-stock earnings calendar** — drives the Fundamentals Domain's refresh
  around each stock's actual report date instead of a guessed interval.
- **Strategy-weighted, read-time recommendation** — an on-demand request
  specifies Day or Swing; all five Domains' cached signals are read every
  time, weighted differently per Strategy, and combined fresh at request
  time (never itself stored).

This is decision support, not trade execution — Chiron produces a
recommendation and output file for a human to read, not an order.

## Status

Under active development. Epic 1 (this fork + the cache/trigger foundation)
is in progress; see `_bmad-output/planning-artifacts/epics.md` for the full
epic/story breakdown and `_bmad-output/implementation-artifacts/` for
current sprint status.

## Provenance

The `tradingagents/`, `cli/`, `tests/`, and related source files in this
repo are a clean-copy fork of TradingAgents (no imported git history) — see
[NOTICE](NOTICE) for the upstream commit and license terms.

## Getting started

See TradingAgents' own setup for the underlying pipeline: create a venv,
install with `pip install -e .`, copy `.env.example` to `.env` and set the
relevant provider API key(s) and `TRADINGAGENTS_*` overrides, then run:

```bash
python main.py
```

Chiron's own cache/worker/entry-point layer (Postgres, Domain workers, the
on-demand request surface) is being built out story by story on top of this
baseline — this README will grow a dedicated usage section once that
surface exists.
