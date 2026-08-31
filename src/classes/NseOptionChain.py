#!/usr/bin/env python3
"""
NSE India Option Chain fetcher for KJScreener.

Adapted from the standalone nse_option_chain.py script (Aug 2026,
api/option-chain-v3) into a reusable class that the Streamlit
Option Chain tab can call directly, plus a helper that builds the
TradingView option-symbol so a strike's CE/PE can be opened on a
TradingView chart with one click.
"""

import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


def _safe_json(response: "requests.Response"):
    """Parse JSON, but if it fails, tell us WHY instead of a bare
    JSONDecodeError — either the bytes are compressed content the
    installed requests/urllib3 couldn't decode (missing 'br' support),
    or NSE served an HTML block/CAPTCHA page instead of the API response.

    Returns (data_or_None, error_message_or_None).
    """
    try:
        return response.json(), None
    except ValueError:
        pass

    raw = response.content or b""
    text_preview = ""
    try:
        text_preview = raw[:150].decode("utf-8", errors="replace")
    except Exception:
        text_preview = repr(raw[:60])

    stripped = text_preview.strip().lower()
    if stripped.startswith("<") or "<html" in stripped or "captcha" in stripped or "access denied" in stripped:
        return None, (
            "NSE served an HTML page instead of JSON (looks like a block/CAPTCHA page), "
            f"even though HTTP status was {response.status_code}. Preview: {text_preview!r}"
        )
    if not raw:
        return None, f"NSE returned an empty body (HTTP {response.status_code})."
    return None, (
        f"Response body wasn't valid JSON and isn't HTML either (HTTP {response.status_code}). "
        f"This usually means the content was compressed (br/brotli) and couldn't be decoded. "
        f"Raw preview: {text_preview!r}"
    )


