#!/usr/bin/env python3
"""
MINI-TEST G14 — ¿anticipa o solo hace ruido?

G14 pretende anticipar un unwind de carry (correlacion yen/peso hacia -1) ANTES de que pase.
Preguntas falsables:

TEST A — ¿G14 predice el movimiento FUTURO del peso?
  Si G14 (velocidad_24h alta, o corr_20d cayendo) el dia D, ¿el peso se mueve mas en D+1..D+3
  que cuando G14 esta tranquilo? Si no hay diferencia, G14 no anticipa nada del peso.

TEST B — ¿G14 anticipa a G12, o G12 se mueve primero?
  ¿La velocidad de G14 sube ANTES de que el yen (G12) se mueva fuerte, o al mismo tiempo/despues?
  Si G14 no adelanta a G12, no aporta ventaja temporal: G12 solo ya da la senal.

Metodo: correlacion con lag. Sin numpy.
"""
import json, glob, os

base = "/mnt/ssd/pvrolo-data/repos/fantasma"
files = sorted(glob.glob(os.path.join(base, "data/history/*.json")))

def find_signal(data, sig):
    for mod in data.get("modules", {}).values():
        for s in mod.get("signals", []):
            if s.get("signal") == sig:
                return s
    return None

# Serie alineada: fecha, fix, g14_vel, g14_corr20, g12_yen(usdjpy)
fechas, fix, vel, corr20, yen = [], [], [], [], []
for f in files:
    try:
        d = json.load(open(f))
        c1 = find_signal(d,"C1_FIX")
        g14 = find_signal(d,"G14_YEN_MXN_VELOCITY")
        g12 = find_signal(d,"G12_YEN_PRESSURE")
        if c1 and g14 and g12 and g14.get("corr_20d") is not None and g14.get("velocidad_24h") is not None:
            v_fix = c1.get("value"); v_vel = g14.get("velocidad_24h")
            v_c20 = g14.get("corr_20d"); v_yen = g12.get("usdjpy_current") or g12.get("value")
            if None not in (v_fix,v_vel,v_c20,v_yen):
                fechas.append(os.path.basename(f).replace(".json",""))
                fix.append(float(v_fix)); vel.append(float(v_vel))
                corr20.append(float(v_c20)); yen.append(float(v_yen))
    except Exception:
        pass

n = len(fix)
print(f"Serie util: {n} dias ({fechas[0]} -> {fechas[-1]})")

def pct_change(series):
    return [ (series[i]-series[i-1])/series[i-1] if series[i-1] else 0.0 for i in range(1,len(series)) ]

def pearson(a,b):
    m=len(a)
    if m<3: return None
    ma,mb=sum(a)/m,sum(b)/m
    num=sum((a[i]-ma)*(b[i]-mb) for i in range(m))
    da=sum((a[i]-ma)**2 for i in range(m))**0.5
    db=sum((b[i]-mb)**2 for i in range(m))**0.5
    if da==0 or db==0: return None
    return num/(da*db)

# abs del retorno diario del peso (magnitud de movimiento)
fix_ret = [abs(x) for x in pct_change(fix)]     # len n-1, indice i corresponde a dia i+1
yen_ret = [abs(x) for x in pct_change(yen)]      # magnitud mov del yen

# --- TEST A: G14 velocidad del dia D predice |mov peso| en D+1, D+2, D+3 ---
print("\n=== TEST A: G14.velocidad_24h[D] vs |retorno peso|[D+k] ===")
print("(Si G14 anticipa, corr POSITIVA y creciente con el lag. Si ~0, no predice)")
for lag in [0,1,2,3]:
    xs, ys = [], []
    for i in range(n-1):
        d_idx = i               # dia D (vel medido en dia i)
        fut = i + lag           # retorno del peso 'lag' dias despues (fix_ret[fut-1] approx)
        # fix_ret[j] es el retorno del dia j+1 respecto j
        j = d_idx + lag
        if 0 <= j < len(fix_ret):
            xs.append(vel[d_idx]); ys.append(fix_ret[j])
    r = pearson(xs,ys)
    print(f"  lag +{lag}d: r(vel, |mov_peso|) = {r:+.3f}  (n={len(xs)})" if r is not None else f"  lag +{lag}d: sin datos")

# --- TEST B: G14 velocidad anticipa el movimiento del yen? ---
print("\n=== TEST B: G14.velocidad_24h[D] vs |mov yen|[D+k] ===")
print("(Si G14 adelanta a G12, corr positiva con lag>0. Si el pico es en lag 0 o negativo, no adelanta)")
for lag in [-2,-1,0,1,2]:
    xs, ys = [], []
    for i in range(n-1):
        j = i + lag
        if 0 <= j < len(yen_ret) and 0 <= i < len(vel):
            xs.append(vel[i]); ys.append(yen_ret[j])
    r = pearson(xs,ys)
    tag = "(G14 antes)" if lag>0 else ("(mismo dia)" if lag==0 else "(yen antes)")
    print(f"  lag {lag:+d}d {tag}: r = {r:+.3f}  (n={len(xs)})" if r is not None else f"  lag {lag:+d}: sin datos")

# --- TEST C: corr_20d baja (hacia unwind) predice peso debil? ---
print("\n=== TEST C: G14.corr_20d[D] vs retorno FIRMADO del peso[D+1..3] ===")
print("(Tesis del indicador: corr_20d hacia -1 = unwind = peso se DEBILITA (fix sube).")
print(" Si fuera cierto, corr_20d baja deberia preceder fix subiendo -> corr NEGATIVA)")
fix_ret_signed = pct_change(fix)
for lag in [1,2,3]:
    xs, ys = [], []
    for i in range(n-1):
        j = i + lag
        if 0 <= j < len(fix_ret_signed):
            xs.append(corr20[i]); ys.append(fix_ret_signed[j])
    r = pearson(xs,ys)
    print(f"  lag +{lag}d: r(corr_20d, retorno_peso) = {r:+.3f}  (n={len(xs)})" if r is not None else f"  lag +{lag}: sin datos")

print("\n=== VEREDICTO AUTOMATICO ===")
# Test A: si todos los |r| < 0.2, G14 no predice magnitud del peso
a_rs = []
for lag in [1,2,3]:
    xs,ys=[],[]
    for i in range(n-1):
        j=i+lag
        if 0<=j<len(fix_ret): xs.append(vel[i]); ys.append(fix_ret[j])
    r=pearson(xs,ys)
    if r is not None: a_rs.append(abs(r))
maxA = max(a_rs) if a_rs else 0
if maxA < 0.2:
    print(f"TEST A: G14 NO predice el movimiento del peso (max|r|={maxA:.3f} < 0.2). Es RUIDO para el peso.")
else:
    print(f"TEST A: G14 tiene alguna relacion con el peso futuro (max|r|={maxA:.3f}). Investigar mas.")
