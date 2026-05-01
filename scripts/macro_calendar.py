"""
Macro Calendar — Upcoming earnings, economic events, and Fed decisions.

Usage:
    from scripts.macro_calendar import get_earnings_calendar, get_economic_events
    from scripts.macro_calendar import get_macro_summary, days_until_event
"""
import os, sys
from datetime import datetime, date, timedelta

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

FOMC_DATES = [
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-17",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-16",
]

CPI_DATES = [
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13",
    "2025-06-11", "2025-07-11", "2025-08-12", "2025-09-10", "2025-10-14",
    "2025-11-12", "2025-12-10",
    "2026-01-14", "2026-02-11", "2026-03-11", "2026-04-14", "2026-05-12",
    "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-15", "2026-10-13",
    "2026-11-10", "2026-12-10",
]

JOBS_DATES = [
    "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04", "2025-05-02",
    "2025-06-06", "2025-07-03", "2025-08-01", "2025-09-05", "2025-10-03",
    "2025-11-07", "2025-12-05",
    "2026-01-09", "2026-02-06", "2026-03-06", "2026-04-03", "2026-05-01",
    "2026-06-05", "2026-07-02", "2026-08-07", "2026-09-04", "2026-10-02",
    "2026-11-06", "2026-12-04",
]

OPEX_DATES = [
    "2025-03-21", "2025-06-20", "2025-09-19", "2025-12-19",
    "2026-03-20", "2026-06-19", "2026-09-18", "2026-12-18",
]


def _parse_date(d):
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    try:
        return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def days_until_event(event_date):
    d = _parse_date(event_date)
    if not d:
        return None
    return (d - date.today()).days


def get_earnings_calendar(tickers):
    results = []
    try:
        import yfinance as yf
    except ImportError:
        return results
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            cal = stock.calendar
            earn_date = None
            if cal is not None:
                if isinstance(cal, dict):
                    ed = cal.get("Earnings Date")
                    if ed:
                        earn_date = ed[0] if isinstance(ed, list) and len(ed) > 0 else ed
                elif hasattr(cal, "iloc"):
                    try:
                        earn_date = cal.iloc[0, 0] if cal.shape[0] > 0 else None
                    except Exception:
                        pass
            if earn_date is None:
                try:
                    edates = stock.earnings_dates
                    if edates is not None and len(edates) > 0:
                        today = datetime.now()
                        future = [d for d in edates.index if d >= today]
                        if future:
                            earn_date = future[0]
                except Exception:
                    pass
            if earn_date is not None:
                d = _parse_date(earn_date)
                if d:
                    days = (d - date.today()).days
                    results.append({
                        "ticker": ticker,
                        "earnings_date": d.isoformat(),
                        "days_until": days,
                        "is_upcoming": 0 <= days <= 14,
                        "is_imminent": 0 <= days <= 3,
                    })
        except Exception:
            continue
    return sorted(results, key=lambda x: x.get("days_until", 999))


def get_economic_events(days_ahead=14):
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    events = []
    for d in FOMC_DATES:
        dt = _parse_date(d)
        if dt and today <= dt <= cutoff:
            events.append({"event": "FOMC Rate Decision", "date": dt.isoformat(),
                           "days_until": (dt - today).days, "impact": "HIGH",
                           "description": "Federal Reserve interest rate decision",
                           "affects": "All sectors — especially REITs, banks, growth stocks"})
    for d in CPI_DATES:
        dt = _parse_date(d)
        if dt and today <= dt <= cutoff:
            events.append({"event": "CPI Report", "date": dt.isoformat(),
                           "days_until": (dt - today).days, "impact": "HIGH",
                           "description": "Consumer Price Index — key inflation measure",
                           "affects": "Rate-sensitive sectors, growth vs value rotation"})
    for d in JOBS_DATES:
        dt = _parse_date(d)
        if dt and today <= dt <= cutoff:
            events.append({"event": "Jobs Report (NFP)", "date": dt.isoformat(),
                           "days_until": (dt - today).days, "impact": "HIGH",
                           "description": "Non-Farm Payrolls — labor market health",
                           "affects": "Consumer discretionary, industrials, broad market"})
    for d in OPEX_DATES:
        dt = _parse_date(d)
        if dt and today <= dt <= cutoff:
            events.append({"event": "Triple Witching (OPEX)", "date": dt.isoformat(),
                           "days_until": (dt - today).days, "impact": "MEDIUM",
                           "description": "Index futures, index options, stock options all expire",
                           "affects": "Elevated volatility, especially last 2 hours of trading"})
    return sorted(events, key=lambda x: x.get("days_until", 999))


def get_macro_summary(tickers=None, days_ahead=14):
    tickers = tickers or []
    earnings = get_earnings_calendar(tickers) if tickers else []
    events = get_economic_events(days_ahead)
    risk_flags = []
    imminent = [e for e in earnings if e.get("is_imminent")]
    if imminent:
        tickers_str = ", ".join(e["ticker"] for e in imminent)
        risk_flags.append({"flag": "EARNINGS_IMMINENT", "severity": "HIGH",
                           "message": f"Earnings within 3 days: {tickers_str} — expect volatility"})
    upcoming = [e for e in earnings if e.get("is_upcoming") and not e.get("is_imminent")]
    if upcoming:
        tickers_str = ", ".join(f"{e['ticker']} ({e['days_until']}d)" for e in upcoming)
        risk_flags.append({"flag": "EARNINGS_UPCOMING", "severity": "MEDIUM",
                           "message": f"Earnings within 14 days: {tickers_str}"})
    high_events = [e for e in events if e.get("impact") == "HIGH" and e.get("days_until", 99) <= 5]
    for ev in high_events:
        risk_flags.append({"flag": "MACRO_EVENT", "severity": "HIGH",
                           "message": f"{ev['event']} in {ev['days_until']} day(s) ({ev['date']}) — {ev.get('affects', '')}"})
    return {"earnings_calendar": earnings, "economic_events": events,
            "risk_flags": risk_flags, "checked_at": datetime.now().isoformat()}


def format_macro_summary(summary):
    lines = []
    lines.append(f"  {'─' * 60}")
    lines.append(f"  MACRO CALENDAR")
    lines.append(f"  {'─' * 60}")
    for f in summary.get("risk_flags", []):
        icon = "🔴" if f["severity"] == "HIGH" else "🟡"
        lines.append(f"  {icon} {f['message']}")
    earnings = summary.get("earnings_calendar", [])
    if earnings:
        lines.append(f"  UPCOMING EARNINGS:")
        for e in earnings:
            days = e["days_until"]
            marker = " *** IMMINENT" if e.get("is_imminent") else ""
            lines.append(f"    {e['ticker']:<8} {e['earnings_date']}  (in {days}d){marker}")
    events = summary.get("economic_events", [])
    if events:
        lines.append(f"  ECONOMIC EVENTS (next 14 days):")
        for ev in events[:8]:
            lines.append(f"    [{ev.get('impact', '?')}] {ev['event']} — {ev['date']} (in {ev['days_until']}d)")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Macro Calendar")
    parser.add_argument("tickers", nargs="*", help="Tickers to check earnings for")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()
    summary = get_macro_summary(tickers=args.tickers, days_ahead=args.days)
    print(format_macro_summary(summary))
