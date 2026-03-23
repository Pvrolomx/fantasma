"""
FANTASMA / OBSERVATORIO - Senales Nuevas (Debate Multi-IA Round 1)
Origen: Debate 8 modelos (22 Mar 2026) — GLM-5, Gemini, DeepSeek, ChatGPT, Copilot, Mistral

G12_YEN_PRESSURE: Fortalecimiento del yen como predictor de carry trade unwind.
    Si el yen se fortalece (USD/JPY baja), los fondos que pidieron prestado yenes
    necesitan devolver mas caro -> venden pesos -> tipo de cambio sube.
    Fuente: FRED DEXJPUS (USD/JPY daily).
    Propuesto por: Gemini ("volatilidad implicita del yen es la senal mas rapida").

C7_CETES_EXTRANJEROS: Tasa de Cetes en subasta para no residentes.
    Si los extranjeros exigen tasas mas altas, es senal de que el apetito
    por deuda mexicana esta bajando. Si bajan sus tenencias mientras el
    peso sigue fuerte, alguien "fantasma" esta sosteniendo el tipo de cambio.
    Fuente: Banxico SIE SF43945 (semanal).
    Propuesto por: Gemini ("base de Cetes en manos de extranjeros").

G8_CARRY_REAL: Carry trade spread REAL (ajustado por inflacion).
    El spread nominal (MX 7% - JP 0.75% = 6.25%) es enganhoso si la
    inflacion de Mexico es alta. El spread real descuenta las expectativas
    de inflacion de ambos paises. Si el spread real cae debajo de 3%,
    el carry trade deja de ser rentable en terminos reales.
    Fuente: FRED T5YIFR (US inflation proxy) + Banxico TIIE.
    Propuesto por: GLM-5 ("spread real debajo de 3% = estampida").
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
BANXICO_TOKEN = os.getenv("BANXICO_TOKEN", "")


# ============================================================
# G12: YEN PRESSURE (Yen strengthening = carry unwind risk)
# ============================================================

async def get_g12_yen_pressure() -> Tuple[float, Dict]:
    """
    G12: Presion del Yen (5 pts max)

    Si USD/JPY baja (yen se fortalece), los carry traders que pidieron
    prestado en yenes tienen que vender sus posiciones en pesos.
    
    Mide: cambio porcentual semanal de USD/JPY.
    - Yen se fortalece >2% en una semana -> 5 pts (CRITICO)
    - Yen se fortalece >1% -> 3 pts (WARNING)
    - Yen se fortalece >0.5% -> 1 pt (ATENCION)
    - Yen estable o debilitandose -> 0 pts
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": "DEXJPUS",
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 10,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                obs = [o for o in data.get("observations", []) if o.get("value", ".") != "."]
                if len(obs) >= 2:
                    current = float(obs[0]["value"])
                    # Find value from ~5 trading days ago
                    prev_idx = min(4, len(obs) - 1)
                    previous = float(obs[prev_idx]["value"])
                    weekly_change_pct = ((current - previous) / previous) * 100
                    
                    # Negative change = yen strengthening (USD/JPY falling)
                    yen_strength = -weekly_change_pct  # positive = yen getting stronger
                    
                    score = 0
                    if yen_strength > 2.0:
                        score = 5
                    elif yen_strength > 1.0:
                        score = 3
                    elif yen_strength > 0.5:
                        score = 1

                    status = "CRITICO" if score >= 5 else "WARNING" if score >= 3 else "ATENCION" if score >= 1 else "NORMAL"

                    return score, {
                        "signal": "G12_YEN_PRESSURE",
                        "value": round(current, 2),
                        "usdjpy_current": round(current, 2),
                        "usdjpy_prev_week": round(previous, 2),
                        "weekly_change_pct": round(weekly_change_pct, 2),
                        "yen_strengthening_pct": round(yen_strength, 2),
                        "status": status,
                        "note": "Yen fuerte = carry traders venden pesos. Catalizador mas rapido de unwind.",
                        "score": score,
                        "max_score": 5,
                    }
    except Exception as e:
        return 0, {"signal": "G12_YEN_PRESSURE", "error": str(e), "score": 0, "max_score": 5}

    return 0, {"signal": "G12_YEN_PRESSURE", "value": None, "note": "Sin datos FRED", "score": 0, "max_score": 5}


# ============================================================
# C7: CETES EXTRANJEROS (Foreign appetite for MX debt)
# ============================================================

