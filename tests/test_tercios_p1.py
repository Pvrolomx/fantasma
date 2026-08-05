#!/usr/bin/env python3
"""
TEST DE TERCIOS — P1 (reanclaje Indice de Manipulacion: Brent -> DXY)
Pregunta: la correlacion peso/DXY se sostiene en los tres tercios de la serie,
o un solo tramo carga el promedio?

Metodo:
- Serie diaria de FIX, DXY, Brent (120 dias).
- Correlacion sobre CAMBIOS diarios (retornos), no niveles. Correlacionar niveles
  produce correlaciones espurias por tendencia comun; los retornos son lo correcto.
- Pearson r por tercio (40 dias c/u) y global.
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

# Extraer series alineadas por fecha
fechas, fix, dxy, brent = [], [], [], []
for f in files:
    try:
        d = json.load(open(f))
        c1, g2, o1 = find_signal(d,"C1_FIX"), find_signal(d,"G2_DXY"), find_signal(d,"O1_BRENT")
        if c1 and g2 and o1:
            v_fix, v_dxy, v_brent = c1.get("value"), g2.get("value"), o1.get("value")
            if None not in (v_fix, v_dxy, v_brent):
                fechas.append(os.path.basename(f).replace(".json",""))
                fix.append(float(v_fix)); dxy.append(float(v_dxy)); brent.append(float(v_brent))
    except Exception as e:
        pass

n = len(fix)
print(f"Serie: {n} dias ({fechas[0]} -> {fechas[-1]})")

# Retornos diarios (pct change)
def returns(series):
    out = []
    for i in range(1, len(series)):
        prev = series[i-1]
        out.append((series[i]-prev)/prev if prev else 0.0)
    return out

r_fix, r_dxy, r_brent = returns(fix), returns(dxy), returns(brent)

# Pearson sin numpy
def pearson(a, b):
    m = len(a)
    if m < 3: return None
    ma, mb = sum(a)/m, sum(b)/m
    num = sum((a[i]-ma)*(b[i]-mb) for i in range(m))
    da = sum((a[i]-ma)**2 for i in range(m))**0.5
    db = sum((b[i]-mb)**2 for i in range(m))**0.5
    if da == 0 or db == 0: return None
    return num/(da*db)

# Nota: el peso (USDMXN) y el DXY deberian correlacionar POSITIVO
# (dolar sube -> USDMXN sube). Igual peso/Brent no tiene signo obvio.
print("\n=== CORRELACION SOBRE RETORNOS DIARIOS ===")
print(f"GLOBAL ({len(r_fix)} obs):")
print(f"  peso/DXY   r = {pearson(r_fix, r_dxy):+.3f}")
print(f"  peso/Brent r = {pearson(r_fix, r_brent):+.3f}")

# Tercios sobre los retornos
L = len(r_fix)
t = L // 3
tramos = [(0, t), (t, 2*t), (2*t, L)]
print("\n=== TEST DE TERCIOS (peso/DXY) ===")
dxy_por_tercio = []
for i, (a, b) in enumerate(tramos, 1):
    r = pearson(r_fix[a:b], r_dxy[a:b])
    dxy_por_tercio.append(r)
    print(f"  Tercio {i} [{fechas[a]}..{fechas[min(b,len(fechas)-1)]}], n={b-a}:  r(DXY) = {r:+.3f}")

print("\n=== TEST DE TERCIOS (peso/Brent) — control ===")
for i, (a, b) in enumerate(tramos, 1):
    r = pearson(r_fix[a:b], r_brent[a:b])
    print(f"  Tercio {i}, n={b-a}:  r(Brent) = {r:+.3f}")

# VEREDICTO
print("\n=== VEREDICTO ===")
vals = [abs(x) for x in dxy_por_tercio if x is not None]
signos = [x for x in dxy_por_tercio if x is not None]
todos_positivos = all(x > 0 for x in signos)
minimo = min(vals); maximo = max(vals)
rango = maximo - minimo
print(f"r(DXY) por tercio (abs): min={minimo:.3f}, max={maximo:.3f}, rango={rango:.3f}")
print(f"Todos mismo signo (positivo esperado): {todos_positivos}")
if minimo >= 0.4 and todos_positivos and rango <= 0.35:
    print("RESULTADO: PASA. r(DXY) se sostiene en los tres tercios. Reanclaje JUSTIFICADO.")
elif minimo >= 0.3 and todos_positivos:
    print("RESULTADO: PASA DEBIL. Positivo en los tres pero con un tramo flojo. Reanclaje defendible, vigilar.")
else:
    print("RESULTADO: NO PASA. Un tramo carga el promedio o cambia de signo. NO reanclar aun.")
