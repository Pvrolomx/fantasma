"""
FANTASMA - Senales Banxico
C1: Tipo de Cambio FIX (SF43718)
C2: TIIE 28 dias (SF60648)
C4: Reservas Internacionales (SF43707 semanal)
"""
import httpx
import os
from datetime import datetime, timedelta
from typing import Dict, Tuple

BANXICO_TOKEN = os.getenv("BANXICO_TOKEN", "")
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
    """C1: Tipo de Cambio FIX (20 pts max)"""
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
    """C2: TIIE 28 dias (10 pts max)"""
    data = await fetch_series("SF60648", days=10)

    if not data:
        return 0, {"signal": "C2_TIIE", "error": "No data"}

    current_tiie = float(data[-1]["dato"].replace(",", ""))
    spread_bps = (current_tiie - fed_funds_rate) * 100

    weekly_change = 0
    if len(data) >= 5:
        week_ago = float(data[-5]["dato"].replace(",", ""))
        weekly_change = (current_tiie - week_ago) * 100

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
    C4: Reservas Internacionales (15 pts max) - SERIE SEMANAL SF43707
    La serie SF110168 es mensual y tiene retraso. SF43707 es semanal y mas fresca.

    Scoring:
    - Caida >$5B en 4 semanas -> 5 pts
    - Caida >$10B en 4 semanas -> 10 pts
    - Caida >$5B en 1 semana -> 10 pts (caida abrupta = intervencion masiva)
    - Reservas <$200B -> 5 pts (alerta estructural)
    - Tendencia 4 semanas consecutivas a la baja -> 3 pts

    Logica de crisis: Si Banxico quema reservas para sostener el peso,
    las reservas caen ANTES de que el peso se devalue. Es predictor,
    no indicador rezagado.
    """
    # Pedir 120 dias para tener ~16 datos semanales
    data = await fetch_series("SF43707", days=120)

    if not data or len(data) < 2:
        return 0, {"signal": "C4_RESERVAS", "error": "No data"}

    try:
        current = float(data[-1]["dato"].replace(",", ""))
        current_date = data[-1].get("fecha", "")

        # Cambio vs semana pasada
        prev_week = float(data[-2]["dato"].replace(",", ""))
        weekly_change = current - prev_week

        # Cambio vs 4 semanas atras
        monthly_change = 0
        if len(data) >= 5:
            four_weeks_ago = float(data[-5]["dato"].replace(",", ""))
            monthly_change = current - four_weeks_ago

        # Tendencia: 4 semanas consecutivas a la baja
        trend_down = False
        if len(data) >= 5:
            last_4 = [float(d["dato"].replace(",", "")) for d in data[-5:]]
            trend_down = all(last_4[i] > last_4[i+1] for i in range(len(last_4)-1))

        score = 0

        # Caida abrupta en 1 semana (intervencion masiva)
        if weekly_change < -5000:
            score = 10
        # Caida en 4 semanas
        if monthly_change < -10000:
            score = max(score, 10)
        elif monthly_change < -5000:
            score = max(score, 5)

        # Alerta estructural: reservas bajas
        if current < 200000:
            score = min(score + 5, 15)

        # Tendencia sostenida a la baja
        if trend_down:
            score = min(score + 3, 15)

        return score, {
            "signal": "C4_RESERVAS",
            "value_billions": round(current / 1000, 2),
            "value_millions": round(current, 2),
            "weekly_change_millions": round(weekly_change, 2),
            "monthly_change_millions": round(monthly_change, 2),
            "trend_4w_down": trend_down,
            "last_report_date": current_date,
            "score": score,
            "max_score": 15
        }

    except (ValueError, KeyError, IndexError) as e:
        return 0, {"signal": "C4_RESERVAS", "error": str(e)}
