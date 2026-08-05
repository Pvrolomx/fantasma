#!/usr/bin/env python3
"""
SIGNAL HEALTH (P6-B) — detector de senales estancadas. READ-ONLY.
Recorre data/history/*.json y mide, por senal:
  (a) VALOR: cuantos dias consecutivos (hasta el ultimo snapshot) su 'value' no cambia.
  (b) FECHAS: si trae un campo *_date/consensus_date/timestamp mas viejo que UMBRAL dias.
Una senal estancada que sigue con "voz de alarma" es un falso positivo estructural
(F3_TECH_BLUE con Apple congelado, C6_CONTRARIAN con consensus de febrero).
NO altera el score. Solo diagnostica. Umbral de sospecha: 30 dias.
"""
import json, glob, os, datetime

base = "/mnt/ssd/pvrolo-data/repos/fantasma"
files = sorted(glob.glob(os.path.join(base, "data/history/*.json")))
UMBRAL = 30

def norm(x):
    return round(x, 4) if isinstance(x, (int, float)) else x

# fecha del ultimo snapshot = "hoy"
hoy_str = os.path.basename(files[-1]).replace(".json", "")
hoy = datetime.date.fromisoformat(hoy_str)

series = {}   # sig -> [(fecha, value)]
lastsig = {}  # sig -> dict completo del ultimo snapshot
modof = {}    # sig -> modulo
for f in files:
    fecha = os.path.basename(f).replace(".json", "")
    try:
        d = json.load(open(f))
    except Exception:
        continue
    for modname, mod in d.get("modules", {}).items():
        for s in mod.get("signals", []):
            sig = s.get("signal")
            if not sig:
                continue
            series.setdefault(sig, []).append((fecha, s.get("value")))
            lastsig[sig] = s
            modof[sig] = modname

# (a) staleness de VALOR: corrida final de valores iguales
rows = []
for sig, pts in series.items():
    last = pts[-1][1]
    run = 0
    since = pts[-1][0]
    if last is not None:
        for i in range(len(pts) - 1, -1, -1):
            if norm(pts[i][1]) == norm(last):
                run += 1
                since = pts[i][0]
            else:
                break
    rows.append([sig, modof[sig], last, run, since, len(pts)])

rows.sort(key=lambda r: -r[3])
print("HOY = %s | %d senales | umbral = %d dias\n" % (hoy_str, len(rows), UMBRAL))
print("%-24s%-16s%12s%11s  %-12s" % ("SENAL", "MODULO", "VALOR", "DIAS_IGUAL", "DESDE"))
for sig, mod, last, run, since, total in rows:
    flag = "  <-- ESTANCADA" if run >= UMBRAL else ""
    print("%-24s%-16s%12s%11d  %-12s%s" % (sig, mod[:15], str(last)[:12], run, since, flag))

# (b) staleness por FECHA embebida
print("\n--- Campos de fecha viejos (> %d dias) en el ultimo snapshot ---" % UMBRAL)
hits = 0
for sig, s in lastsig.items():
    for k, v in s.items():
        if isinstance(v, str) and ("date" in k.lower() or "consensus" in k.lower()):
            try:
                fd = datetime.date.fromisoformat(v[:10])
            except Exception:
                continue
            age = (hoy - fd).days
            if age > UMBRAL:
                print("  %s.%s = %s  (%d dias viejo)" % (sig, k, v[:10], age))
                hits += 1
if not hits:
    print("  (ninguno)")

est = [r for r in rows if r[3] >= UMBRAL]
print("\nRESUMEN: %d/%d senales con VALOR estancado >= %d dias:" % (len(est), len(rows), UMBRAL))
for r in est:
    print("  - %s (%s): %d dias en %s, sin cambio desde %s" % (r[0], r[1], r[3], r[2], r[4]))
