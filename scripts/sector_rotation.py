"""
Sector Rotation Tracker — Tracks 11 sector ETFs vs SPY for relative strength.

Usage:
    from scripts.sector_rotation import get_sector_rotation, get_sector_modifier
    rotation = get_sector_rotation()
    modifier = get_sector_modifier("Technology")  # -0.5 to +0.5 score adjustment
"""
import os, sys
from datetime import datetime, date, timedelta

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

SECTOR_ETFS = {
    "XLK":  "Technology", "XLF":  "Financials", "XLE":  "Energy",
    "XLV":  "Healthcare", "XLI":  "Industrials", "XLY":  "Consumer Discretionary",
    "XLP":  "Consumer Staples", "XLU":  "Utilities", "XLRE": "Real Estate",
    "XLC":  "Communication Services", "XLB":  "Materials",
}

SECTOR_NAME_MAP = {
    "technology": "Technology", "information technology": "Technology",
    "financial services": "Financials", "financials": "Financials",
    "energy": "Energy", "healthcare": "Healthcare", "health care": "Healthcare",
    "industrials": "Industrials", "consumer cyclical": "Consumer Discretionary",
    "consumer discretionary": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples", "consumer staples": "Consumer Staples",
    "utilities": "Utilities", "real estate": "Real Estate",
    "communication services": "Communication Services",
    "basic materials": "Materials", "materials": "Materials",
    "fixed income": "Fixed Income", "broad market": "Broad Market", "other": "Other",
}

_sector_cache = {"data": None, "timestamp": None}
CACHE_TTL_MINUTES = 30


def get_sector_rotation(force_refresh=False):
    if not force_refresh and _sector_cache["data"] and _sector_cache["timestamp"]:
        age = (datetime.now() - _sector_cache["timestamp"]).total_seconds() / 60
        if age < CACHE_TTL_MINUTES:
            return _sector_cache["data"]
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed", "sectors": []}
    all_tickers = list(SECTOR_ETFS.keys()) + ["SPY"]
    try:
        data = yf.download(all_tickers, period="6mo", group_by="ticker",
                           progress=False, auto_adjust=True)
    except Exception as e:
        return {"error": f"Download failed: {e}", "sectors": []}
    if data is None or data.empty:
        return {"error": "No data returned", "sectors": []}
    spy_returns = _compute_returns(data, "SPY")
    if not spy_returns:
        return {"error": "SPY data unavailable", "sectors": []}
    sectors = []
    for etf, name in SECTOR_ETFS.items():
        returns = _compute_returns(data, etf)
        if not returns:
            continue
        rel_1w = returns["perf_1w"] - spy_returns["perf_1w"]
        rel_1m = returns["perf_1m"] - spy_returns["perf_1m"]
        rel_3m = returns["perf_3m"] - spy_returns["perf_3m"]
        composite = rel_1w * 0.4 + rel_1m * 0.35 + rel_3m * 0.25
        sectors.append({
            "etf": etf, "name": name,
            "perf_1w": round(returns["perf_1w"], 2),
            "perf_1m": round(returns["perf_1m"], 2),
            "perf_3m": round(returns["perf_3m"], 2),
            "rel_1w": round(rel_1w, 2), "rel_1m": round(rel_1m, 2),
            "rel_3m": round(rel_3m, 2), "composite_rel": round(composite, 2),
        })
    sectors.sort(key=lambda x: -x["composite_rel"])
    for i, s in enumerate(sectors):
        s["rank"] = i + 1
        if s["composite_rel"] > 2.0: s["signal"] = "STRONG OUTPERFORM"
        elif s["composite_rel"] > 0.5: s["signal"] = "OUTPERFORM"
        elif s["composite_rel"] > -0.5: s["signal"] = "IN LINE"
        elif s["composite_rel"] > -2.0: s["signal"] = "UNDERPERFORM"
        else: s["signal"] = "STRONG UNDERPERFORM"
    result = {
        "sectors": sectors,
        "spy": {"perf_1w": round(spy_returns["perf_1w"], 2),
                "perf_1m": round(spy_returns["perf_1m"], 2),
                "perf_3m": round(spy_returns["perf_3m"], 2)},
        "leaders": [s["name"] for s in sectors[:3]],
        "laggards": [s["name"] for s in sectors[-3:]],
        "timestamp": datetime.now().isoformat(),
    }
    _sector_cache["data"] = result
    _sector_cache["timestamp"] = datetime.now()
    return result


