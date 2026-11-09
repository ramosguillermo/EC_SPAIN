#!/usr/bin/env python3
"""
Geocodifica los centros de datos/ensayos.json con Nominatim (OpenStreetMap).
Añade lat, lon y 'precision' (direccion | nombre | cp | localidad | sin_resultado) a cada centro
y actualiza datos/ensayos.json y la hoja "Centros" de datos/reec_ensayos.xlsx.

Uso:  python geocodificar.py
      python geocodificar.py --incluir-inactivos   (por defecto se omiten activo=0 y activo=2)
Reanudable: guarda datos/geocache.json y solo consulta lo que falta.
Política de Nominatim: máx. 1 petición/segundo y User-Agent identificable (ya incluido).
"""
import argparse, json, re, time
from pathlib import Path
import requests
from openpyxl import load_workbook

DIR = Path(__file__).parent / "datos"
CACHE_F = DIR / "geocache.json"
URL = "https://nominatim.openstreetmap.org/search"
S = requests.Session()
S.headers["User-Agent"] = "reec-ensayos-web/0.1 (proyecto personal; contacto: ramosmorenoguillermo@gmail.com)"

def consulta(params):
    params = {**params, "format": "jsonv2", "countrycodes": "es", "limit": 1}
    for i in range(3):
        try:
            r = S.get(URL, params=params, timeout=30)
            time.sleep(1.1)                      # 1 petición/segundo
            if r.status_code == 200:
                js = r.json()
                if js:
                    lat, lon = float(js[0]["lat"]), float(js[0]["lon"])
                    if 27 <= lat <= 44.5 and -19 <= lon <= 5.5:   # España incl. Canarias y Baleares
                        return lat, lon
                return None
            time.sleep(3 * (i + 1))
        except (requests.RequestException, ValueError):
            time.sleep(3 * (i + 1))
    return None

def limpia_calle(d):
    d = re.sub(r"\b(?:[Bb]loque|[Ee]dificio|[Tt]orre)\s+[A-Z](?=[A-Z][a-zñáéíóú])", "", d or "")  # "Bloque DAvenida" -> "Avenida"
    d = re.sub(r"(?<=[a-zñáéíóú])(?=[A-ZÑÁÉÍÓÚ])", " ", d or "")   # "InfantilPasseig" -> "Infantil Passeig"
    d = re.sub(r"\b(s/n|s\.n\.|sn)\b\.?", "", d, flags=re.I)
    d = re.sub(r"\b(bloque|edificio|planta|local)\s+\w+(?:-\w+)?\b", "", d, flags=re.I)
    return re.sub(r"\s+", " ", d).strip(" ,.")

def normaliza_nombre(n):
    n = re.sub(r"\b(S\.?\s?L\.?U?|S\.?\s?A\.?U?)\b\.?", "", n or "")
    n = re.sub(r"\bGrupo\s+\w+\b", "", n, flags=re.I)
    n = re.sub(r"University Clinical Hospital", "Hospital Clínico Universitario", n, flags=re.I)
    n = re.sub(r"University Hospital", "Hospital Universitario", n, flags=re.I)
    n = re.sub(r"\bHospital Universitario (Virgen|Principe|Ramon|La |Del? )", r"Hospital Universitario \1", n)
    return re.sub(r"\s+", " ", n).strip(" ,.")

def km(a, b):
    from math import radians, sin, cos, asin, sqrt
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2-la1)/2)**2 + cos(la1)*cos(la2)*sin((lo2-lo1)/2)**2
    return 12742 * asin(sqrt(h))

def res(r, precision):
    return {"lat": r[0], "lon": r[1], "precision": precision}

def geocodifica(c):
    calle, cp = limpia_calle(c["domicilio"]), (c["cod_postal"] or "").strip()
    loc, prov, nombre = c["localidad"], c["provincia"], c["centro"]
    if calle:
        r = consulta({"street": calle, "postalcode": cp, "city": loc})
        if r: return res(r, "direccion")
    r_cp = consulta({"postalcode": cp, "city": loc})
    # por nombre del centro; solo se acepta si cae a <15 km del código postal
    r_nom = consulta({"q": f"{normaliza_nombre(nombre)}, {loc}"})
    if r_nom and (not r_cp or km(r_nom, r_cp) < 15):
        return res(r_nom, "nombre")
    if r_cp: return res(r_cp, "cp")
    r = consulta({"city": loc, "state": prov})
    return res(r, "localidad") if r else {"lat": "", "lon": "", "precision": "sin_resultado"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--incluir-inactivos", action="store_true")
    ap.add_argument("--reintentar", action="store_true", help="repite los centros que quedaron en cp/localidad/sin_resultado")
    a = ap.parse_args()
    datos = json.loads((DIR / "ensayos.json").read_text(encoding="utf-8"))
    cache = json.loads(CACHE_F.read_text(encoding="utf-8")) if CACHE_F.exists() else {}
    clave = lambda c: "|".join(str(c[k]).strip().lower() for k in ("centro", "domicilio", "cod_postal", "localidad"))
    if a.reintentar:
        cache = {k: v for k, v in cache.items() if v["precision"] in ("direccion", "nombre")}
    pendientes = {}
    for c in datos["centros"]:
        if str(c["activo"]) in ("0", "2") and not a.incluir_inactivos:   # 0 = inactivo, 2 = cerrado (según REEC)
            continue
        k = clave(c)
        if k not in cache:
            pendientes[k] = c
    print(f"{len(pendientes)} centros por geocodificar (~{len(pendientes)*1.2/60:.0f} min como mínimo).")
    for n, (k, c) in enumerate(pendientes.items(), 1):
        cache[k] = geocodifica(c)
        if n % 10 == 0:
            CACHE_F.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            print(f"  {n}/{len(pendientes)}")
    CACHE_F.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    for c in datos["centros"]:
        g = cache.get(clave(c), {"lat": "", "lon": "", "precision": "omitido_inactivo"})
        c.update(g)
    (DIR / "ensayos.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    # Excel
    xf = DIR / "reec_ensayos.xlsx"
    wb = load_workbook(xf); ws = wb["Centros"]
    cab = [x.value for x in ws[1]]
    if "precision" not in cab:
        ws.cell(1, len(cab) + 1, "precision"); cab.append("precision")
    for fila, c in zip(ws.iter_rows(min_row=2), datos["centros"]):
        for campo in ("lat", "lon", "precision"):
            fila[0].parent.cell(fila[0].row, cab.index(campo) + 1, c[campo])
    try:
        wb.save(xf)
    except PermissionError:
        xf = DIR / "reec_ensayos_geocodificado.xlsx"
        wb.save(xf)
        print(f"AVISO: reec_ensayos.xlsx estaba abierto en Excel; he guardado {xf.name}")
    from collections import Counter
    print("Resultado:", dict(Counter(c["precision"] for c in datos["centros"])))

if __name__ == "__main__":
    main()
