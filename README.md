<div align="center">

# 📈 KJStockScreener

### AI-Native Stock Screener for the Indian Stock Market (NSE)

**Find breakouts. Chat with an AI trading agent. Explore company fundamentals. Track live option chains. All in one Streamlit app.**

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/85599/KJStockScreener?style=for-the-badge)](https://github.com/85599/KJStockScreener/releases/latest)
[![GitHub all releases](https://img.shields.io/github/downloads/85599/KJStockScreener/total?color=Green&label=Downloads&style=for-the-badge)](https://github.com/85599/KJStockScreener/releases)
[![Docker Pulls](https://img.shields.io/docker/pulls/callmejainsahab/kjstockscreener?style=for-the-badge&logo=docker)](https://hub.docker.com/r/callmejainsahab/kjstockscreener)
[![GitHub](https://img.shields.io/github/license/85599/KJStockScreener?style=for-the-badge)](https://github.com/85599/KJStockScreener/blob/main/LICENSE)
[![MADE-IN-INDIA](https://img.shields.io/badge/MADE%20WITH%20%E2%9D%A4%20IN-INDIA-orange?style=for-the-badge)](https://en.wikipedia.org/wiki/India)

[![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](#)
[![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)](#)
[![Mac OS](https://img.shields.io/badge/mac%20os-D3D3D3?style=for-the-badge&logo=apple&logoColor=000000)](#)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](#)

**⭐ If KJStockScreener helps your trading workflow, please star the repo — it genuinely helps the project grow!**

[Quick Start](#-quick-start) · [Features](#-features) · [AI Agent Setup](#-ai-native-mode-setup) · [Screenshots](#️-screenshots) · [Contributing](#-contributing)

</div>

---

## What is KJStockScreener?

**KJStockScreener** is a Python + Streamlit screener for **NSE (India)** stocks that goes beyond a typical breakout scanner. On top of a classic multi-threaded technical screening engine (breakouts, consolidation, RSI, moving-average crossovers, candlestick patterns), v3.0.2 adds an **AI-native trading agent**, a **live NSE option chain viewer**, an **ML-based Nifty gap-up/gap-down predictor**, and **LedgerLens** — a built-in fundamentals explorer that pulls a company's full financials, ratios, and filings straight from screener.in — all inside one self-contained web app.

Whether you want to run a classic rule-based scan in two clicks, or *ask a chatbot in plain English* to "find me swing setups in Nifty 500 with RSI between 50 and 65," KJStockScreener has a mode for it.

## ✨ Features

### 🔍 Classic Screening Engine
- Multi-process, multi-threaded scanning across NSE indices (Nifty 50 up to Nifty 500 / F&O universe)
- Breakout & consolidation detection with configurable lookback and volume-ratio filters
- Candlestick pattern recognition (Bullish/Bearish Engulfing, Inside Bar, Momentum Gainer, and more)
- MA/EMA crossover signals (50/200 Golden Cross, support/resistance zones)
- RSI-based reversal screening (9-SMA of RSI)
- Lorentzian Classification model for higher-accuracy setups
- Excel-style column filters on the results table, one-click export to Excel

### 🤖 AI-Native Mode
- A conversational chat tab (OpenWebUI-style UI) backed by [`openai-agents`](https://github.com/openai/openai-agents-python) — talk to your screener instead of clicking through menus
- Works with **OpenAI, Anthropic, Groq, and any OpenAI-compatible endpoint** — bring your own API key
- **5 built-in trading personas** you can pick or extend, each with its own strategy and toolset:
  - `SwingTrader` — 3–10 day breakout setups from consolidation bases
  - `MomentumAnalyst` — high-momentum Nifty 500 trend continuations
  - `OptionBuyer` — directional F&O option-buying opportunities
  - `ValueScreener` — long-term value & quality picks from Nifty 200
  - `KhushalJain` — Nifty 50 technical-analysis persona
- Cron-style **scheduled agent runs** so a persona can scan the market for you automatically
- Optional **Zerodha Kite MCP** integration for live broker-connected market data inside chat

### 📊 Live Option Chain
- Real-time NSE option chain for NIFTY, BANKNIFTY, and any F&O stock
- One-click "View" on every CE/PE strike to open that exact contract on TradingView

### 🧠 ML-Powered Gap Prediction
- A trained model predicts next-day Nifty gap-up/gap-down using Nifty, Gold, and Crude price action
- Ships as a pure NumPy `.npz` weights file — **no TensorFlow dependency**, works out of the box on Python 3.13

### 📒 LedgerLens — Fundamentals Explorer
- Pulls a company's complete fundamentals straight from screener.in: quarterly results, P&L, balance sheet, cash flow, ratios, shareholding pattern, peer comparison, pros/cons, and documents (annual reports, credit ratings, concall transcripts)
- Search by name or symbol, pick Consolidated/Standalone, choose which sections to pull
- Auto-generated Sales vs Net Profit chart per company
- Download any section as CSV, the full summary as JSON, or everything at once as a ZIP (JSON + CSV + Excel per section)

### 🧰 Everything Else You'd Expect
- Portfolio & watchlist tracking, position-size calculator
- Vector-similarity "Search Similar Stocks"
- Dockerized — one command to run, no local Python setup needed
- Cross-platform: Windows, Linux, macOS (including Apple Silicon), amd64/arm64

## 🖼️ Screenshots

<p align="center">
  <img width="1200" alt="KJStockScreener classic screening tab" src="screenshots/classic-screening.png">
</p>
<p align="center">
  <img width="1200" alt="KJStockScreener screening results" src="screenshots/ai-native-chat.png">
</p>
<p align="center">
  <img width="1200" alt="KJStockScreener additional view" src="screenshots/option-chain.png">
</p>
<p align="center">
  <img width="1200" alt="KJStockScreener configuration" src="screenshots/config.png">
</p>

## 🚀 Quick Start

### Option 1 — Docker (recommended)

```bash
docker pull callmejainsahab/kjstockscreener:latest
docker run -p 8501:8501 -p 8000:8000 callmejainsahab/kjstockscreener:latest
```

Then open **http://localhost:8501** in your browser.

Prefer the CLI mode instead of the web UI?

```bash
docker run -it --entrypoint /bin/bash callmejainsahab/kjstockscreener:latest -c "run_kjscreener.sh --cli"
```

### Option 2 — Run from source

```bash
git clone https://github.com/85599/KJStockScreener.git
cd KJStockScreener
pip install -r requirements.txt
./run_kjscreener.sh --gui      # Streamlit web UI
./run_kjscreener.sh --cli      # Classic terminal UI
```

> Requires Python 3.13. See `pyproject.toml` for the full dependency list.

## 🤖 AI-Native Mode Setup

1. Open the **AI Native** tab inside the app.
2. Add your LLM API key (OpenAI / Anthropic / Groq / any OpenAI-compatible provider) — it's kept in your browser's local storage or as a session-only key, your choice.
3. Pick a persona, or just start chatting — e.g. *"Screen Nifty 500 for swing setups near breakout with RSI 50–65."*

Advanced configuration (LLM provider/model, Kite MCP, scheduled runs) lives in `KJScreener.yaml` at the repo root:

```yaml
kite_mcp:
  enabled: true
  url: https://mcp.kite.trade/mcp
llm:
  api_key_env: KJScreener_API_KEY
  base_url: https://api.groq.com/openai/v1
  model: openai/gpt-oss-120b
  provider: openai-compatible
schedule: []
workflow:
  default_mode: classic
```

## ⚙️ Configuring the Classic Screener

The classic engine reads its parameters from `KJScreener.ini`, generated on first run:

```ini
[config]
period = 300d
daystolookback = 30
duration = 1d
minprice = 30
maxprice = 10000
volumeratio = 2
consolidationpercentage = 10
shuffle = y
cachestockdata = y
onlystagetwostocks = y
useema = n
```

Tweak these to match your trading style — e.g. set `duration = 5d` for weekly charts.

## 📖 Understanding the Result Table

| Column | Meaning |
|---|---|
| **Stock** | NSE symbol. `Ctrl+Click` opens the TradingView chart directly. |
| **Consolidating** | Price range the stock has traded in over the last *N* days. |
| **Breakout (N Days)** | `B:` breakout level and `R:` next resistance level. |
| **LTP** | Last traded price on NSE. |
| **Volume** | Current candle's volume relative to its 20-period moving average. |
| **MA-Signal** | 50/200 MA/EMA crossover signal, e.g. `BullCross-50MA`. |
| **RSI** | 14-period RSI for momentum reads. |
| **Trend** | Computed trendline strength, e.g. `Strong Up`, `Weak Down`. |
| **Pattern** | Detected candlestick/chart pattern, e.g. `Momentum Gainer`, `Bullish Engulfing`. |

## 🛠️ Tech Stack

Python 3.13 · Streamlit · `openai-agents` · pandas / numpy / scipy · `ta-lib` · yfinance · BeautifulSoup4 · ChromaDB (vector search) · Plotly · Docker

## 🤝 Contributing

Issues and pull requests are welcome!

- 🐛 Found a bug? [Open an issue](https://github.com/85599/KJStockScreener/issues/new/choose)
- 💡 Have an idea? [Start a discussion](https://github.com/85599/KJStockScreener/discussions)
- 🔧 Want to contribute code? Fork the repo, make your changes, and open a PR

## ⚠️ Disclaimer

KJStockScreener is a research and educational tool. It does **not** constitute investment advice.

- Do **not** use its output as the sole basis for your trading decisions.
- Always backtest and verify signals manually before trading.
- The author and this software are not liable for any trading losses incurred.
- **LedgerLens** is an unofficial tool that reads publicly available pages on [screener.in](https://www.screener.in) — it's not affiliated with or endorsed by them. It scrapes politely (rate-limited, retried with backoff) and is meant for personal research; please respect screener.in's terms of use.

## 📄 License

Released under the [MIT License](LICENSE).

---

<div align="center">

If this project saved you time, **please consider giving it a ⭐ — it's the easiest way to support the project.**

Made with ❤️ in India

</div>
