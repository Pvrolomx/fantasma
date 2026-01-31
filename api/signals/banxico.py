"""
FANTASMA - Señales Banxico
C1: Tipo de Cambio FIX (SF43718)
C2: TIIE 28 días (SF60648)
C4: Reservas Internacionales (SF110168)
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Tuple

BANXICO_TOKEN = "your_banxico_token"  # Se configura en env
BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"

async def fetch_series(series_id: str, days: int = 30) -> list:
    """Obtiene datos de una serie de Banxico."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    url = f"{BASE_URL}/{series_id}/datos/{start_date}/{end_date}"
    headers = {"Bmx-Token": BANXICO_TOKEN}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30)
            data = response.json()
            return data.get("bmx", {}).get("series", [{}])[0].get("datos", [])
        except Exception as e:
            print(f"Error fetching {series_id}: {e}")
            return []

def calculate_daily_change(data: list) -> float:
    """Calcula cambio porcentual diario."""
    if len(data) < 2:
        return 0.0
    try:
        current = float(data[-1]["dato"].replace(",", ""))
        previous = float(data[-2]["dato"].replace(",", ""))
        return ((current - previous) / previous) * 100
    except (ValueError, KeyError):
        return 0.0

def calculate_trend(data: list, days: int = 5) -> bool:
    """Detecta tendencia alcista sostenida."""
    if len(data) < days:
        return False
    try:
        values = [float(d["dato"].replace(",", "")) for d in data[-days:]]
        return all(values[i] < values[i+1] for i in range(len(values)-1))
    except (ValueError, KeyError):
        return False

async def get_c1_fix() -> Tuple[float, Dict]:
    """
    C1: Tipo de Cambio FIX (20 pts max)
    - Cambio diario >1.5% → 10 pts
    - Cambio diario >2.5% → 15 pts
    - Cambio diario >4% → 20 pts
    - Tendencia 5 días alcista → +5 pts
    """
    data = await fetch_series("SF43718", days=10)
    
    daily_change = calculate_daily_change(data)
    trend_up = calculate_trend(data, 5)
    
    score = 0
    if abs(daily_change) > 4:
        score = 20
    elif abs(daily_change) > 2.5:
        score = 15
    elif abs(daily_change) > 1.5:
        score = 10
    
    if trend_up:
        score = min(score + 5, 20)
    
    current_rate = float(data[-1]["dato"].replace(",", "")) if data else 0
    
    return score, {
        "signal": "C1_FIX",
        "value": current_rate,
        "daily_change_pct": round(daily_change, 2),
        "trend_5d_up": trend_up,
        "score": score,
        "max_score": 20
    }

async def get_c2_tiie(fed_funds_rate: float = 5.25) -> Tuple[float, Dict]:
    """
    C2: TIIE 28 días (10 pts max)
    - Spread vs Fed Funds >600 bps → 5 pts
    - Cambio semanal >25 bps → 5 pts
    """
    data = await fetch_series("SF60648", days=10)
    
    if not data:
        return 0, {"signal": "C2_TIIE", "error": "No data"}
    
    current_tiie = float(data[-1]["dato"].replace(",", ""))
    spread_bps = (current_tiie - fed_funds_rate) * 100
    
    # Cambio semanal
    weekly_change = 0
    if len(data) >= 5:
        week_ago = float(data[-5]["dato"].replace(",", ""))
        weekly_change = (current_tiie - week_ago) * 100  # en bps
    
    score = 0
    if spread_bps > 600:
        score += 5
    if abs(weekly_change) > 25:
        score += 5
    
    return score, {
        "signal": "C2_TIIE",
        "value": current_tiie,
        "spread_vs_fed_bps": round(spread_bps, 0),
        "weekly_change_bps": round(weekly_change, 0),
        "score": score,
        "max_score": 10
    }

async def get_c4_reservas() -> Tuple[float, Dict]:
    """
    C4: Reservas Internacionales (10 pts max)
    - Caída >$5B en mes → 5 pts
    - Caída >$10B en mes → 10 pts
    - Reservas <$150B → 5 pts (alerta estructural)
    """
    data = await fetch_series("SF110168", days=35)
    
    if not data:
        return 0, {"signal": "C4_RESERVAS", "error": "No data"}
    
    current = float(data[-1]["dato"].replace(",", ""))
    
    # Cambio mensual
    monthly_change = 0
    if len(data) >= 20:
        month_ago = float(data[-20]["dato"].replace(",", ""))
        monthly_change = current - month_ago
    
    score = 0
    if monthly_change < -10:
        score = 10
    elif monthly_change < -5:
        score = 5
    
    if current < 150:
        score = min(score + 5, 10)
    
    return score, {
        "signal": "C4_RESERVAS",
        "value_billions": round(current, 2),
        "monthly_change_billions": round(monthly_change, 2),
        "score": score,
        "max_score": 10
    }
