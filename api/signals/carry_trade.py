"""
FANTASMA / OBSERVATORIO - Senal G8: Carry Trade Spread (Japon-Mexico)
Mide el diferencial de tasas entre Mexico y Japon.
Cuando el spread se comprime, el carry trade se deshace y el peso cae.

La tasa de Japon viene de FRED (IRSTCI01JPM156N - mensual).
La tasa de Mexico viene de Banxico (TIIE ya recopilada en C2).
Como fallback, se usa el valor conocido del BoJ (0.75% desde dic 2025).

Este es el predictor mas directo de cuando el peso pierde su soporte
artificial. Si el BoJ sube a 1%+ y Banxico baja a 6%, el spread pasa
de 6.25% a 5% y los fondos empiezan a salir de Mexico.
"""
import os
import httpx
from typing import Dict, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# BoJ rate fallback — actualizar manualmente si FRED falla
# Ultimo conocido: 0.75% desde diciembre 2025 (reunion marzo 2026 mantuvo)
BOJ_RATE_FALLBACK = 0.75

# Umbrales de alerta para el spread
# El carry trade tipicamente se deshace cuando el spread baja de 5%
SPREAD_CRITICAL = 4.0   # Debajo de esto, fuga masiva
SPREAD_WARNING = 5.0    # Debajo de esto, empiezan a salir
SPREAD_NORMAL = 6.0     # Arriba de esto, carry trade atractivo


async def get_boj_rate() -> float:
    """Obtiene la tasa del BoJ de FRED. Fallback al valor conocido."""
    if not FRED_API_KEY:
        return BOJ_RATE_FALLBACK

    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "IRSTCI01JPM156N",
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 3,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                obs = data.get("observations", [])
                for o in obs:
                    val = o.get("value", ".")
                    if val != ".":
                        return float(val)
    except Exception as e:
        print(f"carry_trade: FRED error: {e}")

    return BOJ_RATE_FALLBACK


async def get_g8_carry_trade(banxico_rate: float = None) -> Tuple[float, Dict]:
    """
    G8: Carry Trade Spread Japon-Mexico (8 pts max)

    El carry trade es el mecanismo principal que mantiene el peso fuerte:
    - Inversores piden prestado yenes al 0.75%
    - Compran bonos mexicanos al 7%
    - Se embolsan la diferencia (6.25%)
    - Esa demanda de pesos mantiene el tipo de cambio bajo

    82% de las transacciones en pesos ocurren FUERA de Mexico (BIS).
    Cuando el spread se comprime, los fondos venden pesos y el TC se corrige.

    Scoring:
    - Spread < 4.0% -> 8 pts (CRITICO: carry trade muerto)
    - Spread < 5.0% -> 6 pts (WARNING: fondos empiezan a salir)
    - Spread < 5.5% -> 4 pts (ATENCION: compresion significativa)
    - Spread < 6.0% -> 2 pts (PRECAUCION: tendencia de compresion)
    - Spread >= 6.0% -> 0 pts (carry trade saludable)

    Bonus: Si el spread se comprimio >50bps en el ultimo dato vs anterior,
    +2 pts (movimiento rapido = riesgo de unwind abrupto)
    """
    boj_rate = await get_boj_rate()

    # Si no nos pasan la tasa de Banxico, usar 7.0% como fallback
    mx_rate = banxico_rate if banxico_rate is not None else 7.0

    spread = mx_rate - boj_rate
    spread_bps = round(spread * 100)

    score = 0
    if spread < 4.0:
        score = 8
    elif spread < 5.0:
        score = 6
    elif spread < 5.5:
        score = 4
    elif spread < 6.0:
        score = 2

    # Determinar estado del carry trade
    if spread >= 6.0:
        status = "ATRACTIVO - Carry trade saludable"
    elif spread >= 5.0:
        status = "COMPRESION - Fondos evaluando salida"
    elif spread >= 4.0:
        status = "PELIGRO - Carry trade en riesgo"
    else:
        status = "CRITICO - Carry trade colapsando"

    return score, {
        "signal": "G8_CARRY_TRADE",
        "mexico_rate": round(mx_rate, 2),
        "japan_rate": round(boj_rate, 2),
        "spread_pct": round(spread, 2),
        "spread_bps": spread_bps,
        "status": status,
        "note": "82% de transacciones MXN ocurren fuera de Mexico (BIS). Spread es el soporte principal del peso.",
        "score": score,
        "max_score": 8
    }
