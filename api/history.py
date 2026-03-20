"""
FANTASMA / OBSERVATORIO - History Module
Guarda snapshot diario del score y sirve historico.
Almacena en ~/repos/fantasma/data/history/ como JSON por dia.
"""
import json
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

HISTORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'history')


def ensure_dir():
    os.makedirs(HISTORY_DIR, exist_ok=True)


def save_snapshot(report: dict):
    """Guarda el reporte del dia como JSON."""
    ensure_dir()
    date_str = datetime.utcnow().strftime('%Y-%m-%d')
    filepath = os.path.join(HISTORY_DIR, f'{date_str}.json')
    # Si ya existe un snapshot de hoy, lo sobreescribe con el mas reciente
    with open(filepath, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return filepath


def load_history(days: int = 30) -> list:
    """Carga los ultimos N dias de historia."""
    ensure_dir()
    results = []
    today = datetime.utcnow().date()
    for i in range(days):
        date = today - timedelta(days=i)
        filepath = os.path.join(HISTORY_DIR, f'{date.isoformat()}.json')
        if os.path.exists(filepath):
            with open(filepath) as f:
                data = json.load(f)
                results.append({
                    'date': date.isoformat(),
                    'total_score': data.get('total_score', 0),
                    'raw_score': data.get('raw_score', 0),
                    'alert_level': data.get('alert_level', 'N/A'),
                    'alert_emoji': data.get('alert_emoji', ''),
                    'modules': {
                        k: v.get('score', 0)
                        for k, v in data.get('modules', {}).items()
                    },
                    'protocolo_0': data.get('protocolo_0', {}).get('protocolo_0_active', False),
                    'active_signals': data.get('active_signals', 0),
                })
    results.reverse()  # Oldest first for charting
    return results


def get_daily_summary() -> dict:
    """Resumen rapido de hoy vs ayer."""
    history = load_history(days=2)
    if len(history) < 1:
        return {'today': None, 'yesterday': None, 'change': 0}
    today = history[-1] if history else None
    yesterday = history[-2] if len(history) >= 2 else None
    change = 0
    if today and yesterday:
        change = today['total_score'] - yesterday['total_score']
    return {
        'today': today,
        'yesterday': yesterday,
        'change': change,
        'direction': 'up' if change > 0 else 'down' if change < 0 else 'flat'
    }


async def run_and_save():
    """Ejecuta scoring y guarda snapshot. Para cron."""
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from scoring import run_scoring
    report = await run_scoring()
    path = save_snapshot(report)
    print(f"Snapshot saved: {path}")
    print(f"Score: {report['total_score']} - {report['alert_level']}")
    return report


if __name__ == '__main__':
    r = asyncio.run(run_and_save())
    print(json.dumps(r, indent=2, ensure_ascii=False))
