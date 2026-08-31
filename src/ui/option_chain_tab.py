"""
Option Chain tab for KJScreener Streamlit app.

Fetches the live NSE option chain (NIFTY / BANKNIFTY / any F&O stock)
and shows it strike-by-strike with a one-click "📈 View" link on every
CE and PE cell that opens that exact contract on a TradingView chart —
same pattern as the Chart column on the Classic Screen results table.
"""
import os
import sys
import datetime as _dt

import pandas as pd
import streamlit as st

_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from classes.NseOptionChain import NseOptionChain, tradingview_option_url

_INDEX_PRESETS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]


def _get_client() -> NseOptionChain:
    """One NSE session per browser session — avoids re-doing the cookie
    handshake (and getting rate-limited) on every rerun."""
    if "oc_client" not in st.session_state:
        st.session_state["oc_client"] = NseOptionChain()
    return st.session_state["oc_client"]


def _load_expiries(symbol: str):
    client = _get_client()
    with st.spinner(f"Loading expiries for {symbol}..."):
        expiries = client.get_expiry_dates(symbol)
    st.session_state["oc_expiries"] = expiries
    st.session_state["oc_expiries_symbol"] = symbol
    st.session_state["oc_last_error"] = getattr(client, "last_error", None) if not expiries else None


def _fetch_chain(symbol: str, is_index: bool, expiry: str):
    client = _get_client()
    with st.spinner(f"Fetching {symbol} option chain ({expiry})..."):
        data = client.fetch_option_chain(symbol=symbol, is_index=is_index, expiry=expiry)
    if not data:
        st.session_state["oc_df"] = None
        st.session_state["oc_last_error"] = getattr(client, "last_error", None)
        st.error("Could not fetch the option chain — NSE may be rate-limiting or the market is closed. Try again.")
        return
    df = client.to_dataframe(data, expiry=expiry)
    st.session_state["oc_df"] = df
    st.session_state["oc_df_symbol"] = symbol
    st.session_state["oc_df_expiry"] = expiry


def _colour_chg(val):
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return "color: #26a69a"
    if v < 0:
        return "color: #ef5350"
    return ""


def render():
    st.subheader("⛓️ Option Chain — NSE")

    c_sym, c_expiry, c_range, c_btn = st.columns([2, 2, 2, 1])

    preset = c_sym.selectbox(
        "Underlying", _INDEX_PRESETS + ["Custom Stock"],
        key="oc_preset", label_visibility="collapsed",
    )
    if preset == "Custom Stock":
        symbol = c_sym.text_input(
            "NSE Symbol", placeholder="e.g. RELIANCE, TCS, INFY",
            key="oc_custom_symbol", label_visibility="collapsed",
        ).strip().upper()
        is_index = False
    else:
        symbol = preset
        is_index = True

    if symbol and st.session_state.get("oc_expiries_symbol") != symbol:
        _load_expiries(symbol)

    expiries = st.session_state.get("oc_expiries", []) if st.session_state.get("oc_expiries_symbol") == symbol else []
    expiry = c_expiry.selectbox(
        "Expiry", expiries if expiries else ["—"],
        key="oc_expiry_select", label_visibility="collapsed",
    )

    strikes_around_atm = c_range.slider(
        "Strikes around ATM", min_value=5, max_value=40, value=12,
        key="oc_strike_range", label_visibility="collapsed",
    )

    fetch_clicked = c_btn.button("▶ Fetch", type="primary", key="oc_fetch_btn", width="stretch")

    # ── Live auto-refresh controls ──────────────────────────────────────────
    c_live, c_interval, _sp = st.columns([1, 1, 3])
    live_on = c_live.toggle("🔴 Live", key="oc_live_toggle", value=False)
    interval_label = c_interval.selectbox(
        "Refresh every", ["5s", "10s", "15s", "30s", "60s"],
        index=2, key="oc_live_interval", label_visibility="collapsed",
        disabled=not live_on,
    )
    interval_s = int(interval_label.rstrip("s"))
    if live_on:
        st.caption(
            f"🔴 Live — re-pulling the chain from NSE every {interval_label} while this tab is open. "
            "Turn it off if you see rate-limit errors."
        )

    if fetch_clicked:
        if not symbol:
            st.warning("Enter a symbol first.", icon="⚠️")
        elif not expiries:
            st.warning("No expiry dates found for this symbol.", icon="⚠️")
        else:
            _fetch_chain(symbol, is_index, expiry)

    # ── Isolated auto-refreshing fragment ───────────────────────────────────
    # Defined fresh on every render() call so `run_every` can reflect the
    # interval the user picked right now. When Live is off, run_every=None
    # means it behaves like a normal block (no auto rerun) — Fetch button
    # (outside the fragment) still drives it as before.
    @st.fragment(run_every=f"{interval_s}s" if live_on else None)
    def _live_panel():
        if live_on and symbol and expiries:
            _fetch_chain(symbol, is_index, expiry)
        _render_results(symbol, expiry, strikes_around_atm)

    _live_panel()


