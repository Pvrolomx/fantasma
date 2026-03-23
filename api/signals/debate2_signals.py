"""
FANTASMA - Señales del Debate Multi-IA Round 2
G13: CFTC Leveraged Funds Momentum (Posiciones netas especuladores)
O6: Chicago Fed Supply Chain Stress Index

Pedido por: DeepSeek, GLM-5, ChatGPT (break point detector)
Agregado: 23 Marzo 2026 por CD02
"""
import httpx
import os
from datetime import datetime
from typing import Dict, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pwsrjmhmxqfxmcadhjtz.supabase.co").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
FRED_KEY = os.getenv("FRED_API_KEY", "").strip()

# ============================================================
# G13: CFTC LEVERAGED FUNDS MOMENTUM
# ============================================================
CFTC_FIN_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
MXN_CFTC_CODE = "095741"
MXN_CONTRACT_SIZE = 500_000


async def _fetch_cftc_leveraged() -> Dict:
    """Fetch CFTC Financial Futures report - MXN leveraged funds positions."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(CFTC_FIN_URL, timeout=30, follow_redirects=True)
            if resp.status_code != 200:
                return {"error": f"CFTC HTTP {resp.status_code}"}

            for line in resp.text.split('\n'):
                if MXN_CFTC_CODE in line:
                    cols = line.split(',')
                    if len(cols) < 15:
                        return {"error": "Unexpected CFTC format"}

                    report_date = cols[2].strip()
                    open_interest = int(cols[7].strip())
                    lev_long = int(cols[11].strip())
                    lev_short = int(cols[12].strip())
                    net_contracts = lev_long - lev_short
                    dealer_long = int(cols[8].strip())
                    dealer_short = int(cols[9].strip())

                    return {
                        "report_date": report_date,
                        "open_interest": open_interest,
                        "lev_long": lev_long,
                        "lev_short": lev_short,
                        "net_contracts": net_contracts,
                        "net_billions_mxn": round(net_contracts * MXN_CONTRACT_SIZE / 1e9, 2),
                        "dealer_long": dealer_long,
                        "dealer_short": dealer_short,
                        "dealer_net": dealer_long - dealer_short,
                        "long_pct": round(lev_long / open_interest * 100, 1) if open_interest else 0,
                    }

            return {"error": "MXN not found in CFTC report"}
        except Exception as e:
            return {"error": str(e)}


async def _get_prev_week_cftc() -> Dict:
    """Get previous week CFTC data from Supabase."""
    if not SUPABASE_KEY:
        return {}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/fantasma_obs_cftc_weekly",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                params={"select": "*", "order": "report_date.desc", "limit": "2"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if len(data) >= 1:
                    return data[0]
    except Exception:
        pass
    return {}


async def _save_cftc_snapshot(data: Dict):
    """Save current CFTC data to Supabase for next week comparison."""
    if not SUPABASE_KEY or "error" in data:
        return
    try:
        row = {
            "report_date": data["report_date"],
            "net_contracts": data["net_contracts"],
            "lev_long": data["lev_long"],
            "lev_short": data["lev_short"],
            "open_interest": data["open_interest"],
            "dealer_net": data["dealer_net"],
        }
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/fantasma_obs_cftc_weekly",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates",
                },
                params={"on_conflict": "report_date"},
                json=row, timeout=10,
            )
    except Exception:
        pass


async def get_g13_cftc_momentum() -> Tuple[float, Dict]:
    """
    G13: CFTC Leveraged Funds Momentum (5 pts max)
    Mide el CAMBIO en posiciones netas de especuladores.
    Si hedge funds estan en max long peso y empiezan a voltear,
    es la senal mas temprana de unwind del carry trade.
    """
    current = await _fetch_cftc_leveraged()

    if "error" in current:
        return 0, {"signal": "G13_CFTC_MOMENTUM", "error": current["error"], "score": 0, "max_score": 5}

    await _save_cftc_snapshot(current)
    prev = await _get_prev_week_cftc()

    weekly_change = 0
    if prev and "net_contracts" in prev:
        weekly_change = current["net_contracts"] - prev["net_contracts"]

    score = 0
    status = "NORMAL"

    if prev and current["net_contracts"] < 0 and prev.get("net_contracts", 0) > 0:
        score = 5
        status = "FLIP A SHORT - Especuladores abandonaron el peso"
    elif weekly_change < -15000:
        score = 4
        status = "SALIDA MASIVA"
    elif weekly_change < -10000:
        score = 3
        status = "SALIDA FUERTE"
    elif weekly_change < -5000:
        score = 2
        status = "REDUCCION"
    elif current.get("long_pct", 0) > 50:
        score = 1
        status = "CROWDED TRADE"

    return score, {
        "signal": "G13_CFTC_MOMENTUM",
        "net_contracts": current["net_contracts"],
        "lev_long": current["lev_long"],
        "lev_short": current["lev_short"],
        "weekly_change": weekly_change,
        "long_pct": current.get("long_pct", 0),
        "report_date": current.get("report_date", ""),
        "dealer_net": current.get("dealer_net", 0),
        "status": status,
        "note": "Posiciones netas hedge funds en futuros MXN. Cambio negativo = vendiendo pesos.",
        "score": score,
        "max_score": 5,
    }


# ============================================================
# O6: CHICAGO FED NATIONAL FINANCIAL CONDITIONS INDEX (NFCI)
# Estres financiero global. Complementa Ormuz.
# Fuente: FRED NFCI (semanal, viernes)
# ============================================================

async def get_o6_freight() -> Tuple[float, Dict]:
    """
    O6: Supply Chain Stress (5 pts max)
    Chicago Fed National Financial Conditions Index (NFCI).
    Negativo = holgado, positivo = apretado. >0.5 = estres financiero significativo.
    """
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": "NFCI",
                    "api_key": FRED_KEY,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": "10",
                },
                timeout=15,
            )
            data = resp.json()
            obs = data.get("observations", [])

            if not obs or obs[0].get("value") == ".":
                return 0, {"signal": "O6_FREIGHT", "error": "No data", "score": 0, "max_score": 5}

            current = float(obs[0]["value"])
            current_date = obs[0]["date"]
            prev = None
            for o in obs[1:]:
                if o.get("value") != ".":
                    prev = float(o["value"])
                    break

            score = 0
            if current > 1.0:
                score = 5
            elif current > 0.5:
                score = 3
            elif current > 0.0:
                score = 1

            return score, {
                "signal": "O6_FREIGHT",
                "value": round(current, 2),
                "date": current_date,
                "prev_value": round(prev, 2) if prev else None,
                "status": "ESTRES" if current > 0.5 else "HOLGADO" if current < 0 else "NEUTRAL",
                "note": "NFCI: Negativo = condiciones holgadas. Positivo = estres. >0.5 = apretado significativamente.",
                "score": score,
                "max_score": 5,
            }
        except Exception as e:
            return 0, {"signal": "O6_FREIGHT", "error": str(e), "score": 0, "max_score": 5}
