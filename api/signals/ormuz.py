"""
FANTASMA / OBSERVATORIO - Modulo 2: La Coreografia (Ormuz)
O1: Brent Crude (20 pts max)
O2: Gas Natural Europa TTF (10 pts max)
O3: USD/CHF (5 pts max) - Refugio suizo
O4: SOFR (5 pts max) - Estres financiero core
O5: War Risk Premium proxy (10 pts max) - Brent-WTI spread
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Tuple

from .yahoo import fetch_yahoo_quote


async def get_o1_brent() -> Tuple[float, Dict]:
    """O1: Brent Crude (20 pts max). Pre-guerra ~$65."""
    data = await fetch_yahoo_quote("BZ=F")
    if "error" in data:
        return 0, {"signal": "O1_BRENT", "error": data["error"]}
    current = data.get("current", 0)
    closes = data.get("closes", [])
    weekly_change_pct = 0
    if len(closes) >= 5 and closes[-5] > 0:
        weekly_change_pct = ((current - closes[-5]) / closes[-5]) * 100
    score = 0
    if current > 110: score = 20
    elif current > 100: score = 15
    elif current > 90: score = 10
    elif current > 80: score = 5
    if abs(weekly_change_pct) > 10: score = min(score + 5, 20)
    return score, {
        "signal": "O1_BRENT", "value": round(current, 2),
        "weekly_change_pct": round(weekly_change_pct, 2),
        "pre_war_baseline": 65, "score": score, "max_score": 20
    }


async def get_o2_gas_europe() -> Tuple[float, Dict]:
    """O2: Gas Natural Europa TTF (10 pts max). Qatar LNG via Ormuz."""
    data = await fetch_yahoo_quote("TTF=F")
    if "error" in data:
        data = await fetch_yahoo_quote("NG=F")
        if "error" in data:
            return 0, {"signal": "O2_GAS_EU", "error": data["error"]}
    current = data.get("current", 0)
    closes = data.get("closes", [])
    weekly_change_pct = 0
    if len(closes) >= 5 and closes[-5] > 0:
        weekly_change_pct = ((current - closes[-5]) / closes[-5]) * 100
    score = 0
    if current > 70: score = 10
    elif current > 50: score = 7
    elif current > 35: score = 3
    if abs(weekly_change_pct) > 15: score = min(score + 3, 10)
    return score, {
        "signal": "O2_GAS_EU", "value": round(current, 2),
        "weekly_change_pct": round(weekly_change_pct, 2),
        "score": score, "max_score": 10
    }


async def get_o3_usdchf() -> Tuple[float, Dict]:
    """O3: USD/CHF - Refugio real (5 pts max). CHF sube = fuga de capital."""
    data = await fetch_yahoo_quote("CHF=X")
    if "error" in data:
        return 0, {"signal": "O3_USDCHF", "error": data["error"]}
    current = data.get("current", 0)
    closes = data.get("closes", [])
    weekly_change_pct = 0
    if len(closes) >= 5 and closes[-5] > 0:
        weekly_change_pct = ((current - closes[-5]) / closes[-5]) * 100
    score = 0
    if weekly_change_pct < -2: score = 5
    elif weekly_change_pct < -1: score = 3
    return score, {
        "signal": "O3_USDCHF", "value": round(current, 4),
        "weekly_change_pct": round(weekly_change_pct, 2),
        "interpretation": "CHF strengthening" if weekly_change_pct < 0 else "USD strengthening",
        "score": score, "max_score": 5
    }


async def get_o4_sofr() -> Tuple[float, Dict]:
    """O4: SOFR (5 pts max). Estres en nucleo financiero EEUU."""
    from .fred import fetch_fred_series
    data = await fetch_fred_series("SOFR", days=10)
    if not data:
        return 0, {"signal": "O4_SOFR", "error": "No data"}
    valid = [d for d in data if d["value"] != "."]
    if not valid:
        return 0, {"signal": "O4_SOFR", "error": "No valid data"}
    current = float(valid[0]["value"])
    weekly_change_bps = 0
    if len(valid) >= 5:
        week_ago = float(valid[4]["value"])
        weekly_change_bps = (current - week_ago) * 100
    score = 0
    if abs(weekly_change_bps) > 20: score = 5
    elif current > 5.5: score = 3
    return score, {
        "signal": "O4_SOFR", "value": round(current, 4),
        "weekly_change_bps": round(weekly_change_bps, 1),
        "score": score, "max_score": 5
    }


async def get_o5_war_risk() -> Tuple[float, Dict]:
    """O5: War Risk proxy (10 pts max). Brent-WTI spread = Ormuz premium."""
    brent_data = await fetch_yahoo_quote("BZ=F")
    wti_data = await fetch_yahoo_quote("CL=F")
    if "error" in brent_data or "error" in wti_data:
        return 0, {"signal": "O5_WAR_RISK", "error": "Could not fetch oil data"}
    brent = brent_data.get("current", 0)
    wti = wti_data.get("current", 0)
    spread = brent - wti
    score = 0
    if spread > 12: score = 10
    elif spread > 8: score = 7
    elif spread > 5: score = 3
    return score, {
        "signal": "O5_WAR_RISK", "brent": round(brent, 2), "wti": round(wti, 2),
        "spread": round(spread, 2),
        "interpretation": "Ormuz premium" if spread > 5 else "Normal",
        "score": score, "max_score": 10
    }
