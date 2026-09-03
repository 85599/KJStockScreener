"""
LedgerLens tab for KJStockScreener Streamlit app.

Pulls a company's full fundamentals (summary, quarterly results, P&L,
balance sheet, cash flow, ratios, shareholding, peer comparison,
pros/cons, documents) straight from screener.in and renders it natively
in Streamlit — search, extract, browse, chart, and download, all in
one tab. Replaces the old yfinance-based "Live Quote" tab.
"""
import os
import sys

import pandas as pd
import streamlit as st

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from ledgerlens.scrapers.company_scraper import CompanyScraper
from ledgerlens.scrapers.search_scraper import SearchScraper
from ledgerlens.exporters.zip_exporter import build_zip_bytes
from ledgerlens.exporters.json_exporter import to_json_bytes
from ledgerlens.exporters.tabular_exporter import dataframe_to_csv_bytes

_ALL_SECTIONS = [
    ("quarters", "Quarterly Results"),
    ("profit_loss", "Profit & Loss"),
    ("balance_sheet", "Balance Sheet"),
    ("cash_flow", "Cash Flow"),
    ("ratios", "Ratios"),
    ("shareholding", "Shareholding Pattern"),
    ("peers", "Peer Comparison"),
]


def _run_search(query: str):
    with st.spinner(f'Searching for "{query}"...'):
        scraper = SearchScraper()
        try:
            results = scraper.search(query)
        finally:
            scraper.close()
    st.session_state["ll_search_results"] = results
    st.session_state["ll_search_query"] = query


def _extract(symbol: str, consolidated: bool, sections: list):
    full_sections = ["summary", "pros_cons", "documents"] + sections
    with st.spinner(f"Pulling {symbol} from screener.in — this respects a polite rate limit, give it a few seconds..."):
        with CompanyScraper() as scraper:
            data = scraper.get_company(symbol, consolidated=consolidated, sections=full_sections)
    st.session_state["ll_data"] = data
    st.session_state["ll_data_symbol"] = symbol


def _num(val):
    """Best-effort string -> float for a screener.in table cell."""
    if val is None:
        return None
    s = str(val).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "—", "nan", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _find_row(df: pd.DataFrame, keyword: str):
    if df is None or df.empty or "Particulars" not in df.columns:
        return None
    mask = df["Particulars"].astype(str).str.strip().str.lower().str.startswith(keyword)
    matches = df[mask]
    if matches.empty:
        return None
    return matches.iloc[0]


def _render_growth_chart(data: dict):
    df = data.get("quarters")
    label = "Quarterly"
    if df is None or df.empty:
        df = data.get("profit_loss")
        label = "Annual"
    if df is None or df.empty:
        return

    sales_row = _find_row(df, "sales")
    profit_row = _find_row(df, "net profit")
    if sales_row is None or profit_row is None:
        return

    periods = [c for c in df.columns if c != "Particulars"]
    sales_vals = [_num(sales_row[p]) for p in periods]
    profit_vals = [_num(profit_row[p]) for p in periods]
    if not any(v is not None for v in sales_vals):
        return

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=periods, y=sales_vals, name="Sales", marker_color="#2196f3"),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=periods, y=profit_vals, name="Net Profit", mode="lines+markers",
                    line=dict(color="#26a69a", width=2.5)),
        secondary_y=True,
    )
    fig.update_layout(
        title=f"{label} Sales vs Net Profit (₹ Cr)",
        template="plotly_dark",
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=60, b=40, l=40, r=40),
    )
    st.plotly_chart(fig, width="stretch")


def _render_summary(data: dict):
    summary = data.get("summary") or {}
    name = summary.get("company_name", data.get("symbol", "—"))
    price = summary.get("current_price")

    top1, top2 = st.columns([3, 1])
    top1.subheader(name)
    if price:
        top2.metric("Current Price", f"₹{price}" if not str(price).startswith("₹") else price)

    ratios = summary.get("ratios") or {}
    if ratios:
        items = list(ratios.items())
        cols = st.columns(4)
        for i, (k, v) in enumerate(items):
            cols[i % 4].metric(k, v)

    about = summary.get("about")
    if about:
        with st.expander("About the company"):
            st.write(about)

    links = summary.get("links")
    if links:
        st.caption(" · ".join(f"[{k}]({v})" for k, v in links.items()))


