"""
FANTASMA - Signal G14: YEN/MXN Correlation Velocity
Mide la correlacion rolling entre USDJPY y USDMXN en ventanas cortas.
Un cambio brusco hacia -1 indica unwind activo del carry trade yen/peso.
Agregado: 2026-05-15 por CD73
"""
import httpx
from typing import Tuple, Dict


async def fetch_yahoo_closes(symbol: str) -> list:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "30d"}
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(url, params=params, headers=headers, timeout=30)
            data = r.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            return [c for c in closes if c is not None]
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return []


def pearson_corr(x: list, y: list) -> float:
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    x, y = x[-n:], y[-n:]
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    denom = (sum((xi - mx) ** 2 for xi in x) * sum((yi - my) ** 2 for yi in y)) ** 0.5
    return round(num / denom, 3) if denom != 0 else 0.0


async def get_g14_yen_mxn_velocity() -> Tuple[float, Dict]:
    """
    G14: YEN/MXN Correlation Velocity (8 pts max)
    Scoring:
    - corr_5d < -0.7 Y velocidad_24h > 0.3  -> 8 pts (unwind activo con aceleracion)
    - corr_5d < -0.7                          -> 6 pts (correlacion extrema)
    - corr_5d < -0.5                          -> 4 pts (presion creciente)
    - velocidad_24h > 0.3                     -> 3 pts (aceleracion brusca)
    - Normal                                  -> 0 pts
    """
    usdjpy = await fetch_yahoo_closes("JPY=X")
    usdmxn = await fetch_yahoo_closes("MXN=X")

    if len(usdjpy) < 6 or len(usdmxn) < 6:
        return 0, {
            "signal": "G14_YEN_MXN_VELOCITY",
            "error": "Datos insuficientes para calcular correlacion",
            "score": 0,
            "max_score": 0,
        }

    corr_5d = pearson_corr(usdjpy[-5:], usdmxn[-5:])
    corr_20d = pearson_corr(usdjpy[-20:], usdmxn[-20:])
    corr_5d_ayer = pearson_corr(usdjpy[-6:-1], usdmxn[-6:-1])
    velocidad_24h = round(abs(corr_5d - corr_5d_ayer), 3)
    divergencia = round(corr_5d - corr_20d, 3)

    # DEGRADADO A INFORMATIVO (01-ago-2026, CD03).
    # Mini-test (tests/g14_minitest.py) probo con 74 dias que G14 es ruido:
    # no predice el peso (max|r|=0.097), no anticipa al yen (r~0.02-0.05),
    # y su tesis interna tiene el signo invertido. Ya NO suma al score.
    # Se conservan los datos y un status descriptivo, solo como contexto.
    score = 0
    if corr_5d < -0.5 or velocidad_24h > 0.3:
        status = "INFORMATIVO - movimiento en correlacion (no suma al score; ver g14_minitest)"
    else:
        status = "INFORMATIVO - normal"

    return score, {
        "signal": "G14_YEN_MXN_VELOCITY",
        "corr_5d": corr_5d,
        "corr_20d": corr_20d,
        "divergencia_5d_20d": divergencia,
        "velocidad_24h": velocidad_24h,
        "status": status,
        "note": (
            "Correlacion Pearson USDJPY/USDMXN. "
            "Hacia -1 = carry trade unwind activo. "
            "Velocidad = cambio de correlacion en 24h. "
            "82% transacciones MXN ocurren fuera de Mexico (BIS)."
        ),
        "score": score,
        "max_score": 0,
    }
