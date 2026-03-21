"""
FANTASMA / OBSERVATORIO - Modulo "Dias en Rojo"
Cuenta dias consecutivos que cada senal ha estado por encima de su umbral absoluto.
Los umbrales son FIJOS y PERMANENTES. No se recalibran.

Lee el historial de full_report JSONB en Supabase y calcula rachas.
"""
import os
import json
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pwsrjmhmxqfxmcadhjtz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ============================================================
# UMBRALES ABSOLUTOS — CONGELADOS. NO SE RECALIBRAN.
# Si el valor supera el umbral, el dia cuenta como "rojo".
# Fuente: scoring original del Observatorio + decision Arquitecto.
# ============================================================
RED_THRESHOLDS = {
    # Modulo Ormuz
    "O1_BRENT":    {"field": "value", "op": ">",  "threshold": 100, "label": "Brent Crude"},
    "O2_GAS_EU":   {"field": "value", "op": ">",  "threshold": 50,  "label": "Gas Europa TTF"},
    "O3_USDCHF":   {"field": "weekly_change_pct", "op": "<", "threshold": -1, "label": "USD/CHF (refugio)"},
    "O5_WAR_RISK":  {"field": "spread", "op": ">", "threshold": 8,  "label": "War Risk (Brent-WTI)"},
    # Modulo Mexico
    "M1_USDMXN":   {"field": "value", "op": ">",  "threshold": 20,  "label": "USD/MXN"},
    "M2_CORN":     {"field": "value", "op": ">",  "threshold": 450, "label": "Maiz"},
    # Modulo Global
    "G1_VIX":      {"field": "value", "op": ">",  "threshold": 25,  "label": "VIX"},
    "G2_DXY":      {"field": "value", "op": ">",  "threshold": 105, "label": "Dolar Index"},
    "G3_US10Y":    {"field": "value", "op": ">",  "threshold": 4.5, "label": "US 10Y"},
    "G5_COPPER":   {"field": "monthly_change_pct", "op": "<", "threshold": -5, "label": "Cobre (caida)"},
    # Modulo Core MXN
    "C1_FIX":      {"field": "daily_change_pct", "op": ">", "threshold": 1.5, "label": "FIX Banxico"},
}


def _is_red(signal_data: dict, threshold_config: dict) -> bool:
    """Determina si una senal esta en rojo dado su umbral absoluto."""
    value = signal_data.get(threshold_config["field"])
    if value is None:
        return False
    op = threshold_config["op"]
    thresh = threshold_config["threshold"]
    if op == ">":
        return value > thresh
    elif op == "<":
        return value < thresh
    elif op == ">=":
        return value >= thresh
    elif op == "<=":
        return value <= thresh
    return False


def _extract_signal_from_report(full_report: dict, signal_name: str) -> Optional[dict]:
    """Extrae datos de una senal del full_report JSONB."""
    modules = full_report.get("modules", {})
    for mod_key, mod_data in modules.items():
        for s in mod_data.get("signals", []):
            if s.get("signal") == signal_name:
                return s
    return None


async def fetch_history_reports(days: int = 90) -> List[dict]:
    """Obtiene full_report de Supabase para los ultimos N dias."""
    date_from = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/fantasma_daily_scores",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                },
                params={
                    "select": "date,full_report",
                    "date": f"gte.{date_from}",
                    "order": "date.desc",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"dias_rojo: Supabase error: {e}")
    return []


async def calculate_dias_rojo(current_report: dict = None) -> Dict:
    """
    Calcula dias consecutivos en rojo para cada senal monitoreada.
    Recorre el historial de mas reciente a mas antiguo.
    La racha se rompe en el primer dia que NO esta en rojo.
    
    Si se pasa current_report, se incluye como "dia de hoy" (aun no guardado).
    """
    rows = await fetch_history_reports(days=90)
    
    # Si tenemos reporte actual, lo prepend como el dia mas reciente
    if current_report:
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        # Evitar duplicado si hoy ya esta en el historial
        if not rows or rows[0].get("date") != today_str:
            rows.insert(0, {"date": today_str, "full_report": current_report})
    
    results = {}
    
    for signal_name, config in RED_THRESHOLDS.items():
        consecutive = 0
        first_red_date = None
        current_value = None
        is_red_now = False
        
        for i, row in enumerate(rows):
            report = row.get("full_report", {})
            if not report:
                break
            
            signal_data = _extract_signal_from_report(report, signal_name)
            if signal_data is None:
                break  # Senal no existia en este dia, rompe racha
            
            if i == 0:
                current_value = signal_data.get(config["field"])
                is_red_now = _is_red(signal_data, config)
            
            if _is_red(signal_data, config):
                consecutive += 1
                first_red_date = row.get("date")
            else:
                break  # Racha rota
        
        results[signal_name] = {
            "label": config["label"],
            "threshold": config["threshold"],
            "op": config["op"],
            "field": config["field"],
            "current_value": current_value,
            "is_red": is_red_now,
            "consecutive_days": consecutive,
            "red_since": first_red_date if consecutive > 0 else None,
        }
    
    # Resumen de profundizacion
    red_signals = [k for k, v in results.items() if v["is_red"]]
    chronic_signals = [k for k, v in results.items() if v["consecutive_days"] >= 30]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "signals": results,
        "summary": {
            "total_monitored": len(RED_THRESHOLDS),
            "currently_red": len(red_signals),
            "red_signals": red_signals,
            "chronic_30d": len(chronic_signals),
            "chronic_signals": chronic_signals,
        },
    }


if __name__ == "__main__":
    result = asyncio.run(calculate_dias_rojo())
    print(json.dumps(result, indent=2, ensure_ascii=False))