def _render_pros_cons(data: dict):
    pc = data.get("pros_cons") or {}
    pros, cons = pc.get("pros") or [], pc.get("cons") or []
    if not pros and not cons:
        return
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**✅ Pros**")
        for p in pros:
            st.markdown(f"- {p}")
    with c2:
        st.markdown("**⚠️ Cons**")
        for c in cons:
            st.markdown(f"- {c}")


def _render_table_sections(data: dict, symbol: str):
    available = [(key, label) for key, label in _ALL_SECTIONS if data.get(key) is not None]
    if not available:
        return
    tabs = st.tabs([label for _, label in available])
    for tab, (key, label) in zip(tabs, available):
        with tab:
            df = data[key]
            if isinstance(df, pd.DataFrame) and not df.empty:
                st.dataframe(df, width="stretch", hide_index=True)
                st.download_button(
                    f"⬇️ Download {label} (CSV)",
                    data=dataframe_to_csv_bytes(df),
                    file_name=f"{symbol}_{key}.csv",
                    mime="text/csv",
                    key=f"ll_dl_{key}",
                )
            else:
                st.info(f"No {label.lower()} data found for this company.")


def _render_documents(data: dict):
    docs = data.get("documents") or {}
    groups = [
        ("annual_reports", "📄 Annual Reports"),
        ("credit_ratings", "🏷️ Credit Ratings"),
        ("concalls", "🎙️ Concalls / Transcripts"),
    ]
    if not any(docs.get(k) for k, _ in groups):
        return
    with st.expander("Documents"):
        for key, label in groups:
            items = docs.get(key) or []
            if not items:
                continue
            st.markdown(f"**{label}**")
            for item in items:
                st.markdown(f"- [{item['title']}]({item['url']})")


def render():
    st.markdown("## 📒 LedgerLens")
    st.caption(
        "Pull a company's complete fundamentals from screener.in — quarterly results, "
        "P&L, balance sheet, cash flow, ratios, shareholding, peers, pros/cons and "
        "documents — searchable and downloadable, right here."
    )

    with st.form("ll_search_form"):
        col_q, col_btn = st.columns([4, 1])
        query = col_q.text_input(
            "Search company", placeholder="e.g. Reliance, TCS, INFY",
            label_visibility="collapsed",
        )
        submitted = col_btn.form_submit_button("🔍 Search", use_container_width=True)
    if submitted and query.strip():
        _run_search(query.strip())

    results = st.session_state.get("ll_search_results")
    if results:
        options = {f"{r['name']} ({r['symbol']})": r["symbol"] for r in results if r.get("symbol")}
        if options:
            choice = st.selectbox("Matching companies", list(options.keys()), key="ll_choice")
            symbol = options[choice]

            c1, c2 = st.columns([1, 2])
            consolidated = c1.radio(
                "Financials", ["Consolidated", "Standalone"], horizontal=True, key="ll_consolidated"
            ) == "Consolidated"
            section_labels = c2.multiselect(
                "Sections to pull",
                [label for _, label in _ALL_SECTIONS],
                default=[label for _, label in _ALL_SECTIONS],
                key="ll_sections",
            )
            selected_keys = [key for key, label in _ALL_SECTIONS if label in section_labels]

            if st.button("📥 Extract data", type="primary", key="ll_extract_btn"):
                _extract(symbol, consolidated, selected_keys)
        else:
            st.warning("No matches found. Try a different name or the exact NSE symbol.")

    data = st.session_state.get("ll_data")
    if data:
        if data.get("error"):
            st.error(data["error"])
        else:
            sym = st.session_state.get("ll_data_symbol", data.get("symbol", "STOCK"))
            _render_summary(data)
            _render_growth_chart(data)
            _render_pros_cons(data)
            _render_table_sections(data, sym)
            _render_documents(data)

            st.divider()
            dl1, dl2 = st.columns(2)
            dl1.download_button(
                "⬇️ Download full summary (JSON)",
                data=to_json_bytes(data),
                file_name=f"{sym}_ledgerlens.json",
                mime="application/json",
                key="ll_dl_json",
            )
            dl2.download_button(
                "⬇️ Download everything (ZIP — JSON + CSV + Excel per section)",
                data=build_zip_bytes(data),
                file_name=f"{sym}_ledgerlens.zip",
                mime="application/zip",
                key="ll_dl_zip",
            )
            st.caption(
                f"Source: [{data.get('url', 'screener.in')}]({data.get('url', 'https://www.screener.in')}) · "
                f"Scraped at {data.get('scraped_at', '—')} · "
                "Unofficial tool — verify against the source before relying on any figure."
            )
