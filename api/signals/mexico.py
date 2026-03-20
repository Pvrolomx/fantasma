"""
FANTASMA / OBSERVATORIO - Modulo 3: Impacto Local (Mexico/PV)
M1: USD/MXN stress (15 pts max)
M2: Precio del Maiz internacional (10 pts max) - Crisis alimentaria
M3: Precio Urea/Fertilizantes (5 pts max) - Escasez agricola
"""
from typing import Dict, Tuple
from .yahoo import fetch_yahoo_quote


async def get_m1_usdmxn() -> Tuple[float, Dict]:
    """M1: USD/MXN (15 pts max). Tu poder de compra."""
    data = await fetch_yahoo_quote("MXN=X")
    if "error" in data:
        return 0, {"signal": "M1_USDMXN", "error": data["error"]}
    current = data.get("current", 0)
    closes = data.get("closes", [])
    weekly_change_pct = 0
    if len(closes) >= 5 and closes[-5] > 0:
        weekly_change_pct = ((current - closes[-5]) / closes[-5]) * 100
    score = 0
    if current > 23: score = 15
    elif current > 22: score = 12
    elif current > 21: score = 8
    elif current > 20.5: score = 5
    if abs(weekly_change_pct) > 3: score = min(score + 3, 15)
    return score, {
        "signal": "M1_USDMXN", "value": round(current, 4),
        "weekly_change_pct": round(weekly_change_pct, 2),
        "alert_threshold": 21.0,
        "score": score, "max_score": 15
    }


async def get_m2_corn() -> Tuple[float, Dict]:
    """M2: Precio del Maiz (10 pts max). Proxy crisis alimentaria."""
    data = await fetch_yahoo_quote("ZC=F")
    if "error" in data:
        return 0, {"signal": "M2_CORN", "error": data["error"]}
    current = data.get("current", 0)
    closes = data.get("closes", [])
    monthly_change_pct = 0
    if len(closes) >= 20 and closes[0] > 0:
        monthly_change_pct = ((current - closes[0]) / closes[0]) * 100
    score = 0
    if monthly_change_pct > 20: score = 10
    elif monthly_change_pct > 10: score = 7
    elif monthly_change_pct > 5: score = 3
    return score, {
        "signal": "M2_CORN", "value": round(current, 2),
        "monthly_change_pct": round(monthly_change_pct, 2),
        "score": score, "max_score": 10
    }


async def get_m3_urea() -> Tuple[float, Dict]:
    """M3: Fertilizantes/Urea proxy (5 pts max). Escasez agricola."""
    data = await fetch_yahoo_quote("UAN=F")
    if "error" in data:
        data = await fetch_yahoo_quote("NG=F")
        if "error" in data:
            return 0, {"signal": "M3_UREA", "error": "No proxy available"}
    current = data.get("current", 0)
    closes = data.get("closes", [])
    monthly_change_pct = 0
    if len(closes) >= 20 and closes[0] > 0:
        monthly_change_pct = ((current - closes[0]) / closes[0]) * 100
    score = 0
    if monthly_change_pct > 15: score = 5
    elif monthly_change_pct > 8: score = 3
    return score, {
        "signal": "M3_UREA", "value": round(current, 2),
        "monthly_change_pct": round(monthly_change_pct, 2),
        "note": "Using natural gas as fertilizer proxy",
        "score": score, "max_score": 5
    }
