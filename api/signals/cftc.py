"""
FANTASMA - Senales CFTC
C3: Posiciones Especulativas MXN
Fuente: CFTC COT (Commitment of Traders) via API estructurada Socrata (JSON).
Reemplaza (05-ago-2026) el scraping de financial_lf.htm: aquel regex agarraba
'500,000' (tamano de contrato) menos '095741' (codigo CFTC) = 404,259 CONGELADO.
"""
import httpx
from datetime import datetime
from typing import Dict, Tuple

# API publica de la CFTC (Socrata). Dataset: Legacy Futures-Only.
COT_API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
MXN_CODE = "095741"  # Mexican Peso - Chicago Mercantile Exchange


async def fetch_cftc_mxn() -> Dict:
    """Posiciones no comerciales (especulativas) de MXN: ultima semana + previa."""
    params = {
        "cftc_contract_market_code": MXN_CODE,
        "$select": "report_date_as_yyyy_mm_dd,noncomm_positions_long_all,noncomm_positions_short_all,open_interest_all",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": "2",
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(COT_API, params=params, timeout=30)
            rows = resp.json()
            if not rows:
                return {"error": "CFTC: sin filas para MXN (095741)"}

            def net_of(row):
                return int(row["noncomm_positions_long_all"]) - int(row["noncomm_positions_short_all"])

            cur = rows[0]
            long_now = int(cur["noncomm_positions_long_all"])
            short_now = int(cur["noncomm_positions_short_all"])
            net_now = long_now - short_now
            net_prev = net_of(rows[1]) if len(rows) > 1 else net_now
            return {
                "long": long_now,
                "short": short_now,
                "net": net_now,
                "net_prev": net_prev,
                "weekly_change": net_now - net_prev,
                "report_date": cur["report_date_as_yyyy_mm_dd"][:10],
                "open_interest": int(cur.get("open_interest_all", 0)),
                # Cada contrato = 500,000 MXN; net_billions en miles de millones de MXN.
                "net_billions": net_now * 500000 / 1e9,
            }
        except Exception as e:
            print(f"Error fetching CFTC: {e}")
            return {"error": str(e)}


async def get_c3_cftc() -> Tuple[float, Dict]:
    """
    C3: Posiciones CFTC MXN (15 pts max). Net SHORT = presion sobre el peso.
    - net_billions < -5  -> 10 pts ; < -8 -> 15 pts
    - Giro semanal fuerte hacia short (>4,000 contratos, ~$2B MXN) -> +5
      (este es el confirmador del unwind de carry: especuladores VENDIENDO peso)
    net LARGO (positivo) = especuladores apostando AL peso = 0 pts.
    """
    data = await fetch_cftc_mxn()

    if "error" in data:
        return 0, {"signal": "C3_CFTC", "error": data["error"]}

    net_billions = data.get("net_billions", 0)
    weekly_change = data.get("weekly_change", 0)

    score = 0
    if net_billions < -8:
        score = 15
    elif net_billions < -5:
        score = 10
    if weekly_change < -4000:  # giro semanal hacia short
        score += 5
    score = min(score, 15)

    return score, {
        "signal": "C3_CFTC",
        "net_contracts": data.get("net", 0),
        "net_prev_contracts": data.get("net_prev", 0),
        "weekly_change": weekly_change,
        "net_billions_usd": round(net_billions, 2),
        "long_contracts": data.get("long", 0),
        "short_contracts": data.get("short", 0),
        "report_date": data.get("report_date"),
        "open_interest": data.get("open_interest", 0),
        "score": score,
        "max_score": 15,
    }


# Alternativa: usar datos ya parseados de Quandl/Nasdaq Data Link
async def fetch_cftc_quandl(api_key: str = None) -> Dict:
    """
    Alternativa usando Nasdaq Data Link (antes Quandl)
    Dataset: CFTC/098662_FO_L_ALL - Mexican Peso
    """
    if not api_key:
        return {"error": "No API key"}

    url = f"https://data.nasdaq.com/api/v3/datasets/CFTC/098662_FO_L_ALL.json?api_key={api_key}&rows=5"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30)
            data = response.json()
            dataset = data.get("dataset", {})
            latest = dataset.get("data", [[]])[0]

            if latest:
                return {
                    "date": latest[0],
                    "open_interest": latest[1],
                    "long_spec": latest[2],
                    "short_spec": latest[3],
                    "net": latest[2] - latest[3]
                }
            return {"error": "No data"}
        except Exception as e:
            return {"error": str(e)}
