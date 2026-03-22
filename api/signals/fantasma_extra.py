"""
FANTASMA / OBSERVATORIO - Senales Adicionales del FANTASMA Original
Migradas del monitoreo semanal de Copilot al Observatorio en tiempo real.

G9_SWAP_LINES:  Fed swap lines - senhal nuclear de estres global
G10_INTERBANK:  FRA-OIS proxy - confianza interbancaria
G11_DRAGON:     USD/CNY - pulso de China (proxy de TSF)
C6_CONTRARIAN:  Encuesta expectativas Banxico vs realidad

Fuentes: FRED (SWPT, OBFR, SOFR), Yahoo Finance (CNY=X), Banxico SIE
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


async def _fetch_fred(series_id: str, limit: int = 5) -> list:
    """Helper para obtener datos de FRED."""
    if not FRED_API_KEY:
        return []
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_id,
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return [o for o in data.get("observations", []) if o.get("value", ".") != "."]
    except Exception as e:
        print(f"FRED error ({series_id}): {e}")
    return []


async def _fetch_yahoo(symbol: str) -> dict:
    """Helper para obtener cotizacion de Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"interval": "1d", "range": "1mo"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=30)
            data = resp.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})
            return {"current": meta.get("regularMarketPrice", 0)}
    except Exception as e:
        print(f"Yahoo error ({symbol}): {e}")
        return {"error": str(e)}


# ============================================================
# G9: SWAP LINES — Senhal nuclear de estres global
# Serie FRED: SWPT (semanal)
# Cuando la Fed activa swap lines, el sistema esta en emergencia.
# En tiempos normales: $0-100M. En crisis: $500M+. En 2008: $583B.
# ============================================================
async def get_g9_swap_lines() -> Tuple[float, Dict]:
    """G9: Fed Swap Lines (5 pts max). Senhal de emergencia global."""
    data = await _fetch_fred("SWPT", limit=5)
    if not data:
        return 0, {"signal": "G9_SWAP_LINES", "error": "No data"}

    current = float(data[0]["value"])
    prev = float(data[1]["value"]) if len(data) > 1 else current

    score = 0
    if current > 10000:    # >$10B = crisis severa
        score = 5
    elif current > 1000:   # >$1B = estres significativo
        score = 3
    elif current > 500:    # >$500M = alerta temprana
        score = 1

    status = "EMERGENCIA" if current > 1000 else "ELEVADO" if current > 100 else "NORMAL"

    return score, {
        "signal": "G9_SWAP_LINES",
        "value_millions": round(current, 0),
        "prev_week_millions": round(prev, 0),
        "weekly_change": round(current - prev, 0),
        "status": status,
        "note": "Si sube de $1B, el sistema financiero esta en emergencia.",
        "score": score,
        "max_score": 5
    }


# ============================================================
# G10: INTERBANK TRUST — Confianza interbancaria
# Proxy: SOFR vs OBFR spread. Si divergen, bancos no confian entre si.
# El FRA-OIS real no esta en FRED, pero SOFR-OBFR es un proxy valido.
# En tiempos normales: spread < 5bps. En estres: > 10bps. Pre-crisis: > 20bps.
# ============================================================
async def get_g10_interbank() -> Tuple[float, Dict]:
    """G10: Interbank Trust proxy (5 pts max). SOFR vs OBFR spread."""
    sofr_data = await _fetch_fred("SOFR", limit=3)
    obfr_data = await _fetch_fred("OBFR", limit=3)

    if not sofr_data or not obfr_data:
        return 0, {"signal": "G10_INTERBANK", "error": "No data"}

    sofr = float(sofr_data[0]["value"])
    obfr = float(obfr_data[0]["value"])
    spread_bps = abs(sofr - obfr) * 100

    score = 0
    if spread_bps > 20:
        score = 5
    elif spread_bps > 10:
        score = 3
    elif spread_bps > 5:
        score = 1

    status = "CRISIS" if spread_bps > 20 else "ESTRES" if spread_bps > 10 else "NORMAL"

    return score, {
        "signal": "G10_INTERBANK",
        "sofr": round(sofr, 4),
        "obfr": round(obfr, 4),
        "spread_bps": round(spread_bps, 1),
        "status": status,
        "note": "Si spread > 10bps, bancos no confian entre si para prestarse.",
        "score": score,
        "max_score": 5
    }


