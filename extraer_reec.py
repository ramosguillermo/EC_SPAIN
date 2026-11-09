#!/usr/bin/env python3
"""
Extrae del REEC (AEMPS) los ensayos clínicos en estado "Reclutando" (y opcionalmente
"No iniciado") y genera:
  - datos/reec_ensayos.xlsx   (hojas: Ensayos, Centros)  -> base de datos inicial
  - datos/ensayos.json        (para la web)
Uso:  python extraer_reec.py            (solo Reclutando)
      python extraer_reec.py --no-iniciados
      python extraer_reec.py --limite 20   (prueba rápida)
Es reanudable: guarda cada detalle en datos/raw/ y no lo vuelve a pedir.
Requisitos: pip install requests openpyxl
"""
import argparse, html, json, re, sys, time
from pathlib import Path
import requests
from openpyxl import Workbook

BASE = "https://reec.aemps.es/reec-services"
DIR = Path(__file__).parent / "datos"
RAW = DIR / "raw"
RAW.mkdir(parents=True, exist_ok=True)
S = requests.Session()
S.headers["User-Agent"] = "reec-ensayos-web/0.1 (proyecto personal)"

def get(url, params=None, intentos=4):
    for i in range(intentos):
        try:
            r = S.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} en {url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  error de red ({e})", file=sys.stderr)
        time.sleep(2 * (i + 1))
    return None

def g(d, *nombres, default=""):
    """Lectura tolerante: busca claves sin distinguir mayúsculas/acentos."""
    if not isinstance(d, dict):
        return default
    mapa = {k.lower(): k for k in d}
    for n in nombres:
        if n.lower() in mapa:
            v = d[mapa[n.lower()]]
            return default if v is None else v
    return default

def limpia(v):
    """Quita etiquetas HTML, '|' sobrantes y espacios repetidos de los textos."""
    if not isinstance(v, str): return v
    for _ in range(2):
        v = html.unescape(v)                       # &ccedil; &amp;#39; ...
    v = re.sub(r"<[^>]+>", " ", v).replace("|", " ")
    return re.sub(r"\s+", " ", v).strip()

def lista(x):
    if x is None or x == "": return []
    return x if isinstance(x, list) else [x]

def primera_lista_de_dicts(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = primera_lista_de_dicts(v)
            if r and isinstance(r[0], dict):
                return r
    return []

def buscar(estado):
    r = get(f"{BASE}/busquedaestudios", {"estado": estado})
    if not r:
        return []
    try:
        j = r.json()
        if isinstance(j, dict):
            print("  claves de la respuesta:", list(j.keys())[:10])
        return primera_lista_de_dicts(j)
    except ValueError:
        sys.exit("La búsqueda no devolvió JSON. Revisa datos/ y la documentación del servicio.")

def detalle(ident):
    f = RAW / (re.sub(r"[^\w.-]", "_", ident) + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    r = get(f"{BASE}/json/detalle/{ident}")
    if not r:
        return None
    try:
        d = r.json()
    except ValueError:
        return None
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.5)  # cortesía con el servidor
    return d

def aplanar(ident, busq, det):
    e = det.get("Estudio", det) if isinstance(det, dict) else {}
    if isinstance(e, list) and e: e = e[0]
    info = g(e, "Informacion", default={})
    cal = g(e, "Calendario", default={})
    org = g(e, "Organismo", default={})
    pob = g(e, "Poblacion", default={})
    prop = g(e, "Proposito", default={})
    intervs = lista(g(e, "Intervenciones", default=[]))
    if isinstance(g(e, "Intervenciones", default=[]), dict):
        intervs = lista(g(g(e, "Intervenciones"), "Intervencion", default=[]))
    centros_raw = g(e, "Centros", default=[])
    if isinstance(centros_raw, dict):
        centros_raw = g(centros_raw, "Centro", default=[])
    centros = [c for c in lista(centros_raw) if isinstance(c, dict)]
    fases = [n for n, k in [("I","FaseUno"),("II","FaseDos"),("III","FaseTres"),("IV","FaseCuatro")]
             if str(g(prop, k)) in ("1", "true", "True")]
    ens = {
        "identificador": ident,
        "titulo": g(info, "TituloPublico") or g(busq, "titulo_es"),
        "titulo_cientifico": g(info, "TituloCientifico"),
        "indicacion": g(info, "IndicacionPublica") or g(busq, "indicacion_es"),
        "estado": g(busq, "estado"),
        "fase": "/".join(fases),
        "promotor": g(org, "Promotor") or g(busq, "promotor"),
        "financiador": g(org, "Financiador"),
        "contacto": g(org, "PersonaContacto"),
        "email_contacto": g(org, "Mail"),
        "telefono_contacto": g(org, "Telefono"),
        "enfermedad_rara": g(e, "EnfermedadRara") or g(busq, "enfermedadrara"),
        "fecha_autorizacion": g(cal, "FechaAutorizacionAEMPS") or g(busq, "fecha_autorizacion"),
        "fecha_inicio_real": g(cal, "FechaInicioReal"),
        "fecha_fin_prevista": g(cal, "FechaFinPrevista"),
        "fecha_fin_real_espana": g(cal, "FechaFinRealEspana"),
        "fecha_fin_real_global": g(cal, "FechaFinRealGlobal"),
        "medicamentos": "; ".join(str(g(i, "NombreCientifico") or g(i, "NombreComercial")) for i in intervs if isinstance(i, dict)),
        "criterios_inclusion": g(info, "CriteriosInclusion"),
        "criterios_exclusion": g(info, "CriteriosExclusion"),
        "adultos": g(pob, "Adultos"), "ninos": g(pob, "Ninos"), "adolescentes": g(pob, "Adolescentes"),
        "ancianos": g(pob, "Ancianos"),
        "n_centros": len(centros),
        "url_reec": f"https://reec.aemps.es/reec/estudio/{ident}",
    }
    ens = {k: limpia(v) for k, v in ens.items()}
    cen = [{
        "identificador": ident,
        "centro": g(c, "Nombre"),
        "domicilio": g(c, "Domicilio"),
        "localidad": g(c, "Localidad"),
        "cod_postal": g(c, "CodPostal"),
        "provincia": g(c, "Provincia"),
        "ccaa": g(c, "CCAA"),
        "servicio": g(c, "Departamento"),
        "investigador": g(c, "Investigador"),
        "activo": g(c, "Situacion"),
        "lat": "", "lon": "",   # se rellenan en la fase de geocodificación
    } for c in centros]
    cen = [{k: limpia(v) for k, v in c.items()} for c in cen]
    return ens, cen

def resolver_estados(ensayos, centros):
    """El REec devuelve «Finalizado» y «Fin reclutamiento» con dos códigos numéricos. Se distinguen por la fecha de fin real:
    el conjunto con MENOS ensayos con fecha de fin es «Fin reclutamiento»; el otro se descarta."""
    cuota = {}
    for cod in (3, 4):
        xs = [e for e in ensayos if e["estado"] == f"Estado {cod}"]
        if xs:
            cuota[cod] = sum(1 for e in xs if e.get("fecha_fin_real_global") or e.get("fecha_fin_real_espana")) / len(xs)
        print(f"  estado {cod}: {len(xs)} estudios de hematología" + (f", {cuota[cod]:.0%} con fecha de fin real" if xs else ""))
    if not cuota:
        return ensayos, centros
    fin = min(cuota, key=cuota.get) if len(cuota) == 2 else (next(iter(cuota)) if next(iter(cuota.values())) < .5 else None)
    quitar = set()
    for e in ensayos:
        if e["estado"] in ("Estado 3", "Estado 4"):
            if fin is not None and e["estado"] == f"Estado {fin}":
                e["estado"] = "Fin reclutamiento"
            else:
                quitar.add(e["identificador"])
    print(f"  -> «Fin reclutamiento» = estado {fin}; se descartan {len(quitar)} estudios finalizados")
    return [e for e in ensayos if e["identificador"] not in quitar], [c for c in centros if c["identificador"] not in quitar]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-iniciados", action="store_true")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--fin-reclutamiento", action="store_true",
                    help="añade los estudios que el REec marca como «Fin reclutamiento» (siguen activos con pacientes ya incluidos). "
                         "Sondea los códigos de estado 3 y 4 y deduce cuál es cuál por las fechas de fin")
    ap.add_argument("--solo-busqueda", action="store_true",
                    help="solo guarda datos/busqueda.json (listado de ensayos) y termina")
    ap.add_argument("--hematologia", action="store_true",
                    help="descarga el detalle solo de los ensayos de datos/ids_hematologia.json")
    a = ap.parse_args()
    estados = [2] + ([1] if a.no_iniciados else []) + ([3, 4] if a.fin_reclutamiento else [])
    resultados = {}
    for est in estados:
        print(f"Buscando estudios con estado={est} …")
        for b in buscar(est):
            ident = str(g(b, "identificador"))
            if ident:
                b["estado"] = {1: "No iniciado", 2: "Reclutando", 3: "Estado 3", 4: "Estado 4"}[est]
                resultados[ident] = b
    (DIR / "busqueda.json").write_text(
        json.dumps(list(resultados.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(resultados)} estudios en la búsqueda -> datos/busqueda.json")
    if a.solo_busqueda:
        return
    subareas = {}
    if a.hematologia:
        f = DIR / "ids_hematologia.json"
        if not f.exists():
            sys.exit("Falta datos/ids_hematologia.json: ejecuta antes clasificar_hematologia.py")
        clas = json.loads(f.read_text(encoding="utf-8"))
        subareas = clas.get("subareas", {})
        permitidos = set(clas["incluir"])   # los dudosos solo entran si los marcas como 'incluir'
        resultados = {k: v for k, v in resultados.items() if k in permitidos}
    ids = list(resultados)[: a.limite or None]
    print(f"{len(ids)} estudios; descargando detalles …")
    ensayos, centros, fallos = [], [], []
    for n, ident in enumerate(ids, 1):
        det = detalle(ident)
        if det is None:
            fallos.append(ident); continue
        e, c = aplanar(ident, resultados[ident], det)
        e["subareas"] = "; ".join(subareas.get(ident, []))
        ensayos.append(e); centros += c
        if n % 25 == 0: print(f"  {n}/{len(ids)}")
    if a.fin_reclutamiento:
        ensayos, centros = resolver_estados(ensayos, centros)
    # Excel
    wb = Workbook()
    for nombre, filas in (("Ensayos", ensayos), ("Centros", centros)):
        ws = wb.active if nombre == "Ensayos" else wb.create_sheet(nombre)
        ws.title = nombre
        if filas:
            ws.append(list(filas[0].keys()))
            for f in filas: ws.append([str(v) if isinstance(v, (dict, list)) else v for v in f.values()])
            ws.freeze_panes = "A2"
    try:
        wb.save(DIR / "reec_ensayos.xlsx")
    except PermissionError:
        wb.save(DIR / "reec_ensayos_nuevo.xlsx")
        print("AVISO: reec_ensayos.xlsx estaba abierto; guardado como reec_ensayos_nuevo.xlsx")
    (DIR / "ensayos.json").write_text(
        json.dumps({"ensayos": ensayos, "centros": centros}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Listo: {len(ensayos)} ensayos, {len(centros)} centros. Fallos: {len(fallos)} {fallos[:5]}")

if __name__ == "__main__":
    main()
