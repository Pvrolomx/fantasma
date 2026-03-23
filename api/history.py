"""
FANTASMA / OBSERVATORIO - History Module (Supabase)
Guarda snapshot diario en Supabase y sirve historico.
Fallback a archivos locales si Supabase no disponible.
"""
import json
import os
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass
import asyncio
import httpx
from datetime import datetime, timedelta
from pathlib import Path

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pwsrjmhmxqfxmcadhjtz.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

HISTORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "history")


def ensure_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def _extract_signal_value(signals, signal_name, field="value"):
    """Helper to extract a specific signal value from the report."""
    for mod in signals.values():
        for s in mod.get("signals", []):
            if s.get("signal") == signal_name:
                return s.get(field, 0)
    return 0


async def save_snapshot(report: dict):
    """Guarda el reporte en Supabase y local."""
    # Local backup (skip on read-only filesystem like Vercel)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    local_path = None
    try:
        ensure_dir()
        local_path = os.path.join(HISTORY_DIR, f"{date_str}.json")
        with open(local_path, "w") as lf:
            json.dump(report, lf, ensure_ascii=False, indent=2)
    except OSError:
        pass  # Read-only filesystem

    # Supabase upsert
    try:
        modules = report.get("modules", {})
        p0 = report.get("protocolo_0", {})
        row = {
            "date": date_str,
            "total_score": report.get("total_score", 0),
            "raw_score": report.get("raw_score", 0),
            "max_raw": report.get("max_raw", 180),
            "alert_level": report.get("alert_level", "N/A"),
            "alert_emoji": report.get("alert_emoji", ""),
            "recommended_action": report.get("recommended_action", ""),
            "core_mxn_score": modules.get("core_mxn", {}).get("score", 0),
            "global_overlay_score": modules.get("global_overlay", {}).get("score", 0),
            "ormuz_score": modules.get("ormuz_coreografia", {}).get("score", 0),
            "mexico_score": modules.get("mexico_local", {}).get("score", 0),
            "protocolo_0_active": p0.get("protocolo_0_active", False),
            "protocolo_0_severity": p0.get("severity", ""),
            "protocolo_0_alerts_count": p0.get("alerts_count", 0),
            "brent_price": _extract_signal_value(modules, "O1_BRENT"),
            "gas_eu_price": _extract_signal_value(modules, "O2_GAS_EU"),
            "usdmxn": _extract_signal_value(modules, "M1_USDMXN"),
            "vix": _extract_signal_value(modules, "G1_VIX"),
            "war_risk_spread": _extract_signal_value(modules, "O5_WAR_RISK", "spread"),
            "corn_price": _extract_signal_value(modules, "M2_CORN"),
            "active_signals": report.get("active_signals", 0),
            "full_report": report,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/fantasma_daily_scores",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
                json=row, timeout=15
            )
            if resp.status_code < 300:
                print(f"Supabase: saved {date_str}")
            else:
                print(f"Supabase error: {resp.status_code} {resp.text}")

        # Also save protocolo alerts (same client session)
            if p0.get("protocolo_0_active") and p0.get("alerts"):
                for alert in p0["alerts"]:
                    alert_row = {
                        "date": date_str,
                        "alert_type": alert.get("type", ""),
                        "alert_name": alert.get("name", ""),
                        "severity": alert.get("severity", ""),
                        "message": alert.get("message", ""),
                        "data": alert,
                    }
                    await client.post(
                        f"{SUPABASE_URL}/rest/v1/fantasma_protocolo_alerts",
                        headers=HEADERS, json=alert_row, timeout=10
                    )
                print(f"Supabase: saved {len(p0['alerts'])} alerts")
    except Exception as e:
        print(f"Supabase save error: {e}")

    return local_path


async def load_history(days: int = 30) -> list:
    """Carga historial de Supabase. Fallback a local."""
    try:
        date_from = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/fantasma_daily_scores",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                params={
                    "select": "date,total_score,raw_score,alert_level,alert_emoji,core_mxn_score,global_overlay_score,ormuz_score,mexico_score,protocolo_0_active,active_signals,brent_price,usdmxn,vix",
                    "date": f"gte.{date_from}",
                    "order": "date.asc",
                },
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                return [{
                    "date": r["date"],
                    "total_score": r["total_score"],
                    "alert_level": r["alert_level"],
                    "alert_emoji": r.get("alert_emoji", ""),
                    "modules": {
                        "core_mxn": r.get("core_mxn_score", 0),
                        "global_overlay": r.get("global_overlay_score", 0),
                        "ormuz_coreografia": r.get("ormuz_score", 0),
                        "mexico_local": r.get("mexico_score", 0),
                    },
                    "protocolo_0": r.get("protocolo_0_active", False),
                    "active_signals": r.get("active_signals", 0),
                } for r in data]
    except Exception as e:
        print(f"Supabase load error: {e}, falling back to local")

    # Fallback local
    return _load_local_history(days)


def _load_local_history(days: int = 30) -> list:
    """Fallback: carga historial de archivos locales."""
    try:
        ensure_dir()
    except OSError:
        return []  # Read-only filesystem (Vercel)
    results = []
    today = datetime.utcnow().date()
    for i in range(days):
        date = today - timedelta(days=i)
        fp = os.path.join(HISTORY_DIR, f"{date.isoformat()}.json")
        if os.path.exists(fp):
            with open(fp) as lf:
                data = json.load(lf)
                results.append({
                    "date": date.isoformat(),
                    "total_score": data.get("total_score", 0),
                    "alert_level": data.get("alert_level", "N/A"),
                    "alert_emoji": data.get("alert_emoji", ""),
                    "modules": {k: v.get("score", 0) for k, v in data.get("modules", {}).items()},
                    "protocolo_0": data.get("protocolo_0", {}).get("protocolo_0_active", False),
                    "active_signals": data.get("active_signals", 0),
                })
    results.reverse()
    return results


def get_daily_summary(history: list) -> dict:
    """Resumen de hoy vs ayer."""
    if len(history) < 1:
        return {"today": None, "yesterday": None, "change": 0}
    today = history[-1] if history else None
    yesterday = history[-2] if len(history) >= 2 else None
    change = 0
    if today and yesterday:
        change = today["total_score"] - yesterday["total_score"]
    return {
        "today": today, "yesterday": yesterday,
        "change": change,
        "direction": "up" if change > 0 else "down" if change < 0 else "flat"
    }


async def run_and_save():
    """Ejecuta scoring y guarda snapshot. Para cron."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from scoring import run_scoring
    report = await run_scoring()
    path = await save_snapshot(report)
    print(f"Snapshot saved: {path}")
    print(f"Score: {report['total_score']} - {report['alert_level']}")
    return report


if __name__ == "__main__":
    r = asyncio.run(run_and_save())
    print(json.dumps(r, indent=2, ensure_ascii=False))
