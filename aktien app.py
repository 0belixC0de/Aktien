"""
Aktien Signal-App — Überarbeitete Version
==========================================
INSTALLATION: pip install streamlit yfinance pandas plotly requests
STARTEN:      streamlit run aktien_app.py
              (oder Doppelklick auf "App starten.bat")

WICHTIG: Keine Finanzberatung. Alle Signale sind rein technisch.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
import concurrent.futures
import json
import requests

st.set_page_config(page_title="Aktien Signal-Tool", page_icon="📈", layout="centered")

# ---------------------------------------------------------------------------
# DATEN-FUNKTIONEN
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def search_ticker(query):
    """
    Sucht nach Aktien per Firmenname oder Ticker.
    Gibt eine Liste von Dicts zurück: [{symbol, name, exchange}]
    """
    if not query or len(query) < 2:
        return []
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": 8, "newsCount": 0, "enableFuzzyQuery": True},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=5,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for q in data.get("quotes", []):
            if q.get("typeDisp") not in ("Equity", "ETF", "Index"):
                continue
            results.append({
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname") or q.get("symbol", ""),
                "exchange": q.get("exchDisp", ""),
            })
        return results
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_intraday(ticker):
    """Lädt Intraday-Kurse (5-Minuten-Intervall, letzter Handelstag)."""
    try:
        data = yf.download(ticker, period="1d", interval="5m", progress=False)
        if data.empty:
            return None
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    except Exception:
        return None



@st.cache_data(ttl=600, show_spinner=False)
def get_close(ticker, days=120):
    data = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
    if data.empty:
        return None
    close = data["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna()


@st.cache_data(ttl=300, show_spinner=False)
def get_news(ticker):
    try:
        return yf.Ticker(ticker).news or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_market_overview():
    symbols = {
        "S&P 500": "^GSPC", "Nasdaq": "^IXIC", "DAX": "^GDAXI",
        "Dow Jones": "^DJI", "EUR/USD": "EURUSD=X", "Gold": "GC=F",
    }
    rows = []
    for name, sym in symbols.items():
        try:
            d = yf.download(sym, period="2d", interval="1d", progress=False)
            if d.empty or len(d) < 2:
                continue
            close = d["Close"].iloc[:, 0] if isinstance(d["Close"], pd.DataFrame) else d["Close"]
            close = close.dropna()
            if len(close) < 2:
                continue
            prev, curr = float(close.iloc[-2]), float(close.iloc[-1])
            pct = (curr - prev) / prev * 100
            rows.append({"name": name, "price": curr, "pct": pct})
        except Exception:
            pass
    return rows


@st.cache_data(ttl=3600, show_spinner=False)
def get_seasonality(ticker, years=5):
    try:
        data = yf.download(ticker, period=f"{years}y", interval="1d", progress=False)
        if data.empty or len(data) < 100:
            return None
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close = close.dropna()
        monthly = close.resample("ME").last()
        ret = monthly.pct_change().dropna() * 100
        df = ret.to_frame("return")
        df["month"] = df.index.month
        names = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]
        avg = df.groupby("month")["return"].mean().reindex(range(1, 13))
        avg.index = names
        return avg
    except Exception:
        return None


def fetch_ticker_momentum(ticker, lookback):
    try:
        close = get_close(ticker, days=lookback + 20)
        if close is None or len(close) < lookback + 1:
            return None
        curr = float(close.iloc[-1])
        past = float(close.iloc[-1 - lookback])
        pct = (curr - past) / past * 100
        return {"Ticker": ticker, "Kurs": round(curr, 2), "Veränderung %": round(pct, 2)}
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def scan_market(tickers, lookback):
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as ex:
        results = list(ex.map(lambda t: fetch_ticker_momentum(t, lookback), tickers))
    return pd.DataFrame([r for r in results if r])


# ---------------------------------------------------------------------------
# INDIKATOR-FUNKTIONEN
# ---------------------------------------------------------------------------

def compute_ma_signal(close, short_w, long_w):
    short_ma = close.rolling(short_w).mean()
    long_ma = close.rolling(long_w).mean()
    if len(close) < long_w + 2 or pd.isna(short_ma.iloc[-1]) or pd.isna(long_ma.iloc[-1]):
        return None
    curr = float(short_ma.iloc[-1] - long_ma.iloc[-1])
    prev = float(short_ma.iloc[-2] - long_ma.iloc[-2])
    if prev <= 0 < curr:
        sig, col = "KAUFSIGNAL", "green"
    elif prev >= 0 > curr:
        sig, col = "VERKAUFSSIGNAL", "red"
    elif curr > 0:
        sig, col = "Aufwärtstrend", "green"
    else:
        sig, col = "Abwärtstrend", "orange"
    return {"signal": sig, "color": col, "short_ma": short_ma, "long_ma": long_ma, "price": float(close.iloc[-1])}


def compute_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    val = rsi.iloc[-1]
    return float(val) if not pd.isna(val) else None


def compute_momentum(close, period=10):
    if len(close) <= period:
        return None
    return float((close.iloc[-1] / close.iloc[-1 - period] - 1) * 100)


def compute_risk(close, rfr=0.04):
    ret = close.pct_change().dropna()
    if len(ret) < 10:
        return None
    ann_vol = float(ret.std() * np.sqrt(252))
    ann_ret = float(ret.mean() * 252)
    sharpe = (ann_ret - rfr) / ann_vol if ann_vol > 0 else 0.0
    running_max = close.cummax()
    drawdown = (close - running_max) / running_max
    return {
        "ann_vol": ann_vol, "ann_ret": ann_ret,
        "sharpe": float(sharpe), "max_drawdown": float(drawdown.min()),
        "drawdown_series": drawdown,
    }


def build_ampel(ma, rsi_val, mom_val):
    votes = {}
    votes["MA-Crossover"] = (1, "bullisch") if ma["color"] in ("green",) else (-1, "bärisch")
    if rsi_val is not None:
        if rsi_val < 30:   votes["RSI"] = (1,  f"überverkauft ({rsi_val:.0f})")
        elif rsi_val > 70: votes["RSI"] = (-1, f"überkauft ({rsi_val:.0f})")
        else:              votes["RSI"] = (0,  f"neutral ({rsi_val:.0f})")
    else:
        votes["RSI"] = (0, "keine Daten")
    if mom_val is not None:
        if mom_val > 1:    votes["Momentum"] = (1,  f"positiv ({mom_val:+.1f}%)")
        elif mom_val < -1: votes["Momentum"] = (-1, f"negativ ({mom_val:+.1f}%)")
        else:              votes["Momentum"] = (0,  f"flach ({mom_val:+.1f}%)")
    else:
        votes["Momentum"] = (0, "keine Daten")
    score = sum(v[0] for v in votes.values())
    if score >= 2:   ampel, label = "green",  "Bullisch — Indikatoren mehrheitlich positiv"
    elif score <= -2: ampel, label = "red",   "Bärisch — Indikatoren mehrheitlich negativ"
    else:             ampel, label = "yellow", "Gemischt — Indikatoren widersprechen sich"
    return ampel, label, votes


# ---------------------------------------------------------------------------
# SENTIMENT-FUNKTIONEN
# ---------------------------------------------------------------------------

POS_WORDS = ["surge","soar","jump","rally","beat","beats","growth","record","upgrade","outperform",
             "strong","gain","gains","rise","rises","boost","profit","bullish","breakthrough","wins",
             "approval","approved","partnership","deal","exceed","exceeds"]
NEG_WORDS = ["plunge","plummet","drop","drops","fall","falls","miss","misses","downgrade","underperform",
             "weak","loss","losses","decline","declines","cut","cuts","bearish","lawsuit","investigation",
             "recall","warning","scandal","layoff","layoffs","crash","default","fraud","ban","tariff","sanction"]


def simple_sentiment(news_items):
    pos, neg, matched = 0, 0, []
    for item in news_items:
        cb = item.get("content", item)
        title = (cb.get("title") or item.get("title") or "").lower()
        for w in POS_WORDS:
            if w in title: pos += 1; matched.append((title[:70], "positiv", w))
        for w in NEG_WORDS:
            if w in title: neg += 1; matched.append((title[:70], "negativ", w))
    total = pos + neg
    score = 0.0 if total == 0 else (pos - neg) / total
    return score, pos, neg, matched


def claude_sentiment(news_items, ticker, api_key):
    headlines = []
    for item in news_items[:10]:
        cb = item.get("content", item)
        t = cb.get("title") or item.get("title")
        if t:
            headlines.append(t)
    if not headlines:
        return 0.0, "Keine Schlagzeilen.", []
    text = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
    prompt = f"""Du bewertest Finanz-Schlagzeilen zur Aktie {ticker} auf ihre kurzfristige Kursrelevanz.