def _render_results(symbol, expiry, strikes_around_atm):
    df: pd.DataFrame = st.session_state.get("oc_df")
    shown_symbol = st.session_state.get("oc_df_symbol")
    shown_expiry = st.session_state.get("oc_df_expiry")

    if df is None or df.empty or shown_symbol != symbol:
        st.info("Pick a symbol and expiry, then hit **Fetch** to load the live option chain.", icon="🔍")
        last_err = st.session_state.get("oc_last_error")
        if last_err:
            st.warning(f"Last NSE error: {last_err}", icon="🚫")
            st.caption(
                "If this keeps happening only on your server/Docker deployment (and works fine on your "
                "local PC), NSE is almost certainly blocking that machine's IP address — this is a known "
                "NSE anti-bot behaviour against cloud/datacenter IPs, not a bug in the code. "
                "Test it directly with: `docker exec <container> curl -I https://www.nseindia.com/option-chain` "
                "— a 403/999 response confirms the block."
            )
        return

    underlying = df.attrs.get("underlying")
    timestamp = df.attrs.get("timestamp")

    total_ce = df["CE_OI"].sum()
    total_pe = df["PE_OI"].sum()
    pcr = (total_pe / total_ce) if total_ce else 0

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Underlying", f"{underlying:,.2f}" if underlying else "—")
    h2.metric("Expiry", shown_expiry)
    h3.metric("PCR (PE/CE OI)", f"{pcr:.3f}")
    h4.metric("Updated", timestamp.split(" ")[-1] if timestamp else "—")

    # ── Trim to strikes around ATM so the table stays readable ────────────────
    view_df = df.copy()
    if underlying and len(view_df) > strikes_around_atm * 2:
        view_df["_dist"] = (view_df["Strike"] - underlying).abs()
        atm_idx = view_df["_dist"].idxmin()
        pos = view_df.index.get_loc(atm_idx)
        lo = max(0, pos - strikes_around_atm)
        hi = min(len(view_df), pos + strikes_around_atm + 1)
        view_df = view_df.iloc[lo:hi].drop(columns="_dist")

    # ── TradingView chart links, one per CE cell and one per PE cell ─────────
    view_df["CE_Chart"] = [
        tradingview_option_url(shown_symbol, shown_expiry, s, "CE") for s in view_df["Strike"]
    ]
    view_df["PE_Chart"] = [
        tradingview_option_url(shown_symbol, shown_expiry, s, "PE") for s in view_df["Strike"]
    ]

    display_cols = [
        "CE_Chart", "CE_OI", "CE_Chg_OI", "CE_Volume", "CE_IV", "CE_LTP", "CE_Chg",
        "Strike",
        "PE_Chg", "PE_LTP", "PE_IV", "PE_Volume", "PE_Chg_OI", "PE_OI", "PE_Chart",
    ]
    view_df = view_df[display_cols]

    styled = view_df.style.map(_colour_chg, subset=["CE_Chg", "PE_Chg", "CE_Chg_OI", "PE_Chg_OI"])
    styled = styled.set_properties(**{"font-size": "0.85rem"})

    st.dataframe(
        styled,
        width="stretch",
        hide_index=True,
        height=min(48 + len(view_df) * 36, 640),
        column_config={
            "CE_Chart": st.column_config.LinkColumn("Call", display_text="📈 CE", width="small"),
            "CE_OI": st.column_config.NumberColumn("OI", format="%d", width="small"),
            "CE_Chg_OI": st.column_config.NumberColumn("Chg OI", format="%d", width="small"),
            "CE_Volume": st.column_config.NumberColumn("Vol", format="%d", width="small"),
            "CE_IV": st.column_config.NumberColumn("IV", format="%.1f", width="small"),
            "CE_LTP": st.column_config.NumberColumn("LTP", format="%.2f", width="small"),
            "CE_Chg": st.column_config.NumberColumn("Chg", format="%.2f", width="small"),
            "Strike": st.column_config.NumberColumn("Strike", format="%d", width="small"),
            "PE_Chg": st.column_config.NumberColumn("Chg", format="%.2f", width="small"),
            "PE_LTP": st.column_config.NumberColumn("LTP", format="%.2f", width="small"),
            "PE_IV": st.column_config.NumberColumn("IV", format="%.1f", width="small"),
            "PE_Volume": st.column_config.NumberColumn("Vol", format="%d", width="small"),
            "PE_Chg_OI": st.column_config.NumberColumn("Chg OI", format="%d", width="small"),
            "PE_OI": st.column_config.NumberColumn("OI", format="%d", width="small"),
            "PE_Chart": st.column_config.LinkColumn("Put", display_text="📈 PE", width="small"),
        },
    )
    st.caption("Click 📈 CE / 📈 PE on any strike to open that exact contract on TradingView.")
