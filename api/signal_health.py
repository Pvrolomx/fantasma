# -*- coding: utf-8 -*-
"""
FANTASMA / OBSERVATORIO - Signal Health (P6-B): detector de senales estancadas.
Diagnostico NO-scoring. Por cada senal mide cuantos dias consecutivos su
campo-clave no cambia. Una senal 'estancada' que aun trae voz de alarma es un
falso positivo (F3 con el precio de Apple congelado, C6 con consensus viejo).
Lee del historico local (Pi). En entornos sin historico (Vercel) devuelve vacio.
Construido 05-ago-2026 con FIELD_MAP derivado del esquema real del snapshot.
"""
import os
import json
import glob

# Campo que carga el NUMERO real de cada senal (la mitad no usa 'value').
FIELD_MAP = {
    "C1_FIX": "value", "C2_TIIE": "value", "C3_CFTC": "net_contracts",
    "C4_RESERVAS": "value_millions", "C5_SPREAD": "spread_bps",
    "C6_CONTRARIAN": "consensus_eoy", "C7_CETES_NR": "value",
    "G1_VIX": "value", "G2_DXY": "value", "G3_US10Y": "value",
    "G4_HY_SPREAD": "spread_proxy", "G5_COPPER": "value",
    "G6_GOOGLE_TRENDS": "spike_ratio", "G7_VOLATILITY": "volatility_20d_annualized",
    "G8_CARRY_TRADE": "spread_bps", "G9_SWAP_LINES": "value_millions",
    "G10_INTERBANK": "spread_bps", "G11_DRAGON": "usdcny",
    "G12_YEN_PRESSURE": "value", "G13_CFTC_MOMENTUM": "net_contracts",
    "O1_BRENT": "value", "O2_GAS_EU": "value", "O3_USDCHF": "value",
    "O4_SOFR": "value", "O5_WAR_RISK": "spread", "O6_FREIGHT": "value",
    "M1_USDMXN": "value", "M2_CORN": "value", "M3_UREA": "value",
    "F1_USDT_P2P": "spread_buy_pct", "F2_ORO_FISICO": "estimated_premium_pct",
    "F3_TECH_BLUE": "apple_mx_price_mxn", "F4_REMESA": "spread_pct",
}
STALE_DAYS = 30
LOOKBACK = 90  # dias de historico a revisar


def _field(sig_dict):
    key = FIELD_MAP.get(sig_dict.get("signal"), "value")
    return sig_dict.get(key)


def _round(x):
    return round(x, 4) if isinstance(x, (int, float)) else x


def _signals_of(report):
    out = {}
    for mod in (report.get("modules") or {}).values():
        for s in mod.get("signals", []):
            if s.get("signal"):
                out[s["signal"]] = s
    return out


def compute_signal_health(history_dir, today_report=None):
    files = sorted(glob.glob(os.path.join(history_dir, "*.json")))[-LOOKBACK:]
    series = {}  # name -> [(fecha, valor_campo)]
    for f in files:
        fecha = os.path.basename(f).replace(".json", "")
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        for name, s in _signals_of(d).items():
            series.setdefault(name, []).append((fecha, _field(s)))
    # anexar HOY (su archivo aun no existe al momento del cron)
    if today_report is not None:
        hoy = (today_report.get("timestamp", "") or "hoy")[:10]
        for name, s in _signals_of(today_report).items():
            series.setdefault(name, []).append((hoy, _field(s)))

    stale = []
    for name, pts in series.items():
        last = pts[-1][1]
        run, since = 0, pts[-1][0]
        if last is not None:
            for i in range(len(pts) - 1, -1, -1):
                if _round(pts[i][1]) == _round(last):
                    run += 1
                    since = pts[i][0]
                else:
                    break
        if run >= STALE_DAYS:
            stale.append({
                "signal": name,
                "field": FIELD_MAP.get(name, "value"),
                "days_unchanged": run,
                "since": since,
                "last": last,
            })
    stale.sort(key=lambda r: -r["days_unchanged"])
    return {
        "checked": len(series),
        "stale_threshold_days": STALE_DAYS,
        "stale_count": len(stale),
        "stale": stale,
        "note": "Diagnostico no-scoring. 'Estancada' = campo clave sin cambio >= %d dias." % STALE_DAYS,
    }


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    hdir = os.path.join(os.path.dirname(here), "data", "history")
    print(json.dumps(compute_signal_health(hdir), indent=2, ensure_ascii=False))