async def get_c7_cetes_extranjeros() -> Tuple[float, Dict]:
    """
    C7: Cetes Tasa Extranjeros (5 pts max)

    Monitorea la tasa que pagan los Cetes en subasta para no residentes.
    Si los extranjeros exigen tasas mas altas que los locales, estan
    demandando mas premio por el riesgo Mexico.

    Fuente: Banxico SF43945 (semanal) y SF60634 (local).
    
    Scoring:
    - Tasa NR > 8.5% -> 5 pts (riesgo alto, extranjeros exigen mucho)
    - Tasa NR > 8.0% -> 3 pts
    - Tasa NR > 7.5% -> 1 pt
    - Tasa NR <= 7.5% -> 0 pts (apetito saludable)
    """
    nr_rate = None
    local_rate = None

    try:
        async with httpx.AsyncClient() as client:
            # SF43945 = Tasa Cetes no residentes (semanal)
            resp_nr = await client.get(
                "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF43945/datos/oportuno",
                headers={"Bmx-Token": BANXICO_TOKEN},
                timeout=15,
            )
            if resp_nr.status_code == 200:
                d = resp_nr.json()
                datos = d.get("bmx", {}).get("series", [{}])[0].get("datos", [])
                if datos:
                    val = datos[-1].get("dato", "").replace(",", "")
                    if val and val != "N/E":
                        nr_rate = float(val)

            # SF60634 = Tasa Cetes local (semanal)
            resp_loc = await client.get(
                "https://www.banxico.org.mx/SieAPIRest/service/v1/series/SF60634/datos/oportuno",
                headers={"Bmx-Token": BANXICO_TOKEN},
                timeout=15,
            )
            if resp_loc.status_code == 200:
                d = resp_loc.json()
                datos = d.get("bmx", {}).get("series", [{}])[0].get("datos", [])
                if datos:
                    val = datos[-1].get("dato", "").replace(",", "")
                    if val and val != "N/E":
                        local_rate = float(val)
    except Exception as e:
        return 0, {"signal": "C7_CETES_NR", "error": str(e), "score": 0, "max_score": 5}

    if nr_rate is None:
        return 0, {"signal": "C7_CETES_NR", "value": None, "note": "Sin datos Banxico", "score": 0, "max_score": 5}

    spread = round(nr_rate - local_rate, 2) if local_rate else None

    score = 0
    if nr_rate > 8.5:
        score = 5
    elif nr_rate > 8.0:
        score = 3
    elif nr_rate > 7.5:
        score = 1

    return score, {
        "signal": "C7_CETES_NR",
        "value": round(nr_rate, 2),
        "nr_rate": round(nr_rate, 2),
        "local_rate": round(local_rate, 2) if local_rate else None,
        "nr_local_spread": spread,
        "note": "Tasa que exigen extranjeros por Cetes. Mas alta = menos apetito por deuda MX.",
        "score": score,
        "max_score": 5,
    }


# ============================================================
# G8_CARRY_REAL: Carry Trade Spread REAL (inflation-adjusted)
# ============================================================

async def get_carry_trade_real(mx_rate: float = None) -> Tuple[float, Dict]:
    """
    Carry Trade Real Spread (supplemental to G8)

    Calcula el spread real del carry trade descontando inflacion.
    - Spread nominal: MX rate - JP rate
    - Spread real: (MX rate - MX inflation) - (JP rate - JP inflation)
    
    Simplificacion: usamos US inflation (FRED T5YIFR) como proxy de
    inflacion global, y asumimos JP inflation ~2% (target del BoJ).
    MX inflation se aproxima con UDIS o encuesta de expectativas.
    
    No genera score propio — enriquece el G8 existente.
    """
    us_inflation = None
    jp_rate = 0.75  # BoJ fallback

    try:
        async with httpx.AsyncClient() as client:
            # US 5Y Inflation Expectations
            resp = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": "T5YIFR",
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 1,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                obs = resp.json().get("observations", [])
                if obs and obs[0].get("value", ".") != ".":
                    us_inflation = float(obs[0]["value"])
    except Exception:
        pass

    if us_inflation is None:
        us_inflation = 2.5  # fallback

    # Mexico inflation proxy: use 4.0% as standing estimate
    # (Encuesta Banxico marzo 2026 dice ~3.8-4.2%)
    mx_inflation = 4.0
    jp_inflation = 2.0  # BoJ target

    mx = mx_rate if mx_rate else 7.0
    real_mx = mx - mx_inflation
    real_jp = jp_rate - jp_inflation
    real_spread = round(real_mx - real_jp, 2)

    return {
        "real_spread_pct": real_spread,
        "nominal_mx": round(mx, 2),
        "nominal_jp": round(jp_rate, 2),
        "mx_inflation_est": mx_inflation,
        "jp_inflation_est": jp_inflation,
        "us_inflation_5y": round(us_inflation, 2),
        "interpretation": "PELIGRO" if real_spread < 3.0 else "ATRACTIVO" if real_spread >= 4.0 else "PRECAUCION",
    }
