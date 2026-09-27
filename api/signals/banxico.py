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

async def get_banxico_target_rate() -> float:
    """Tasa objetivo de Banxico (SF61745) = tasa de politica. Reemplaza el
    fallback hardcodeado 7.0 de G8, que congelaba el carry spread."""
    data = await fetch_series("SF61745", days=30)
    for d in reversed(data):
        v = (d.get("dato", "N/E") or "").replace(",", "").strip()
        if v not in ("N/E", ""):
            try:
                return float(v)
            except ValueError:
                pass
    return 6.5  # fallback si la API falla (tasa vigente ago-2026)


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

def calculate_cumulative(data: list, days: int) -> float:
    """Cambio % acumulado entre hace `days` observaciones y la ultima. 0.0 si no hay serie."""
    if len(data) < days + 1:
        return 0.0
    try:
        vals = [float(d["dato"].replace(",", "")) for d in data]
        a, b = vals[-(days + 1)], vals[-1]
        return ((b - a) / a) * 100 if a else 0.0
    except (ValueError, KeyError):
        return 0.0


async def get_c1_fix() -> Tuple[float, Dict]:
    """C1: Tipo de Cambio FIX (20 pts max).

    P14 (27-sep-2026): antes solo miraba el cambio DIARIO (>1.5% para el primer
    escalon) mas un bono por racha estrictamente creciente. Un deslizamiento como el
    de sep-2026 (+4.95% en 20 dias) marcaba CERO. Ahora puntua tambien por acumulado
    de 5 y 20 dias, y se toma el MAXIMO de los tres componentes -- no la suma -- para
    no contar el mismo movimiento dos veces.
    Umbrales calibrados sobre los 190 snapshots (20-mar a 27-sep-2026):
      5d  >1.5% = 9.2% de los dias | >2.5% = 3.2%
      20d >3.0% = 7.1% de los dias | >4.5% = ~3%
    """
    data = await fetch_series("SF43718", days=40)

    daily_change = calculate_daily_change(data)
    trend_up = calculate_trend(data, 5)
    change_5d = calculate_cumulative(data, 5)
    change_20d = calculate_cumulative(data, 20)

    # componente salto (lo que ya existia)
    s_daily = 0
    if abs(daily_change) > 4:
        s_daily = 20
    elif abs(daily_change) > 2.5:
        s_daily = 15
    elif abs(daily_change) > 1.5:
        s_daily = 10

    # componente deslizamiento (nuevo). DIRECCIONAL a proposito: solo cuenta cuando el
    # peso se DEPRECIA (FIX al alza). Simetrico prendia 9 dias de abr-2026 con el peso
    # FORTALECIENDOSE -- el mismo defecto de magnitud-sin-signo del G4_HY_SPREAD.
    # Backtest 190 snapshots: simetrico 28 dias encendidos vs direccional 14, y estos
    # 14 son todos depreciacion real. El salto diario SI queda simetrico (un brinco
    # de >1.5% en un dia es shock en cualquier direccion).
    s_5d = 10 if change_5d > 2.5 else (5 if change_5d > 1.5 else 0)
    s_20d = 10 if change_20d > 4.5 else (5 if change_20d > 3.0 else 0)

    score = max(s_daily, s_5d, s_20d)
    if trend_up:
        score = min(score + 5, 20)

    current_rate = float(data[-1]["dato"].replace(",", "")) if data else 0

    return score, {
        "signal": "C1_FIX",
        "value": current_rate,
        "daily_change_pct": round(daily_change, 2),
        "change_5d_pct": round(change_5d, 2),
        "change_20d_pct": round(change_20d, 2),
        "trend_5d_up": trend_up,
        "score_components": {"diario": s_daily, "5d": s_5d, "20d": s_20d},
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
