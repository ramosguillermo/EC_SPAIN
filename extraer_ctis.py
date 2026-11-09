#!/usr/bin/env python3
"""Descarga de CTIS (registro europeo, API pública) los criterios de inclusión/exclusión de los ensayos
de hematología publicados cuyo detalle en el REec NO los trae.
Uso (PowerShell, con internet):   python extraer_ctis.py
Guarda cada respuesta en datos/raw_ctis/<id>.json (caché) y, después, `python preparar_web.py` los incorpora a la web.
Opciones:  --todos  (también los que ya tienen criterios en el REec, para compararlos)   --forzar  (vuelve a descargar)"""
import json, re, sys, time, urllib.request, urllib.error
from pathlib import Path
D = Path(__file__).parent
RAW, CTIS = D / "datos/raw", D / "datos/raw_ctis"
CTIS.mkdir(exist_ok=True)
URL = "https://euclinicaltrials.eu/ctis-public-api/retrieve/{}"
from enriquecer import criterios_ctis

ids = json.loads((D / "datos/ids_hematologia.json").read_text(encoding="utf-8"))["incluir"]
pendientes = []
for i in ids:
    if not re.match(r"^\d{4}-\d{6}-\d{2}-\d{2}$", i):
        continue                                           # los EudraCT antiguos no están en CTIS
    f = RAW / f"{i}.json"
    inf = json.loads(f.read_text(encoding="utf-8")).get("informacion", {}) if f.exists() else {}
    if "--todos" in sys.argv or not (inf.get("criteriosInclusion") or inf.get("criteriosExclusion")):
        pendientes.append(i)
print(f"{len(pendientes)} ensayos para consultar en CTIS")
ok = vacios = fallos = 0
for n, i in enumerate(pendientes, 1):
    dest = CTIS / f"{i}.json"
    if not dest.exists() or "--forzar" in sys.argv:
        req = urllib.request.Request(URL.format(i), headers={"Accept": "application/json", "User-Agent": "ensayos-hematologia-web (uso academico)"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                dest.write_bytes(r.read())
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  [{n}/{len(pendientes)}] {i}: ERROR {e}"); fallos += 1; continue
        time.sleep(1.5)                                    # sin saturar el servidor
    inc, exc = criterios_ctis(json.loads(dest.read_text(encoding="utf-8")))
    if inc or exc:
        ok += 1
    else:
        vacios += 1
    print(f"  [{n}/{len(pendientes)}] {i}: {len(inc)} inclusión, {len(exc)} exclusión")
print(f"\nCon criterios: {ok} | sin criterios en CTIS: {vacios} | errores de red: {fallos}")
print("Ahora ejecuta:  python preparar_web.py")