Schlagzeilen:
{text}

Ironie, Verneinungen und Kontext zählen. Antworte NUR mit validem JSON:
{{"score": <-1.0 bis 1.0>, "reasoning": "<max 2 Sätze Deutsch>", "items": [{{"headline": "<kurz>", "sentiment": "positiv|negativ|neutral", "relevance": "hoch|mittel|niedrig"}}]}}"""
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 1024,
                  "messages": [{"role": "user", "content": prompt}]}, timeout=30)
        r.raise_for_status()
        raw = "".join(b.get("text","") for b in r.json().get("content",[]) if b.get("type")=="text").strip()
        if raw.startswith("```"): raw = raw.strip("`"); raw = raw[4:] if raw.startswith("json") else raw
        parsed = json.loads(raw)
        score = max(-1.0, min(1.0, float(parsed.get("score", 0.0))))
        return score, parsed.get("reasoning",""), parsed.get("items",[])
    except Exception as e:
        return None, f"Fehler: {e}", []

WATCHLIST = [
    "MMM", "AOS", "ABT", "ABBV", "ACN", "ADBE", "AMD", "AES", "AFL", "A",
    "APD", "ABNB", "AKAM", "ALB", "ARE", "ALGN", "ALLE", "LNT", "ALL", "GOOGL",
    "GOOG", "MO", "AMZN", "AMCR", "AEE", "AEP", "AXP", "AIG", "AMT", "AWK",
    "AMP", "AME", "AMGN", "APH", "ADI", "AON", "APA", "APO", "AAPL", "AMAT",
    "APP", "APTV", "ACGL", "ADM", "ARES", "ANET", "AJG", "AIZ", "T", "ATO",
    "ADSK", "ADP", "AZO", "AVB", "AVY", "AXON", "BKR", "BALL", "BAC", "BAX",
    "BDX", "BRK-B", "BBY", "TECH", "BIIB", "BLK", "BX", "XYZ", "BNY", "BA",
    "BKNG", "BSX", "BMY", "AVGO", "BR", "BRO", "BF-B", "BLDR", "BG", "BXP",
    "CHRW", "CDNS", "CPT", "CPB", "COF", "CAH", "CCL", "CARR", "CVNA", "CASY",
    "CAT", "CBOE", "CBRE", "CDW", "COR", "CNC", "CNP", "CF", "CRL", "SCHW",
    "CHTR", "CVX", "CMG", "CB", "CHD", "CIEN", "CI", "CINF", "CTAS", "CSCO",
    "C", "CFG", "CLX", "CME", "CMS", "KO", "CTSH", "COHR", "COIN", "CL",
    "CMCSA", "FIX", "CAG", "COP", "ED", "STZ", "CEG", "COO", "CPRT", "GLW",
    "CPAY", "CTVA", "CSGP", "COST", "CRH", "CRWD", "CCI", "CSX", "CMI", "CVS",
    "DHR", "DRI", "DDOG", "DVA", "DECK", "DE", "DELL", "DAL", "DVN", "DXCM",
    "FANG", "DLR", "DG", "DLTR", "D", "DPZ", "DASH", "DOV", "DOW", "DHI",
    "DTE", "DUK", "DD", "ETN", "EBAY", "SATS", "ECL", "EIX", "EW", "EA",
    "ELV", "EME", "EMR", "ETR", "EOG", "EPAM", "EQT", "EFX", "EQIX", "EQR",
    "ERIE", "ESS", "EL", "EG", "EVRG", "ES", "EXC", "EXE", "EXPE", "EXPD",
    "EXR", "XOM", "FFIV", "FDS", "FICO", "FAST", "FRT", "FDX", "FIS", "FITB",
    "FSLR", "FE", "FISV", "F", "FTNT", "FTV", "FOXA", "FOX", "BEN", "FCX",
    "GRMN", "IT", "GE", "GEHC", "GEV", "GEN", "GNRC", "GD", "GIS", "GM",
    "GPC", "GILD", "GPN", "GL", "GDDY", "GS", "HAL", "HIG", "HAS", "HCA",
    "DOC", "HSIC", "HSY", "HPE", "HLT", "HD", "HON", "HRL", "HST", "HWM",
    "HPQ", "HUBB", "HUM", "HBAN", "HII", "IBM", "IEX", "IDXX", "ITW", "INCY",
    "IR", "PODD", "INTC", "IBKR", "ICE", "IFF", "IP", "INTU", "ISRG", "IVZ",
    "INVH", "IQV", "IRM", "JBHT", "JBL", "JKHY", "J", "JNJ", "JCI", "JPM",
    "KVUE", "KDP", "KEY", "KEYS", "KMB", "KIM", "KMI", "KKR", "KLAC", "KHC",
    "KR", "LHX", "LH", "LRCX", "LVS", "LDOS", "LEN", "LII", "LLY", "LIN",
    "LYV", "LMT", "L", "LOW", "LULU", "LITE", "LYB", "MTB", "MPC", "MAR",
    "MRSH", "MLM", "MAS", "MA", "MKC", "MCD", "MCK", "MDT", "MRK", "META",
    "MET", "MTD", "MGM", "MCHP", "MU", "MSFT", "MAA", "MRNA", "TAP", "MDLZ",
    "MPWR", "MNST", "MCO", "MS", "MOS", "MSI", "MSCI", "NDAQ", "NTAP", "NFLX",
    "NEM", "NWSA", "NWS", "NEE", "NKE", "NI", "NDSN", "NSC", "NTRS", "NOC",
    "NCLH", "NRG", "NUE", "NVDA", "NVR", "NXPI", "ORLY", "OXY", "ODFL", "OMC",
    "ON", "OKE", "ORCL", "OTIS", "PCAR", "PKG", "PLTR", "PANW", "PSKY", "PH",
    "PAYX", "PYPL", "PNR", "PEP", "PFE", "PCG", "PM", "PSX", "PNW", "PNC",
    "POOL", "PPG", "PPL", "PFG", "PG", "PGR", "PLD", "PRU", "PEG", "PTC",
    "PSA", "PHM", "PWR", "QCOM", "DGX", "Q", "RL", "RJF", "RTX", "O",
    "REG", "REGN", "RF", "RSG", "RMD", "RVTY", "HOOD", "ROK", "ROL", "ROP",
    "ROST", "RCL", "SPGI", "CRM", "SNDK", "SBAC", "SLB", "STX", "SRE", "NOW",
    "SHW", "SPG", "SWKS", "SJM", "SW", "SNA", "SOLV", "SO", "LUV", "SWK",
    "SBUX", "STT", "STLD", "STE", "SYK", "SMCI", "SYF", "SNPS", "SYY", "TMUS",
    "TROW", "TTWO", "TPR", "TRGP", "TGT", "TEL", "TDY", "TER", "TSLA", "TXN",
    "TPL", "TXT", "TMO", "TJX", "TKO", "TTD", "TSCO", "TT", "TDG", "TRV",
    "TRMB", "TFC", "TYL", "TSN", "USB", "UBER", "UDR", "ULTA", "UNP", "UAL",
    "UPS", "URI", "UNH", "UHS", "VLO", "VEEV", "VTR", "VLTO", "VRSN", "VRSK",
    "VZ", "VRTX", "VRT", "VTRS", "VICI", "V", "VST", "VMC", "WRB", "GWW",
    "WAB", "WMT", "DIS", "WBD", "WM", "WAT", "WEC", "WFC", "WELL", "WST",
    "WDC", "WY", "WSM", "WMB", "WTW", "WDAY", "WYNN", "XEL", "XYL", "YUM",
    "ZBRA", "ZBH", "ZTS",
]

SECTOR_MAP = {
    "MMM": "Industrie", "AOS": "Industrie", "ABT": "Gesundheit", "ABBV": "Gesundheit", "ACN": "Technologie", "ADBE": "Technologie",
    "AMD": "Technologie", "AES": "Versorger", "AFL": "Finanzen", "A": "Gesundheit", "APD": "Rohstoffe", "ABNB": "Konsum (zyklisch)",
    "AKAM": "Technologie", "ALB": "Rohstoffe", "ARE": "Immobilien", "ALGN": "Gesundheit", "ALLE": "Industrie", "LNT": "Versorger",
    "ALL": "Finanzen", "GOOGL": "Kommunikation", "GOOG": "Kommunikation", "MO": "Konsum (Basis)", "AMZN": "Konsum (zyklisch)", "AMCR": "Rohstoffe",
    "AEE": "Versorger", "AEP": "Versorger", "AXP": "Finanzen", "AIG": "Finanzen", "AMT": "Immobilien", "AWK": "Versorger",
    "AMP": "Finanzen", "AME": "Industrie", "AMGN": "Gesundheit", "APH": "Technologie", "ADI": "Technologie", "AON": "Finanzen",
    "APA": "Energie", "APO": "Finanzen", "AAPL": "Technologie", "AMAT": "Technologie", "APP": "Technologie", "APTV": "Konsum (zyklisch)",
    "ACGL": "Finanzen", "ADM": "Konsum (Basis)", "ARES": "Finanzen", "ANET": "Technologie", "AJG": "Finanzen", "AIZ": "Finanzen",
    "T": "Kommunikation", "ATO": "Versorger", "ADSK": "Technologie", "ADP": "Industrie", "AZO": "Konsum (zyklisch)", "AVB": "Immobilien",
    "AVY": "Rohstoffe", "AXON": "Industrie", "BKR": "Energie", "BALL": "Rohstoffe", "BAC": "Finanzen", "BAX": "Gesundheit",
    "BDX": "Gesundheit", "BRK-B": "Finanzen", "BBY": "Konsum (zyklisch)", "TECH": "Gesundheit", "BIIB": "Gesundheit", "BLK": "Finanzen",
    "BX": "Finanzen", "XYZ": "Finanzen", "BNY": "Finanzen", "BA": "Industrie", "BKNG": "Konsum (zyklisch)", "BSX": "Gesundheit",
    "BMY": "Gesundheit", "AVGO": "Technologie", "BR": "Industrie", "BRO": "Finanzen", "BF-B": "Konsum (Basis)", "BLDR": "Industrie",
    "BG": "Konsum (Basis)", "BXP": "Immobilien", "CHRW": "Industrie", "CDNS": "Technologie", "CPT": "Immobilien", "CPB": "Konsum (Basis)",
    "COF": "Finanzen", "CAH": "Gesundheit", "CCL": "Konsum (zyklisch)", "CARR": "Industrie", "CVNA": "Konsum (zyklisch)", "CASY": "Konsum (Basis)",
    "CAT": "Industrie", "CBOE": "Finanzen", "CBRE": "Immobilien", "CDW": "Technologie", "COR": "Gesundheit", "CNC": "Gesundheit",
    "CNP": "Versorger", "CF": "Rohstoffe", "CRL": "Gesundheit", "SCHW": "Finanzen", "CHTR": "Kommunikation", "CVX": "Energie",
    "CMG": "Konsum (zyklisch)", "CB": "Finanzen", "CHD": "Konsum (Basis)", "CIEN": "Technologie", "CI": "Gesundheit", "CINF": "Finanzen",
    "CTAS": "Industrie", "CSCO": "Technologie", "C": "Finanzen", "CFG": "Finanzen", "CLX": "Konsum (Basis)", "CME": "Finanzen",
    "CMS": "Versorger", "KO": "Konsum (Basis)", "CTSH": "Technologie", "COHR": "Technologie", "COIN": "Finanzen", "CL": "Konsum (Basis)",
    "CMCSA": "Kommunikation", "FIX": "Industrie", "CAG": "Konsum (Basis)", "COP": "Energie", "ED": "Versorger", "STZ": "Konsum (Basis)",
    "CEG": "Versorger", "COO": "Gesundheit", "CPRT": "Industrie", "GLW": "Technologie", "CPAY": "Finanzen", "CTVA": "Rohstoffe",
    "CSGP": "Immobilien", "COST": "Konsum (Basis)", "CRH": "Rohstoffe", "CRWD": "Technologie", "CCI": "Immobilien", "CSX": "Industrie",
    "CMI": "Industrie", "CVS": "Gesundheit", "DHR": "Gesundheit", "DRI": "Konsum (zyklisch)", "DDOG": "Technologie", "DVA": "Gesundheit",
    "DECK": "Konsum (zyklisch)", "DE": "Industrie", "DELL": "Technologie", "DAL": "Industrie", "DVN": "Energie", "DXCM": "Gesundheit",
    "FANG": "Energie", "DLR": "Immobilien", "DG": "Konsum (Basis)", "DLTR": "Konsum (Basis)", "D": "Versorger", "DPZ": "Konsum (zyklisch)",
    "DASH": "Konsum (zyklisch)", "DOV": "Industrie", "DOW": "Rohstoffe", "DHI": "Konsum (zyklisch)", "DTE": "Versorger", "DUK": "Versorger",
    "DD": "Rohstoffe", "ETN": "Industrie", "EBAY": "Konsum (zyklisch)", "SATS": "Kommunikation", "ECL": "Rohstoffe", "EIX": "Versorger",
    "EW": "Gesundheit", "EA": "Kommunikation", "ELV": "Gesundheit", "EME": "Industrie", "EMR": "Industrie", "ETR": "Versorger",
    "EOG": "Energie", "EPAM": "Technologie", "EQT": "Energie", "EFX": "Industrie", "EQIX": "Immobilien", "EQR": "Immobilien",
    "ERIE": "Finanzen", "ESS": "Immobilien", "EL": "Konsum (Basis)", "EG": "Finanzen", "EVRG": "Versorger", "ES": "Versorger",
    "EXC": "Versorger", "EXE": "Energie", "EXPE": "Konsum (zyklisch)", "EXPD": "Industrie", "EXR": "Immobilien", "XOM": "Energie",
    "FFIV": "Technologie", "FDS": "Finanzen", "FICO": "Technologie", "FAST": "Industrie", "FRT": "Immobilien", "FDX": "Industrie",
    "FIS": "Finanzen", "FITB": "Finanzen", "FSLR": "Technologie", "FE": "Versorger", "FISV": "Finanzen", "F": "Konsum (zyklisch)",
    "FTNT": "Technologie", "FTV": "Industrie", "FOXA": "Kommunikation", "FOX": "Kommunikation", "BEN": "Finanzen", "FCX": "Rohstoffe",
    "GRMN": "Konsum (zyklisch)", "IT": "Technologie", "GE": "Industrie", "GEHC": "Gesundheit", "GEV": "Industrie", "GEN": "Technologie",
    "GNRC": "Industrie", "GD": "Industrie", "GIS": "Konsum (Basis)", "GM": "Konsum (zyklisch)", "GPC": "Konsum (zyklisch)", "GILD": "Gesundheit",
    "GPN": "Finanzen", "GL": "Finanzen", "GDDY": "Technologie", "GS": "Finanzen", "HAL": "Energie", "HIG": "Finanzen",
    "HAS": "Konsum (zyklisch)", "HCA": "Gesundheit", "DOC": "Immobilien", "HSIC": "Gesundheit", "HSY": "Konsum (Basis)", "HPE": "Technologie",
    "HLT": "Konsum (zyklisch)", "HD": "Konsum (zyklisch)", "HON": "Industrie", "HRL": "Konsum (Basis)", "HST": "Immobilien", "HWM": "Industrie",
    "HPQ": "Technologie", "HUBB": "Industrie", "HUM": "Gesundheit", "HBAN": "Finanzen", "HII": "Industrie", "IBM": "Technologie",
    "IEX": "Industrie", "IDXX": "Gesundheit", "ITW": "Industrie", "INCY": "Gesundheit", "IR": "Industrie", "PODD": "Gesundheit",
    "INTC": "Technologie", "IBKR": "Finanzen", "ICE": "Finanzen", "IFF": "Rohstoffe", "IP": "Rohstoffe", "INTU": "Technologie",
    "ISRG": "Gesundheit", "IVZ": "Finanzen", "INVH": "Immobilien", "IQV": "Gesundheit", "IRM": "Immobilien", "JBHT": "Industrie",
    "JBL": "Technologie", "JKHY": "Finanzen", "J": "Industrie", "JNJ": "Gesundheit", "JCI": "Industrie", "JPM": "Finanzen",
    "KVUE": "Konsum (Basis)", "KDP": "Konsum (Basis)", "KEY": "Finanzen", "KEYS": "Technologie", "KMB": "Konsum (Basis)", "KIM": "Immobilien",
    "KMI": "Energie", "KKR": "Finanzen", "KLAC": "Technologie", "KHC": "Konsum (Basis)", "KR": "Konsum (Basis)", "LHX": "Industrie",
    "LH": "Gesundheit", "LRCX": "Technologie", "LVS": "Konsum (zyklisch)", "LDOS": "Industrie", "LEN": "Konsum (zyklisch)", "LII": "Industrie",
    "LLY": "Gesundheit", "LIN": "Rohstoffe", "LYV": "Kommunikation", "LMT": "Industrie", "L": "Finanzen", "LOW": "Konsum (zyklisch)",
    "LULU": "Konsum (zyklisch)", "LITE": "Technologie", "LYB": "Rohstoffe", "MTB": "Finanzen", "MPC": "Energie", "MAR": "Konsum (zyklisch)",
    "MRSH": "Finanzen", "MLM": "Rohstoffe", "MAS": "Industrie", "MA": "Finanzen", "MKC": "Konsum (Basis)", "MCD": "Konsum (zyklisch)",
    "MCK": "Gesundheit", "MDT": "Gesundheit", "MRK": "Gesundheit", "META": "Kommunikation", "MET": "Finanzen", "MTD": "Gesundheit",
    "MGM": "Konsum (zyklisch)", "MCHP": "Technologie", "MU": "Technologie", "MSFT": "Technologie", "MAA": "Immobilien", "MRNA": "Gesundheit",
    "TAP": "Konsum (Basis)", "MDLZ": "Konsum (Basis)", "MPWR": "Technologie", "MNST": "Konsum (Basis)", "MCO": "Finanzen", "MS": "Finanzen",
    "MOS": "Rohstoffe", "MSI": "Technologie", "MSCI": "Finanzen", "NDAQ": "Finanzen", "NTAP": "Technologie", "NFLX": "Kommunikation",
    "NEM": "Rohstoffe", "NWSA": "Kommunikation", "NWS": "Kommunikation", "NEE": "Versorger", "NKE": "Konsum (zyklisch)", "NI": "Versorger",
    "NDSN": "Industrie", "NSC": "Industrie", "NTRS": "Finanzen", "NOC": "Industrie", "NCLH": "Konsum (zyklisch)", "NRG": "Versorger",
    "NUE": "Rohstoffe", "NVDA": "Technologie", "NVR": "Konsum (zyklisch)", "NXPI": "Technologie", "ORLY": "Konsum (zyklisch)", "OXY": "Energie",
    "ODFL": "Industrie", "OMC": "Kommunikation", "ON": "Technologie", "OKE": "Energie", "ORCL": "Technologie", "OTIS": "Industrie",
    "PCAR": "Industrie", "PKG": "Rohstoffe", "PLTR": "Technologie", "PANW": "Technologie", "PSKY": "Kommunikation", "PH": "Industrie",
    "PAYX": "Industrie", "PYPL": "Finanzen", "PNR": "Industrie", "PEP": "Konsum (Basis)", "PFE": "Gesundheit", "PCG": "Versorger",
    "PM": "Konsum (Basis)", "PSX": "Energie", "PNW": "Versorger", "PNC": "Finanzen", "POOL": "Konsum (zyklisch)", "PPG": "Rohstoffe",
    "PPL": "Versorger", "PFG": "Finanzen", "PG": "Konsum (Basis)", "PGR": "Finanzen", "PLD": "Immobilien", "PRU": "Finanzen",
    "PEG": "Versorger", "PTC": "Technologie", "PSA": "Immobilien", "PHM": "Konsum (zyklisch)", "PWR": "Industrie", "QCOM": "Technologie",
    "DGX": "Gesundheit", "Q": "Technologie", "RL": "Konsum (zyklisch)", "RJF": "Finanzen", "RTX": "Industrie", "O": "Immobilien",
    "REG": "Immobilien", "REGN": "Gesundheit", "RF": "Finanzen", "RSG": "Industrie", "RMD": "Gesundheit", "RVTY": "Gesundheit",
    "HOOD": "Finanzen", "ROK": "Industrie", "ROL": "Industrie", "ROP": "Technologie", "ROST": "Konsum (zyklisch)", "RCL": "Konsum (zyklisch)",
    "SPGI": "Finanzen", "CRM": "Technologie", "SNDK": "Technologie", "SBAC": "Immobilien", "SLB": "Energie", "STX": "Technologie",
    "SRE": "Versorger", "NOW": "Technologie", "SHW": "Rohstoffe", "SPG": "Immobilien", "SWKS": "Technologie", "SJM": "Konsum (Basis)",
    "SW": "Rohstoffe", "SNA": "Industrie", "SOLV": "Gesundheit", "SO": "Versorger", "LUV": "Industrie", "SWK": "Industrie",
    "SBUX": "Konsum (zyklisch)", "STT": "Finanzen", "STLD": "Rohstoffe", "STE": "Gesundheit", "SYK": "Gesundheit", "SMCI": "Technologie",
    "SYF": "Finanzen", "SNPS": "Technologie", "SYY": "Konsum (Basis)", "TMUS": "Kommunikation", "TROW": "Finanzen", "TTWO": "Kommunikation",
    "TPR": "Konsum (zyklisch)", "TRGP": "Energie", "TGT": "Konsum (Basis)", "TEL": "Technologie", "TDY": "Technologie", "TER": "Technologie",
    "TSLA": "Konsum (zyklisch)", "TXN": "Technologie", "TPL": "Energie", "TXT": "Industrie", "TMO": "Gesundheit", "TJX": "Konsum (zyklisch)",
    "TKO": "Kommunikation", "TTD": "Kommunikation", "TSCO": "Konsum (zyklisch)", "TT": "Industrie", "TDG": "Industrie", "TRV": "Finanzen",
    "TRMB": "Technologie", "TFC": "Finanzen", "TYL": "Technologie", "TSN": "Konsum (Basis)", "USB": "Finanzen", "UBER": "Industrie",
    "UDR": "Immobilien", "ULTA": "Konsum (zyklisch)", "UNP": "Industrie", "UAL": "Industrie", "UPS": "Industrie", "URI": "Industrie",
    "UNH": "Gesundheit", "UHS": "Gesundheit", "VLO": "Energie", "VEEV": "Gesundheit", "VTR": "Immobilien", "VLTO": "Industrie",
    "VRSN": "Technologie", "VRSK": "Industrie", "VZ": "Kommunikation", "VRTX": "Gesundheit", "VRT": "Industrie", "VTRS": "Gesundheit",
    "VICI": "Immobilien", "V": "Finanzen", "VST": "Versorger", "VMC": "Rohstoffe", "WRB": "Finanzen", "GWW": "Industrie",
    "WAB": "Industrie", "WMT": "Konsum (Basis)", "DIS": "Kommunikation", "WBD": "Kommunikation", "WM": "Industrie", "WAT": "Gesundheit",
    "WEC": "Versorger", "WFC": "Finanzen", "WELL": "Immobilien", "WST": "Gesundheit", "WDC": "Technologie", "WY": "Immobilien",
    "WSM": "Konsum (zyklisch)", "WMB": "Energie", "WTW": "Finanzen", "WDAY": "Technologie", "WYNN": "Konsum (zyklisch)", "XEL": "Versorger",
    "XYL": "Industrie", "YUM": "Konsum (zyklisch)", "ZBRA": "Technologie", "ZBH": "Gesundheit", "ZTS": "Gesundheit",
}
# ---------------------------------------------------------------------------
# SESSION STATE INITIALISIEREN
# ---------------------------------------------------------------------------
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60
if 'selected_ticker_t1' not in st.session_state:
    st.session_state.selected_ticker_t1 = "AAPL"
if 'selected_ticker_t3' not in st.session_state:
    st.session_state.selected_ticker_t3 = "AAPL"

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title('📈 Aktien Signal-Tool')
    st.caption('Technische Analyse — keine Finanzberatung')
    st.divider()

    st.subheader('🔄 Auto-Refresh')
    r_col1, r_col2 = st.columns(2)
    auto_refresh = r_col1.toggle('Aktiv', value=st.session_state.auto_refresh, key='ar_toggle')
    refresh_interval = r_col2.selectbox('Intervall', [30, 60, 120, 300],
        index=[30,60,120,300].index(st.session_state.refresh_interval),
        format_func=lambda x: f"{x} Sek", key='ar_interval')
    st.session_state.auto_refresh = auto_refresh
    st.session_state.refresh_interval = refresh_interval
    if auto_refresh:
        st.caption(f'✅ Aktualisiert alle {refresh_interval} Sek.')
    else:
        st.caption('Manuell — Daten eingefroren bis Neustart.')

    st.divider()
    st.subheader('⭐ Meine Watchlist')
    col_in, col_btn = st.columns([3, 1])
    new_fav = col_in.text_input('Ticker', placeholder='z.B. NVDA', label_visibility='collapsed', key='new_fav')
    if col_btn.button('➕', key='add_fav'):
        t = new_fav.strip().upper()
        if t and t not in st.session_state.favorites:
            st.session_state.favorites.append(t)
            st.rerun()

    if st.session_state.favorites:
        for fav in list(st.session_state.favorites):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f'`{fav}`')
            if c2.button('✕', key=f'rm_{fav}'):
                st.session_state.favorites.remove(fav)
                st.rerun()
    else:
        st.caption('Noch leer — füge Ticker hinzu.')

    st.divider()
    st.subheader('🤖 Claude API (optional)')
    claude_api_key = st.text_input(
        'Anthropic API-Key',
        type='password',
        help='Für bessere News-Analyse. Holen unter console.anthropic.com → API Keys.',
        key='claude_api_key',
        label_visibility='collapsed',
        placeholder='sk-ant-...',
    )
    if claude_api_key:
        st.caption('✅ KI-Analyse aktiv')
    else:
        st.caption('Ohne Key: einfache Wortzählung')

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(['📊 Analyse', '🔥 Scanner', '🔮 Projektion & News', '🌍 Märkte'])


# ---------------------------------------------------------------------------
# TAB 1: ANALYSE
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("📊 Aktien-Analyse")


    # --- TICKER-SUCHE ---
    s_c1, s_c2 = st.columns([3, 2])
    search_query = s_c1.text_input(
        "Firmenname oder Ticker suchen",
        placeholder="z.B. Apple, Lufthansa, NVDA ...",
        key="t1_search"
    )
    fav_pick = "—"
    if st.session_state.get("favorites"):
        fav_pick = s_c2.selectbox("Aus Watchlist", ["—"] + st.session_state.favorites, key="t1_fav")

    if fav_pick != "—":
        st.session_state.selected_ticker_t1 = fav_pick

    elif search_query and len(search_query) >= 2:
        with st.spinner("Suche..."):
            suggestions = search_ticker(search_query)
        if suggestions:
            options = [f"{s['symbol']} — {s['name']} ({s['exchange']})" for s in suggestions]
            chosen = st.selectbox("Treffer — bitte auswählen:", options, key="t1_pick")
            if chosen:
                new_ticker = chosen.split(" — ")[0].strip()
                if new_ticker != st.session_state.selected_ticker_t1:
                    st.session_state.selected_ticker_t1 = new_ticker
                    st.rerun()
        else:
            st.warning(
                f"Keine börsennotierten Treffer für '{search_query}' gefunden. "
                "Manche Unternehmen (z.B. SpaceX) sind nicht börsennotiert und haben keinen Ticker."
            )

    ticker = st.session_state.selected_ticker_t1
    st.caption(f"📌 Aktuell geladen: **{ticker}**")


    a_col1, a_col2 = st.columns(2)
    short_w = a_col1.slider("Kurzer MA (Tage)", 2, 50, 20, key="t1_short")
    long_w  = a_col2.slider("Langer MA (Tage)", 5, 200, 50, key="t1_long")

    opt_col1, opt_col2 = st.columns(2)
    show_market = opt_col1.checkbox("Mit S&P 500 vergleichen", key="t1_spx")
    show_season = opt_col2.checkbox("Saisonalität anzeigen", key="t1_season")

    if ticker:
        close = get_close(ticker, days=max(long_w + 30, 120))
        if close is None or len(close) < long_w + 2:
            st.warning(f"Nicht genug Daten für {ticker}.")
        else:
            ma = compute_ma_signal(close, short_w, long_w)
            if ma is None:
                st.warning("Nicht genug Daten für die gewählten MA-Zeiträume.")
            else:
                # --- KENNZAHLEN ---
                rsi_val = compute_rsi(close)
                mom_val = compute_momentum(close)
                ampel, ampel_label, votes = build_ampel(ma, rsi_val, mom_val)

                # Ampel als Herzstück oben
                st.markdown("### 🚦 Strategie-Ampel")
                ampel_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[ampel]
                if ampel == "green":
                    st.success(f"{ampel_icon} **{ampel_label}**")
                elif ampel == "red":
                    st.error(f"{ampel_icon} **{ampel_label}**")
                else:
                    st.warning(f"{ampel_icon} **{ampel_label}**")

                v1, v2, v3 = st.columns(3)
                icons = {1: "🟢", -1: "🔴", 0: "⚪"}
                v1.metric("MA-Crossover", icons[votes["MA-Crossover"][0]], votes["MA-Crossover"][1])
                v2.metric("RSI", icons[votes["RSI"][0]], votes["RSI"][1])
                v3.metric("Momentum", icons[votes["Momentum"][0]], votes["Momentum"][1])

                st.divider()

                # --- CHART ---
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=close.index, y=close, name="Kurs", line=dict(color="#888780", width=1.5)))
                fig.add_trace(go.Scatter(x=close.index, y=ma["short_ma"], name=f"MA{short_w}", line=dict(color="#1D9E75", width=2)))
                fig.add_trace(go.Scatter(x=close.index, y=ma["long_ma"], name=f"MA{long_w}", line=dict(color="#D85A30", width=2)))

                if show_market:
                    bench = get_close("^GSPC", days=max(long_w + 30, 120))
                    if bench is not None:
                        common = max(close.index[0], bench.index[0])
                        s_norm = (close[close.index >= common] / close[close.index >= common].iloc[0]) * float(close[close.index >= common].iloc[0])
                        b_raw  = bench[bench.index >= common]
                        b_scaled = b_raw / float(b_raw.iloc[0]) * float(close[close.index >= common].iloc[0])
                        fig.add_trace(go.Scatter(x=b_scaled.index, y=b_scaled, name="S&P 500 (skaliert)", line=dict(color="gray", width=1.5, dash="dot")))

                fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02))
                st.plotly_chart(fig, use_container_width=True)

                # --- INTRADAY CHART ---
                with st.expander("📡 Heutiger Intraday-Verlauf (5-Min-Takt)"):
                    with st.spinner("Lade Live-Daten..."):
                        intraday = get_intraday(ticker)
                    if intraday is not None and len(intraday) > 3:
                        fig_id = go.Figure()
                        fig_id.add_trace(go.Scatter(
                            x=intraday.index, y=intraday,
                            name="Kurs (5 Min)", line=dict(color="#1D9E75", width=1.5),
                            fill="tozeroy", fillcolor="rgba(29,158,117,0.08)"
                        ))
                        open_price = float(intraday.iloc[0])
                        fig_id.add_hline(y=open_price, line_dash="dot", line_color="gray",
                                         annotation_text="Eröffnung", annotation_position="bottom right")
                        fig_id.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10),
                                             showlegend=False, yaxis_title="Kurs")
                        last = float(intraday.iloc[-1])
                        pct = (last - open_price) / open_price * 100
                        id_icon = "🟢" if pct >= 0 else "🔴"
                        st.caption(f"{id_icon} Aktuell: **{last:.2f}** ({pct:+.2f}% seit Eröffnung) — Live-Daten (5-Min-Takt, Börsenstunden)")
                        st.plotly_chart(fig_id, use_container_width=True)
                    else:
                        st.caption("Keine Intraday-Daten verfügbar (Markt möglicherweise geschlossen oder Daten noch nicht geladen).")

                # --- RISIKO-KENNZAHLEN ---
                with st.expander("📐 Risiko-Kennzahlen anzeigen"):
                    risk = compute_risk(close)
                    if risk:
                        r1, r2, r3 = st.columns(3)
                        sharpe_label = "gut" if risk["sharpe"] > 1 else ("mäßig" if risk["sharpe"] > 0 else "schwach")
                        r1.metric("Sharpe Ratio", f"{risk['sharpe']:.2f}", sharpe_label)
                        r2.metric("Volatilität (p.a.)", f"{risk['ann_vol']*100:.1f}%")
                        r3.metric("Max. Drawdown", f"{risk['max_drawdown']*100:.1f}%")
                        fig_dd = go.Figure()
                        fig_dd.add_trace(go.Scatter(
                            x=risk["drawdown_series"].index, y=risk["drawdown_series"] * 100,
                            fill="tozeroy", fillcolor="rgba(216,90,48,0.2)",
                            line=dict(color="#D85A30", width=1), name="Drawdown %"
                        ))
                        fig_dd.update_layout(height=160, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, yaxis_title="Drawdown %")
                        st.plotly_chart(fig_dd, use_container_width=True)

                # --- SAISONALITÄT ---
                if show_season:
                    with st.spinner("Lade Saisonalitätsdaten..."):
                        season = get_seasonality(ticker)
                    if season is not None:
                        st.markdown("**📅 Ø Monatsrendite (letzte 5 Jahre)**")
                        fig_s = go.Figure()
                        fig_s.add_trace(go.Bar(
                            x=season.index, y=season.values,
                            marker_color=["#1D9E75" if v >= 0 else "#D85A30" for v in season.values],
                            text=[f"{v:+.1f}%" if not np.isnan(v) else "" for v in season.values],
                            textposition="outside",
                        ))
                        fig_s.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Ø Rendite %")
                        st.plotly_chart(fig_s, use_container_width=True)
                        st.caption("Rein statistisch, keine Garantie. Einzeljahre können stark abweichen.")
                    else:
                        st.caption("Nicht genug historische Daten für Saisonalität.")

    st.caption("Keine Finanzberatung. Technische Analyse auf Basis historischer Tageskurse.")

# ---------------------------------------------------------------------------
# TAB 2: SCANNER
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("🔥 Markt-Scanner")
    st.caption(f"Durchsucht alle {len(WATCHLIST)} S&P-500-Aktien nach der stärksten Kursbewegung.")

    s_col1, s_col2 = st.columns(2)
    lookback = s_col1.slider("Zeitraum (Tage)", 1, 30, 5, key="t2_lb")
    top_n    = s_col2.slider("Top-Anzahl anzeigen", 3, 20, 8, key="t2_top")

    if st.button("🔍 Jetzt scannen", type="primary", key="t2_scan"):
        with st.spinner(f"Durchsuche {len(WATCHLIST)} Aktien … (ca. 20–40 Sek.)"):
            df = scan_market(WATCHLIST, lookback)

        if df.empty:
            st.warning("Keine Daten erhalten, bitte später erneut versuchen.")
        else:
            df = df.sort_values("Veränderung %", ascending=False)

            g_col, l_col = st.columns(2)

            with g_col:
                st.markdown(f"**🚀 Top {top_n} Gewinner**")
                gainers = df.head(top_n).reset_index(drop=True)
                st.dataframe(gainers.style.format({"Kurs": "{:.2f}", "Veränderung %": "{:+.2f}%"}),
                             use_container_width=True, hide_index=True)

            with l_col:
                st.markdown(f"**📉 Top {top_n} Verlierer**")
                losers = df.tail(top_n).sort_values("Veränderung %").reset_index(drop=True)
                st.dataframe(losers.style.format({"Kurs": "{:.2f}", "Veränderung %": "{:+.2f}%"}),
                             use_container_width=True, hide_index=True)

            st.divider()
            st.markdown(f"**🏭 Sektor-Übersicht (Ø {lookback}-Tage)**")
            df["Sektor"] = df["Ticker"].map(SECTOR_MAP).fillna("Sonstige")
            sector_avg = df.groupby("Sektor")["Veränderung %"].mean().round(2).sort_values(ascending=False).reset_index()
            sector_avg.columns = ["Sektor", "Ø %"]
            fig_sec = go.Figure(go.Bar(
                x=sector_avg["Sektor"], y=sector_avg["Ø %"],
                marker_color=["#1D9E75" if v >= 0 else "#D85A30" for v in sector_avg["Ø %"]],
                text=sector_avg["Ø %"].apply(lambda v: f"{v:+.2f}%"), textposition="outside",
            ))
            fig_sec.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=80),
                                  yaxis_title="Ø Veränderung %", xaxis_tickangle=-35)
            st.plotly_chart(fig_sec, use_container_width=True)
            st.caption(f"Stand: {datetime.now().strftime('%H:%M:%S')} — Ergebnis wird 5 Min. zwischengespeichert.")
    else:
        st.info("Klick auf 'Jetzt scannen', um zu starten.")

# ---------------------------------------------------------------------------
# TAB 3: PROJEKTION & NEWS
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("🔮 Projektion & News")
    st.warning("Keine Vorhersage — statistische Hochrechnung auf Basis historischer Kurse. Echte Kurse können stark abweichen.")


    # --- TICKER-SUCHE ---
    s_c1, s_c2 = st.columns([3, 2])
    search_query_t3 = s_c1.text_input(
        "Firmenname oder Ticker suchen",
        placeholder="z.B. Apple, Lufthansa, NVDA ...",
        key="t3_search"
    )
    fav_pick_t3 = "—"
    if st.session_state.get("favorites"):
        fav_pick_t3 = s_c2.selectbox("Aus Watchlist", ["—"] + st.session_state.favorites, key="t3_fav")

    if fav_pick_t3 != "—":
        st.session_state.selected_ticker_t3 = fav_pick_t3

    elif search_query_t3 and len(search_query_t3) >= 2:
        with st.spinner("Suche..."):
            suggestions_t3 = search_ticker(search_query_t3)
        if suggestions_t3:
            options_t3 = [f"{s['symbol']} — {s['name']} ({s['exchange']})" for s in suggestions_t3]
            chosen_t3 = st.selectbox("Treffer — bitte auswählen:", options_t3, key="t3_pick")
            if chosen_t3:
                new_ticker_t3 = chosen_t3.split(" — ")[0].strip()
                if new_ticker_t3 != st.session_state.selected_ticker_t3:
                    st.session_state.selected_ticker_t3 = new_ticker_t3
                    st.rerun()
        else:
            st.warning(
                f"Keine börsennotierten Treffer für '{search_query_t3}' gefunden. "
                "Manche Unternehmen (z.B. SpaceX) sind nicht börsennotiert und haben keinen Ticker."
            )

    proj_ticker = st.session_state.selected_ticker_t3
    st.caption(f"📌 Aktuell geladen: **{proj_ticker}**")


    pc1, pc2, pc3 = st.columns(3)
    hist_days     = pc1.slider("Vergangene Tage", 20, 250, 90, key="t3_hist")
    horizon_days  = pc2.slider("Projektion (Tage)", 5, 60, 20, key="t3_hor")
    news_strength = pc3.slider("News-Einfluss", 0, 100, 30, key="t3_ns",
                               help="0 = reine Mathematik, höher = News verschieben die Projektion stärker")

    if proj_ticker:
        close = get_close(proj_ticker, days=hist_days + 30)
        if close is None or len(close) < 20:
            st.warning(f"Nicht genug Daten für {proj_ticker}.")
        else:
            close = close.tail(hist_days)
            log_ret = np.log(close / close.shift(1)).dropna()
            base_drift = log_ret.mean()
            vol = log_ret.std()
            last_price = float(close.iloc[-1])

            # News laden + Stimmung
            news_items = get_news(proj_ticker)
            score = 0.0
            claude_reasoning, claude_items = None, []
            pos_hits, neg_hits, matched = 0, 0, []
            using_claude = False

            if news_strength > 0:
                using_claude = bool(claude_api_key)
                if using_claude:
                    with st.spinner("Claude analysiert Schlagzeilen..."):
                        score, claude_reasoning, claude_items = claude_sentiment(news_items, proj_ticker, claude_api_key)
                    if score is None:
                        st.error(claude_reasoning)
                        using_claude = False
                        score, pos_hits, neg_hits, matched = simple_sentiment(news_items)
                        score = score if score else 0.0
                else:
                    _score, pos_hits, neg_hits, matched = simple_sentiment(news_items)
                    score = _score

            adj_drift = base_drift + score * vol * (news_strength / 100.0)
            t_arr = np.arange(1, horizon_days + 1)
            math_proj  = last_price * np.exp(base_drift * t_arr)
            combo_proj = last_price * np.exp(adj_drift * t_arr)
            upper_95   = last_price * np.exp(adj_drift * t_arr + 1.96 * vol * np.sqrt(t_arr))
            lower_95   = last_price * np.exp(adj_drift * t_arr - 1.96 * vol * np.sqrt(t_arr))
            future_dates = [close.index[-1] + timedelta(days=int(d)) for d in t_arr]

            # Kennzahlen
            m1, m2, m3 = st.columns(3)
            m1.metric("Aktueller Kurs", f"{last_price:.2f}")
            m2.metric(f"Mathe-Schätzung +{horizon_days}T", f"{math_proj[-1]:.2f}", f"{(math_proj[-1]/last_price-1)*100:+.1f}%")
            if news_strength > 0:
                m3.metric("Mit News-Einfluss", f"{combo_proj[-1]:.2f}", f"{(combo_proj[-1]/math_proj[-1]-1)*100:+.2f}% Drift")
            else:
                m3.metric("Tages-Volatilität", f"{vol*100:.2f}%")

            # Stimmungsanzeige
            if news_strength > 0:
                if using_claude:
                    label_src = "🤖 Laut Claude"
                else:
                    label_src = "📝 Laut Wortzählung"
                if score > 0.15:
                    st.success(f"{label_src}: eher positive Nachrichtenlage (Score {score:+.2f})")
                elif score < -0.15:
                    st.error(f"{label_src}: eher negative Nachrichtenlage (Score {score:+.2f})")
                else:
                    st.info(f"{label_src}: neutrale/gemischte Nachrichtenlage (Score {score:+.2f})")
                if using_claude and claude_reasoning:
                    st.caption(f"Begründung: {claude_reasoning}")

            # Chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=close.index, y=close, name="Verlauf", line=dict(color="gray", width=1.5)))
            fig.add_trace(go.Scatter(x=future_dates, y=upper_95, line=dict(width=0), showlegend=False))
            fig.add_trace(go.Scatter(x=future_dates, y=lower_95, fill="tonexty",
                                     fillcolor="rgba(255,165,0,0.15)", name="95% Korridor"))
            fig.add_trace(go.Scatter(x=future_dates, y=math_proj, name="Nur Mathe",
                                     line=dict(color="gray", width=2, dash="dot")))
            if news_strength > 0:
                fig.add_trace(go.Scatter(x=future_dates, y=combo_proj, name="Mathe + News",
                                         line=dict(color="orange", width=2, dash="dash")))
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                              legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig, use_container_width=True)

            # Detail-Aufklapper
            if using_claude and claude_items:
                with st.expander(f"Claude-Bewertung der {len(claude_items)} Schlagzeilen"):
                    for ci in claude_items:
                        icon = {"positiv":"🟢","negativ":"🔴","neutral":"⚪"}.get(ci.get("sentiment","neutral"),"⚪")
                        st.caption(f"{icon} {ci.get('headline','')} — {ci.get('sentiment','')} · Relevanz: {ci.get('relevance','')}")
            elif not using_claude and matched:
                with st.expander(f"Erkannte Signalwörter ({len(matched)})"):
                    seen = set()
                    for title, kind, word in matched:
                        if (title, word) not in seen:
                            seen.add((title, word))
                            icon = "🟢" if kind == "positiv" else "🔴"
                            st.caption(f"{icon} '{word}' in: {title}...")

            st.divider()
            st.markdown(f"**📰 Aktuelle Schlagzeilen zu {proj_ticker}**")
            if not news_items:
                st.caption("Keine Nachrichten gefunden.")
            else:
                for item in news_items[:8]:
                    cb = item.get("content", item)
                    title = cb.get("title") or item.get("title")
                    link = (cb.get("canonicalUrl", {}).get("url")
                            if isinstance(cb.get("canonicalUrl"), dict) else item.get("link"))
                    if title:
                        st.markdown(f"- [{title}]({link})" if link else f"- {title}")

# ---------------------------------------------------------------------------
# TAB 4: LIVE-MÄRKTE
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("🌍 Live-Marktübersicht")
    st.caption("Tageskurse — kein Echtzeit-Tick.")

    if st.button("🔄 Aktualisieren", key="t4_refresh"):
        st.cache_data.clear()

    # --- MARKTINDIZES ---
    with st.spinner("Lade Marktdaten..."):
        market = get_market_overview()

    if not market:
        st.warning("Keine Marktdaten verfügbar.")
    else:
        row1 = market[:3]
        cols = st.columns(len(row1))
        for i, q in enumerate(row1):
            icon = "🟢" if q["pct"] >= 0 else "🔴"
            cols[i].metric(f"{icon} {q['name']}", f"{q['price']:,.2f}", f"{q['pct']:+.2f}%")
        st.markdown("")
        row2 = market[3:]
        if row2:
            cols2 = st.columns(len(row2))
            for i, q in enumerate(row2):
                icon = "🟢" if q["pct"] >= 0 else "🔴"
                cols2[i].metric(f"{icon} {q['name']}", f"{q['price']:,.2f}", f"{q['pct']:+.2f}%")

    st.divider()

    # --- ETFs ---
    st.markdown("**📦 Beliebte ETFs**")
    ETFS = {
        "S&P 500 (SPY)": "SPY",
        "Nasdaq 100 (QQQ)": "QQQ",
        "Welt (VT)": "VT",
        "Europa (VGK)": "VGK",
        "Emerging Markets (EEM)": "EEM",
        "Gold (GLD)": "GLD",
        "Anleihen (TLT)": "TLT",
        "Immobilien (VNQ)": "VNQ",
    }

    @st.cache_data(ttl=300, show_spinner=False)
    def get_etf_quotes(symbols):
        rows = []
        for name, sym in symbols.items():
            try:
                d = yf.download(sym, period="2d", interval="1d", progress=False)
                if d.empty or len(d) < 2:
                    continue
                close = d["Close"].iloc[:, 0] if isinstance(d["Close"], pd.DataFrame) else d["Close"]
                close = close.dropna()
                if len(close) < 2:
                    continue
                prev, curr = float(close.iloc[-2]), float(close.iloc[-1])
                pct = (curr - prev) / prev * 100
                rows.append({"name": name, "price": curr, "pct": pct})
            except Exception:
                pass
        return rows

    with st.spinner("Lade ETF-Daten..."):
        etf_data = get_etf_quotes(ETFS)

    if etf_data:
        etf_col1, etf_col2 = st.columns(2)
        for i, q in enumerate(etf_data):
            col = etf_col1 if i % 2 == 0 else etf_col2
            icon = "🟢" if q["pct"] >= 0 else "🔴"
            col.metric(f"{icon} {q['name']}", f"{q['price']:.2f}", f"{q['pct']:+.2f}%")

    st.divider()

    # --- WATCHLIST-AKTIEN ---
    st.markdown("**⭐ Meine Watchlist**")
    if not st.session_state.favorites:
        st.caption("Noch keine Favoriten — füge Ticker in der Sidebar hinzu.")
    else:
        @st.cache_data(ttl=300, show_spinner=False)
        def get_watchlist_quotes(tickers):
            rows = []
            def fetch(t):
                try:
                    d = yf.download(t, period="2d", interval="1d", progress=False)
                    if d.empty or len(d) < 2:
                        return None
                    close = d["Close"].iloc[:, 0] if isinstance(d["Close"], pd.DataFrame) else d["Close"]
                    close = close.dropna()
                    if len(close) < 2:
                        return None
                    prev, curr = float(close.iloc[-2]), float(close.iloc[-1])
                    pct = (curr - prev) / prev * 100
                    return {"ticker": t, "price": curr, "pct": pct}
                except Exception:
                    return None
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
                results = list(ex.map(fetch, tickers))
            return [r for r in results if r]

        with st.spinner("Lade Watchlist-Kurse..."):
            wl_data = get_watchlist_quotes(tuple(st.session_state.favorites))

        if wl_data:
            wl_col1, wl_col2 = st.columns(2)
            for i, q in enumerate(wl_data):
                col = wl_col1 if i % 2 == 0 else wl_col2
                icon = "🟢" if q["pct"] >= 0 else "🔴"
                col.metric(f"{icon} {q['ticker']}", f"{q['price']:.2f}", f"{q['pct']:+.2f}%")
        else:
            st.caption("Kurse konnten nicht geladen werden.")

    st.divider()
    st.caption(f"Letzte Aktualisierung: {datetime.now().strftime('%H:%M:%S')}")
    st.caption("Keine Finanzberatung. Alle Daten über Yahoo Finance (Tageskurse).")

# ---------------------------------------------------------------------------
# AUTO-REFRESH
# ---------------------------------------------------------------------------
if st.session_state.get('auto_refresh'):
    import time
    interval = st.session_state.get('refresh_interval', 60)
    now = datetime.now().strftime('%H:%M:%S')
    st.sidebar.caption(f'⏱ Nächste Aktualisierung in {interval} Sek. (Stand: {now})')
    time.sleep(interval)
    st.cache_data.clear()
    st.rerun()