class NseOptionChain:
    """Thin wrapper around NSE's option-chain-v3 endpoint with retry/session handling."""

    def __init__(self):
        self.base_url = "https://www.nseindia.com"
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Referer": "https://www.nseindia.com/option-chain",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        self.session.headers.update(self.headers)
        # Last error observed on the homepage/expiry/chain calls, surfaced to
        # the UI so "no data" doesn't look identical to "NSE blocked us" —
        # these need very different fixes (retry vs. change hosting/IP).
        self.last_error: Optional[str] = None
        self._init_session()

    def _init_session(self):
        try:
            r = self.session.get(f"{self.base_url}/option-chain", timeout=15)
            if r.status_code != 200:
                self.last_error = (
                    f"NSE homepage returned HTTP {r.status_code} while warming up "
                    f"the session (cookie handshake)."
                )
            time.sleep(random.uniform(0.6, 1.2))
        except Exception as e:
            self.last_error = f"Could not reach nseindia.com: {e!r}"

    def _refresh_session(self):
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._init_session()
        time.sleep(random.uniform(2, 4))

    def get_expiry_dates(self, symbol: str) -> List[str]:
        """Available expiry dates for the given symbol, e.g. ['28-Aug-2026', ...]."""
        url = f"{self.base_url}/api/option-chain-contract-info?symbol={symbol.upper()}"
        try:
            r = self.session.get(url, timeout=15)
            if r.status_code == 200:
                data, err = _safe_json(r)
                if err is None:
                    self.last_error = None
                    return data.get("expiryDates", [])
                self.last_error = err
                return []
            self.last_error = (
                f"NSE returned HTTP {r.status_code} for {symbol.upper()} expiry lookup "
                f"({'likely blocked — datacenter/cloud IPs are frequently denied by NSE' if r.status_code in (401, 403, 429) else 'unexpected status'})."
            )
        except Exception as e:
            self.last_error = f"Request to NSE failed: {e!r}"
        return []

    def fetch_option_chain(
        self,
        symbol: str = "NIFTY",
        is_index: bool = True,
        expiry: Optional[str] = None,
        max_retries: int = 4,
    ) -> Optional[Dict[str, Any]]:
        symbol = symbol.upper().strip()
        type_param = "Indices" if is_index else "Equity"

        if not expiry:
            expiries = self.get_expiry_dates(symbol)
            if not expiries:
                return None
            expiry = expiries[0]

        url = f"{self.base_url}/api/option-chain-v3?type={type_param}&symbol={symbol}&expiry={expiry}"

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url, timeout=20)

                if response.status_code == 200:
                    data, err = _safe_json(response)
                    if err is None and data and "records" in data:
                        self.last_error = None
                        return data
                    self.last_error = err or "NSE returned HTTP 200 but no 'records' in the response body."
                    time.sleep(2)
                    continue

                elif response.status_code in (403, 401, 429):
                    self.last_error = (
                        f"NSE returned HTTP {response.status_code} on attempt {attempt}/{max_retries} — "
                        f"this is NSE's bot-protection blocking the request. Very common when the server "
                        f"is on a cloud/datacenter IP (AWS, GCP, Azure, DigitalOcean, etc.); NSE mostly "
                        f"allows only residential/ISP IPs."
                    )
                    self._refresh_session()
                    time.sleep(random.uniform(3, 6) * attempt)
                    continue

                elif response.status_code == 404:
                    if attempt == 1 and expiry:
                        url2 = f"{self.base_url}/api/option-chain-v3?type={type_param}&symbol={symbol}"
                        r2 = self.session.get(url2, timeout=15)
                        if r2.status_code == 200:
                            data2, err2 = _safe_json(r2)
                            if err2 is None and data2 and data2.get("records"):
                                self.last_error = None
                                return data2
                    self.last_error = f"NSE returned HTTP 404 for {symbol} / {expiry}."
                    time.sleep(2)
                    continue
                else:
                    self.last_error = f"NSE returned unexpected HTTP {response.status_code}."
                    time.sleep(2)

            except requests.exceptions.RequestException as e:
                self.last_error = f"Network error talking to NSE: {e!r}"
                time.sleep(3 * attempt)
                self._refresh_session()

        return None

    def to_dataframe(self, data: Dict[str, Any], expiry: Optional[str] = None) -> pd.DataFrame:
        if not data or "records" not in data:
            return pd.DataFrame()

        records = data["records"]["data"]
        underlying = None
        rows = []

        for rec in records:
            ce = rec.get("CE", {})
            pe = rec.get("PE", {})

            strike = ce.get("strikePrice") or pe.get("strikePrice") or rec.get("strikePrice")
            if strike is None:
                continue

            if underlying is None:
                underlying = ce.get("underlyingValue") or pe.get("underlyingValue")

            rows.append({
                "Strike": strike,
                "CE_OI": ce.get("openInterest", 0) or 0,
                "CE_Chg_OI": ce.get("changeinOpenInterest", 0) or 0,
                "CE_Volume": ce.get("totalTradedVolume", 0) or 0,
                "CE_IV": ce.get("impliedVolatility", 0) or 0,
                "CE_LTP": ce.get("lastPrice", 0) or 0,
                "CE_Chg": ce.get("change", 0) or 0,
                "PE_Chg": pe.get("change", 0) or 0,
                "PE_LTP": pe.get("lastPrice", 0) or 0,
                "PE_IV": pe.get("impliedVolatility", 0) or 0,
                "PE_Volume": pe.get("totalTradedVolume", 0) or 0,
                "PE_Chg_OI": pe.get("changeinOpenInterest", 0) or 0,
                "PE_OI": pe.get("openInterest", 0) or 0,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("Strike").reset_index(drop=True)

        df.attrs["underlying"] = underlying
        df.attrs["expiry"] = expiry
        # Use NSE's own timestamp (always IST, embedded in the response) instead
        # of the local machine clock — a Docker container's system timezone is
        # almost always UTC unless explicitly set, which made this show a time
        # 5:30 hours behind real IST.
        nse_ts = data.get("records", {}).get("timestamp")
        df.attrs["timestamp"] = nse_ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return df


def tradingview_option_symbol(underlying: str, expiry_dd_mon_yyyy: str, strike: float, opt_type: str) -> str:
    """
    Build the TradingView option ticker for a given NSE contract.

    TradingView's own format (per their support docs) is:
        <UNDERLYING><YYMMDD><C|P><STRIKE>
    e.g. NIFTY240314C22450 = NIFTY, 14-Mar-2024 expiry, Call, strike 22450.

    expiry_dd_mon_yyyy: NSE-style date string, e.g. "28-Aug-2026".
    opt_type: "CE" or "PE".
    """
    try:
        dt = datetime.strptime(expiry_dd_mon_yyyy.strip(), "%d-%b-%Y")
        yymmdd = dt.strftime("%y%m%d")
    except Exception:
        # Fall back to today's date if the expiry string can't be parsed —
        # better to give a best-effort link than none at all.
        yymmdd = datetime.now().strftime("%y%m%d")

    code = "C" if opt_type.upper().startswith("C") else "P"
    strike_str = str(int(strike)) if float(strike).is_integer() else str(strike)
    return f"{underlying.upper()}{yymmdd}{code}{strike_str}"


def tradingview_option_url(underlying: str, expiry_dd_mon_yyyy: str, strike: float, opt_type: str) -> str:
    ticker = tradingview_option_symbol(underlying, expiry_dd_mon_yyyy, strike, opt_type)
    return f"https://in.tradingview.com/chart?symbol=NSE%3A{ticker}"
