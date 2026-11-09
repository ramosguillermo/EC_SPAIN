#!/usr/bin/env python3
"""Orquestador: aplica decisiones y ejecuta toda la cadena de datos.
Uso: python actualizar.py [--sin-red] [--desde N] [--solo-web]
  --sin-red : omite los pasos que consultan REEC/CTIS/CT.gov (usa lo ya descargado)
  --desde N : empieza en el paso N (ver lista)"""
import argparse, subprocess, sys, time
from pathlib import Path

D = Path(__file__).parent
PASOS = [  # (nombre, comando, usa_red)
    ("Aplicar decisiones de revisión", ["aplicar_decisiones.py"], False),
    ("REEC: búsqueda", ["extraer_reec.py", "--fin-reclutamiento", "--solo-busqueda"], True),
    ("Clasificar hematología", ["clasificar_hematologia.py"], False),
    ("REEC: detalle", ["extraer_reec.py", "--hematologia", "--fin-reclutamiento"], True),
    ("Geocodificar", ["geocodificar.py"], True),
    ("Fusionar hospitales", ["fusionar_hospitales.py"], False),
    ("CTIS", ["extraer_ctis.py", "--todos"], True),
    ("ClinicalTrials.gov", ["extraer_ctgov.py"], True),
    ("Preparar web", ["preparar_web.py"], False),
    ("Cola de revisión y novedades", ["revision.py"], False),
]

ap = argparse.ArgumentParser()
ap.add_argument("--sin-red", action="store_true"); ap.add_argument("--desde", type=int, default=1); ap.add_argument("--solo-web", action="store_true")
A = ap.parse_args()
inicio = 9 if A.solo_web else A.desde
for n, (nombre, cmd, red) in enumerate(PASOS, 1):
    if n < inicio and n != 1: continue
    if n == 1 and inicio > 1 and not A.solo_web: pass
    if red and A.sin_red:
        print(f"[{n}] {nombre}: omitido (--sin-red)"); continue
    print(f"\n=== [{n}/{len(PASOS)}] {nombre} ===", flush=True); t = time.time()
    r = subprocess.run([sys.executable, str(D / cmd[0])] + cmd[1:], cwd=D)
    if r.returncode != 0:
        print(f"ERROR en «{nombre}» (código {r.returncode})", file=sys.stderr); sys.exit(r.returncode)
    print(f"    ({time.time()-t:.0f} s)")
nov = D / "datos/novedades.md"
if nov.exists():
    txt = nov.read_text(encoding="utf-8"); print("\n" + txt)
    import os
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s: open(s, "a", encoding="utf-8").write(txt + "\n")