# ============================================================
# G11: DRAGON PULSE — Pulso de China via USD/CNY
# TSF real no disponible en FRED (discontinuado 2018).
# Proxy: USD/CNY (yuan offshore). Si el yuan se debilita (sube),
# China esta bajo presion y el efecto llega a emergentes.
# Normal: 7.0-7.2. Debil: >7.3. Crisis: >7.5.
# Si baja de 6.8 = yuan fuerte, China inyecta liquidez.
# ============================================================
async def get_g11_dragon() -> Tuple[float, Dict]:
    """G11: Dragon Pulse - China stress via USD/CNY (5 pts max)."""
    data = await _fetch_yahoo("CNY=X")
    if "error" in data:
        return 0, {"signal": "G11_DRAGON", "error": data["error"]}

    usdcny = data.get("current", 0)
    if usdcny == 0:
        return 0, {"signal": "G11_DRAGON", "error": "No price data"}

    score = 0
    if usdcny > 7.5:
        score = 5
    elif usdcny > 7.3:
        score = 3
    elif usdcny > 7.1:
        score = 1

    status = "CRISIS" if usdcny > 7.5 else "DEBIL" if usdcny > 7.2 else "NORMAL" if usdcny > 6.9 else "FUERTE"

    return score, {
        "signal": "G11_DRAGON",
        "usdcny": round(usdcny, 4),
        "status": status,
        "note": "Yuan debil (>7.2) = China bajo presion, impacto en emergentes y commodities.",
        "score": score,
        "max_score": 5
    }


# ============================================================
# C6: CONTRARIAN — Lo que los expertos dicen vs lo que pasa
# Basado en la Encuesta de Expectativas de Banxico (mensual).
# Si los analistas predicen depreciacion y el peso se aprecia,
# alguien con informacion privilegiada se posiciono antes.
# Logica inversa: si todos dicen X, preparate para no-X.
#
# Como la encuesta de Banxico no tiene API directa, usamos el
# approach hibrido: comparar el USDMXN actual contra el consenso
# conocido. El consenso se actualiza manualmente cada mes.
#
# Consenso actual (Mar 2026): Analistas promedian 19.50 para fin de 2026
# (Fuente: Encuesta Banxico Feb 2026)
# ============================================================

# Actualizar mensualmente con dato de la Encuesta de Expectativas Banxico
CONSENSUS_USDMXN_EOY = 19.50     # Mediana analistas para dic 2026
CONSENSUS_DATE = "2026-02"         # Fecha de la encuesta

async def get_c6_contrarian(current_usdmxn: float = None) -> Tuple[float, Dict]:
    """
    C6: Indicador Contrarian (5 pts max).
    Compara el consenso de analistas con la realidad del mercado.
    Si los expertos dicen que el peso se va a depreciar pero se aprecia,
    marca alerta — alguien con info privilegiada esta posicionado al reves.
    """
    if current_usdmxn is None or current_usdmxn == 0:
        # Fetch USDMXN from Yahoo if not provided
        yahoo_data = await _fetch_yahoo("MXN=X")
        current_usdmxn = yahoo_data.get("current", 0)
        if current_usdmxn == 0:
            return 0, {"signal": "C6_CONTRARIAN", "error": "No USDMXN data"}

    # Distancia entre consenso y realidad (en %)
    deviation = ((CONSENSUS_USDMXN_EOY - current_usdmxn) / current_usdmxn) * 100

    # Si los analistas esperan 19.50 y el peso esta en 17.9,
    # la desviacion es +8.9% — los "expertos" esperan depreciacion
    # pero el mercado dice lo contrario.

    score = 0
    direction = ""

    if deviation > 8:
        # Consenso espera depreciacion fuerte pero peso esta fuerte
        # Contrarian dice: cuidado, el golpe puede venir de donde NO esperan
        score = 5
        direction = "DIVERGENCIA EXTREMA - Expertos predicen depreciacion pero peso fuerte. Preparate para lo inesperado."
    elif deviation > 5:
        score = 3
        direction = "DIVERGENCIA ALTA - Consenso y realidad no coinciden. Los expertos se equivocaron en 2025 tambien."
    elif deviation > 2:
        score = 1
        direction = "DIVERGENCIA MODERADA - Algo de distancia entre consenso y mercado."
    elif deviation < -5:
        # Consenso esperaba peso fuerte pero se deprecia — raro pero posible
        score = 4
        direction = "CONSENSO REBASADO - El peso se deprecio mas de lo esperado. Crisis en curso."
    else:
        direction = "ALINEADO - Consenso y mercado estan cerca. Sin senal contrarian."

    return score, {
        "signal": "C6_CONTRARIAN",
        "current_usdmxn": round(current_usdmxn, 4),
        "consensus_eoy": CONSENSUS_USDMXN_EOY,
        "consensus_date": CONSENSUS_DATE,
        "deviation_pct": round(deviation, 1),
        "direction": direction,
        "note": "Si los expertos con info privilegiada dicen X, preparate para no-X.",
        "score": score,
        "max_score": 5
    }