def _compute_returns(data, ticker):
    try:
        if ticker in data.columns.get_level_values(0):
            close = data[ticker]["Close"].dropna()
        else:
            close = data["Close"][ticker].dropna() if "Close" in data.columns.get_level_values(0) else None
        if close is None or len(close) < 10:
            return None
        latest = close.iloc[-1]
        w1_price = close.iloc[-6] if len(close) > 5 else close.iloc[0]
        m1_idx = min(22, len(close) - 1)
        m3_idx = min(64, len(close) - 1)
        return {
            "perf_1w": ((latest / w1_price) - 1) * 100,
            "perf_1m": ((latest / close.iloc[-m1_idx]) - 1) * 100,
            "perf_3m": ((latest / close.iloc[-m3_idx]) - 1) * 100,
        }
    except Exception:
        return None


def get_sector_modifier(sector_name, rotation_data=None):
    if not sector_name:
        return 0.0
    rotation = rotation_data or get_sector_rotation()
    if not rotation or not rotation.get("sectors"):
        return 0.0
    normalized = SECTOR_NAME_MAP.get(sector_name.lower(), sector_name)
    sector = next((s for s in rotation["sectors"] if s["name"].lower() == normalized.lower()), None)
    if not sector:
        return 0.0
    rel = sector["composite_rel"]
    if rel > 3.0: return 0.5
    elif rel > 1.5: return 0.35
    elif rel > 0.5: return 0.2
    elif rel > -0.5: return 0.0
    elif rel > -1.5: return -0.2
    elif rel > -3.0: return -0.35
    else: return -0.5


def get_portfolio_sector_exposure(holdings_with_sectors, rotation_data=None):
    rotation = rotation_data or get_sector_rotation()
    sector_counts = {}
    total = len(holdings_with_sectors)
    for h in holdings_with_sectors:
        sector = h.get("sector", "") or ""
        normalized = SECTOR_NAME_MAP.get(sector.lower(), sector) if sector else "Unclassified"
        sector_counts[normalized] = sector_counts.get(normalized, 0) + 1
    breakdown = []
    for sector, count in sorted(sector_counts.items(), key=lambda x: -x[1]):
        weight = count / total if total > 0 else 0
        modifier = get_sector_modifier(sector, rotation)
        signal = next((s.get("signal", "N/A") for s in rotation.get("sectors", [])
                       if s["name"].lower() == sector.lower()), "N/A")
        breakdown.append({"sector": sector, "count": count,
                          "weight_pct": round(weight * 100, 1),
                          "modifier": modifier, "signal": signal})
    warnings = []
    for item in breakdown:
        if item["weight_pct"] > 40:
            warnings.append(f"Heavy concentration in {item['sector']} ({item['weight_pct']}%) — {item['signal']}")
        if item["weight_pct"] > 25 and item["modifier"] < -0.2:
            warnings.append(f"{item['sector']} ({item['weight_pct']}%) is underperforming the market")
    modifiers = [get_sector_modifier(h.get("sector", ""), rotation) for h in holdings_with_sectors]
    avg_mod = sum(modifiers) / len(modifiers) if modifiers else 0
    return {"sector_breakdown": breakdown, "concentration_warnings": warnings,
            "avg_sector_modifier": round(avg_mod, 3)}


def format_sector_rotation(rotation):
    lines = []
    lines.append(f"  {'─' * 60}")
    lines.append(f"  SECTOR ROTATION")
    lines.append(f"  {'─' * 60}")
    spy = rotation.get("spy", {})
    lines.append(f"  S&P 500 (SPY):  1W {spy.get('perf_1w', 0):+.1f}%  |  "
                 f"1M {spy.get('perf_1m', 0):+.1f}%  |  3M {spy.get('perf_3m', 0):+.1f}%")
    lines.append("")
    lines.append(f"  {'Rank':<5} {'Sector':<28} {'1W':>6} {'1M':>6} {'3M':>6} {'vs SPY':>7}  {'Signal'}")
    lines.append(f"  {'─' * 75}")
    for s in rotation.get("sectors", []):
        signal = s.get("signal", "N/A")
        arrow = "▲▲" if "STRONG OUTPERFORM" in signal else ("▲" if "OUTPERFORM" in signal else
                ("▼▼" if "STRONG UNDERPERFORM" in signal else ("▼" if "UNDERPERFORM" in signal else "━")))
        lines.append(f"  {s['rank']:<5} {s['name']:<28} "
                     f"{s['perf_1w']:>+5.1f}% {s['perf_1m']:>+5.1f}% {s['perf_3m']:>+5.1f}% "
                     f"{s['composite_rel']:>+6.1f}%  {arrow} {signal}")
    leaders = rotation.get("leaders", [])
    laggards = rotation.get("laggards", [])
    if leaders: lines.append(f"  Leaders:  {', '.join(leaders)}")
    if laggards: lines.append(f"  Laggards: {', '.join(laggards)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Fetching sector rotation data...\n")
    rotation = get_sector_rotation(force_refresh=True)
    if rotation.get("error"):
        print(f"Error: {rotation['error']}")
    else:
        print(format_sector_rotation(rotation))
