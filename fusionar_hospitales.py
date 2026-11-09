#!/usr/bin/env python3
"""
Fusiona las variantes del MISMO hospital en datos/ensayos.json (mayúsculas, acentos, apóstrofos,
códigos postales distintos, nombres equivalentes...) y les da un nombre, una dirección y unas
coordenadas únicos, más un `hospital_id`.

Orden del flujo:  extraer_reec.py -> geocodificar.py -> fusionar_hospitales.py -> preparar_web.py

Salidas (en datos/):
  hospitales.csv           registro de hospitales ya fusionados (separador ';'), con sus variantes
  hospitales_manual.csv    TUS correcciones (se conserva entre ejecuciones):
                             hospital_id;nombre;lat;lon;fusionar_con
                           - nombre/lat/lon: sustituyen a lo calculado (déjalo vacío si no cambia)
                           - fusionar_con: id de otro hospital con el que unirlo
  ensayos_antes_de_fusionar.json   copia de seguridad (solo la primera vez)

Uso:  python fusionar_hospitales.py
      python fusionar_hospitales.py --verificar-poi   (consulta Nominatim por el NOMBRE del hospital
                                                       para decidir cuando las variantes discrepan >150 m)
"""
import argparse, csv, html, json, math, re, shutil, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

D = Path(__file__).parent / "datos"
RANGO = {"nombre": 4, "direccion": 3, "cp": 2, "localidad": 1}      # fiabilidad de la coordenada
GENERICAS = set("hospital universitario general de del la las el los i y d l en s sl sa slu grupo consorcio asistencial".split())
EQUIV = {"clinical": "clinico", "universitari": "universitario", "universitaria": "universitario",
         "university": "universitario", "hospitalario": "hospital", "hospitalaria": "hospital",
         "complejo": "hospital", "complexo": "hospital", "hospitals": "hospital"}
# si lo que SOBRA en el nombre más largo es esto, son entidades distintas (no se fusionan por inclusión)
BLOQ = set("institut institute instituto fundacion foundation centro center centre cima vhio ico "
           "idibaps idibell vhir irb ciber clinica".split())
PART = {"de", "del", "y", "i", "e", "en"}     # partículas: siempre en minúscula (salvo la primera palabra)
ART = {"la", "las", "los", "el"}               # artículos: en minúscula solo tras "de" (Virgen de la Macarena, pero La Paz)
UMBRAL_CONFLICTO_M = 150

def na(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn").lower()

def tokens(nombre):
    s = re.sub(r"grupo\s+quironsalud|quironsalud\s+group", " ", na(nombre))
    s = re.sub(r"\bdhebron\b", "hebron", re.sub(r"[^a-z0-9]+", " ", s))   # "Vall DHebron" = "Vall d'Hebron"
    return frozenset(t for t in (EQUIV.get(x, x) for x in s.split()) if len(t) > 1 and t not in GENERICAS)

def norm_nombre(nombre):
    return re.sub(r"[^a-z0-9]+", " ", na(nombre)).strip()

def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))

def limpia_txt(s):
    """Decodifica entidades HTML (también las escapadas dos veces) y unifica apóstrofos."""
    s = str(s or "")
    for _ in range(2):
        s = html.unescape(s)
    s = re.sub(r"[´’‘`]", "'", s)
    return re.sub(r"\s+", " ", s).strip()

def bonito(s):
    s = limpia_txt(s)
    s = re.sub(r"^(el|la)\s+(?=hospital|complejo|complexo|instituto|clinica|clínica)", "", s, flags=re.I)
    forzar = any(ch.isalpha() for ch in s) and (s.isupper() or s.islower())   # TODO MAYÚSCULAS o todo minúsculas
    out = []
    for i, w in enumerate(s.split(" ")):
        lw = w.lower()
        prev = out[-1].lower() if out else ""
        if i > 0 and (lw in PART or (lw in ART and prev == "de")):
            out.append(lw)
        elif re.match(r"^[dl]'.", lw) and (forzar or i > 0):
            out.append(lw[:2] + lw[2:].capitalize() if i > 0 else lw[0].upper() + lw[1:].capitalize())
        elif forzar:
            out.append("-".join(p.capitalize() for p in lw.split("-")))
        else:
            out.append(w)
    return " ".join(out)

def bonito_dir(s):
    """Dirección legible: baja las palabras en MAYÚSCULAS (≥4 letras) y unifica 's/n'."""
    s = limpia_txt(s)
    s = re.sub(r"\b(s/n|sn)\b\.?", "s/n", s, flags=re.I)
    s = " ".join(w.capitalize() if (len(w) >= 4 and w.isupper()) else w for w in s.split(" "))
    return bonito(s)

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", na(s)).strip("-")[:70]

def num(x):
    try:
        v = float(x); return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def clave(c):
    return (limpia_txt(c["centro"]), limpia_txt(c["domicilio"]), limpia_txt(c["cod_postal"]),
            limpia_txt(c["localidad"]), limpia_txt(c["ccaa"]))

def mismo_hospital(a, b):
    if a["ccaa"] != b["ccaa"]:
        return False
    dist = km((a["lat"], a["lon"]), (b["lat"], b["lon"])) if a["lat"] is not None and b["lat"] is not None else None
    if a["nn"] == b["nn"] and (a["lk"] == b["lk"] or (dist is not None and dist < 5)):
        return True
    A, B = a["toks"], b["toks"]
    if not A or not B:
        return False
    cerca = a["lk"] == b["lk"] or (dist is not None and dist < 3)
    if not cerca:
        return False
    if A == B:
        return True
    peq, gran = (A, B) if len(A) <= len(B) else (B, A)
    return len(peq) >= 2 and peq <= gran and not (BLOQ & (gran - peq))

def leer_manual(f):
    man = {}
    if f.exists():
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                if r.get("hospital_id"):
                    man[r["hospital_id"].strip()] = {k: (r.get(k) or "").strip() for k in ("nombre", "lat", "lon", "fusionar_con")}
    return man

def agrupar(recs, extra_union=()):
    padre = list(range(len(recs)))
    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]; i = padre[i]
        return i
    def unir(i, j):
        padre[raiz(i)] = raiz(j)
    for i in range(len(recs)):
        for j in range(i + 1, len(recs)):
            if mismo_hospital(recs[i], recs[j]):
                unir(i, j)
    for i, j in extra_union:
        unir(i, j)
    for i, r in enumerate(recs):                       # registros sin localidad ni coordenadas
        if r["lk"] or r["lat"] is not None:
            continue
        cand = {raiz(j) for j, o in enumerate(recs) if j != i and o["ccaa"] == r["ccaa"] and o["lk"]
                and (o["nn"] == r["nn"] or (r["toks"] and o["toks"] == r["toks"]))}
        if len(cand) == 1:
            unir(i, next(iter(cand)))
    grupos = defaultdict(list)
    for i in range(len(recs)):
        grupos[raiz(i)].append(i)
    return list(grupos.values())

def canonico(miembros, recs):
    ms = [recs[i] for i in miembros]
    conc = Counter()
    for m in ms: conc[m["nombre"]] += m["n"]
    puntua = lambda nm: (sum(1 for ch in nm if ord(ch) > 127 or ch == "'"), conc[nm])   # más acentos/apóstrofos = mejor escrito
    nombre = bonito(max(conc, key=puntua))
    locs = Counter()
    for m in ms: locs[m["localidad"]] += m["n"]
    localidad = bonito(max(locs, key=lambda x: (sum(1 for ch in x if ord(ch) > 127), locs[x])))
    con = [m for m in ms if m["lat"] is not None]
    best = max(con, key=lambda m: (RANGO.get(m["prec"], 0), m["n"])) if con else max(ms, key=lambda m: m["n"])
    coords = sorted({(round(m["lat"], 5), round(m["lon"], 5)) for m in con})
    disp = max((km((best["lat"], best["lon"]), c) * 1000 for c in coords), default=0) if best["lat"] is not None else 0
    return {
        "nombre": nombre, "localidad": localidad, "domicilio": bonito_dir(best["domicilio"]),
        "cp": best["cp"], "ccaa": best["ccaa"], "provincia": Counter(m["provincia"] for m in ms).most_common(1)[0][0],
        "lat": best["lat"], "lon": best["lon"], "precision": best["prec"] if best["lat"] is not None else "",
        "fuente": "reglas" if best["lat"] is not None else "", "dispersion_m": round(disp),
        "coords": coords, "n_filas": sum(m["n"] for m in ms),
        "variantes": sorted({f'{m["nombre"]} [{m["cp"]} {m["localidad"]}]' for m in ms}),
        "nn_distintos": len({m["nn"] for m in ms}),
    }

def verificar_poi(reg):
    import geocodificar as G
    f = D / "geocache_poi.json"
    cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    pend = [h for h in reg if (h["dispersion_m"] > UMBRAL_CONFLICTO_M or h.get("sospechoso")) and h["fuente"] == "reglas"]
    print(f"Verificando por nombre {len(pend)} hospitales con variantes que discrepan >{UMBRAL_CONFLICTO_M} m …")
    for n, h in enumerate(pend, 1):
        q = f'{h["nombre"]}, {h["localidad"]}'
        if q not in cache:
            r = G.consulta({"q": q})
            cache[q] = list(r) if r else None
            f.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        r = cache[q]
        if r and ((h["coords"] and min(km(c, r) for c in h["coords"]) < 1.5) or (h.get("cp_ref") and km(h["cp_ref"], r) < 2)):
            h["lat"], h["lon"], h["fuente"], h["precision"] = r[0], r[1], "poi", "nombre"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verificar-poi", action="store_true")
    a = ap.parse_args()
    ruta = D / "ensayos.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    copia = D / "ensayos_antes_de_fusionar.json"
    centros = datos["centros"]
    if centros and "hospital_id" not in centros[0]:      # JSON recién generado (sin fusionar): guarda copia
        shutil.copy(ruta, copia)

    recs, idx = [], {}
    for c in centros:
        k = clave(c)
        if k not in idx:
            idx[k] = len(recs)
            recs.append({"nombre": k[0], "domicilio": k[1], "cp": k[2], "localidad": k[3], "ccaa": k[4],
                         "provincia": limpia_txt(c["provincia"]), "lat": num(c.get("lat")), "lon": num(c.get("lon")),
                         "prec": c.get("precision", ""), "n": 0, "toks": tokens(k[0]), "nn": norm_nombre(k[0]),
                         "loc": norm_nombre(k[3]), "lk": " ".join(sorted(norm_nombre(k[3]).split()))})
        recs[idx[k]]["n"] += 1

    manual = leer_manual(D / "hospitales_manual.csv")
    grupos = agrupar(recs)
    regs = [canonico(g, recs) for g in grupos]
    usados = Counter()
    for h, g in zip(regs, grupos):
        h["id"] = slug(h["nombre"] + " " + h["localidad"])
        usados[h["id"]] += 1
        if usados[h["id"]] > 1: h["id"] += f"-{usados[h['id']]}"
    # fusiones manuales
    id2g = {h["id"]: i for i, h in enumerate(regs)}
    extra = [(grupos[id2g[o]][0], grupos[id2g[m["fusionar_con"]]][0])
             for o, m in manual.items() if m["fusionar_con"] and o in id2g and m["fusionar_con"] in id2g]
    if extra:
        ids_prev = {tuple(sorted(g)): h["id"] for g, h in zip(grupos, regs)}
        grupos = agrupar(recs, extra)
        regs = [canonico(g, recs) for g in grupos]
        for h, g in zip(regs, grupos):
            h["id"] = next((i for k, i in ids_prev.items() if set(k) & set(g) and i in
                            {m["fusionar_con"] for m in manual.values() if m["fusionar_con"]}),
                           slug(h["nombre"] + " " + h["localidad"]))
    por_cp = defaultdict(list)
    for h in regs:
        if h["lat"] is not None and h["cp"]:
            por_cp[h["cp"]].append(h)
    for h in regs:                                     # ¿coordenada lejos de los demás hospitales de su código postal?
        otros = [o for o in por_cp.get(h["cp"], []) if o is not h]
        if h["lat"] is not None and otros:
            ref = (sorted(o["lat"] for o in otros)[len(otros) // 2], sorted(o["lon"] for o in otros)[len(otros) // 2])
            h["cp_ref"] = ref
            if km((h["lat"], h["lon"]), ref) > 2:
                h["sospechoso"] = True
    if a.verificar_poi:
        verificar_poi(regs)
    for h in regs:                                     # correcciones manuales
        m = manual.get(h["id"])
        if m:
            if m["nombre"]: h["nombre"] = m["nombre"]
            if num(m["lat"].replace(",", ".")) is not None and num(m["lon"].replace(",", ".")) is not None:
                h["lat"], h["lon"] = num(m["lat"].replace(",", ".")), num(m["lon"].replace(",", ".")); h["fuente"] = "manual"

    por_rec = {}
    for h, g in zip(regs, grupos):
        for i in g: por_rec[i] = h
    antes_pts = {(round(num(c["lat"]), 3), round(num(c["lon"]), 3)) for c in centros
                 if str(c.get("activo")) == "1" and num(c.get("lat")) is not None}
    antes_nombres = len({norm_nombre(c["centro"]) for c in centros if str(c.get("activo")) == "1"})
    for c in centros:
        h = por_rec[idx[clave(c)]]
        c.setdefault("centro_original", c["centro"])
        c["hospital_id"] = h["id"]; c["centro"] = h["nombre"]; c["domicilio"] = h["domicilio"]
        c["localidad"] = h["localidad"]; c["cod_postal"] = h["cp"]
        c["lat"] = h["lat"] if h["lat"] is not None else ""; c["lon"] = h["lon"] if h["lon"] is not None else ""
        c["precision"] = h["precision"] or c.get("precision", "")
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")

    with open(D / "hospitales.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["hospital_id", "nombre", "domicilio", "cp", "localidad", "provincia", "ccaa", "lat", "lon",
                    "precision", "fuente_coord", "n_filas", "n_variantes", "dispersion_m", "variantes"])
        for h in sorted(regs, key=lambda x: (x["ccaa"], x["localidad"], x["nombre"])):
            w.writerow([h["id"], h["nombre"], h["domicilio"], h["cp"], h["localidad"], h["provincia"], h["ccaa"],
                        h["lat"] if h["lat"] is not None else "", h["lon"] if h["lon"] is not None else "",
                        h["precision"], h["fuente"], h["n_filas"], len(h["variantes"]), h["dispersion_m"],
                        " || ".join(h["variantes"])])
    if not (D / "hospitales_manual.csv").exists():
        with open(D / "hospitales_manual.csv", "w", encoding="utf-8-sig", newline="") as fh:
            csv.writer(fh, delimiter=";").writerow(["hospital_id", "nombre", "lat", "lon", "fusionar_con"])

    despues_pts = {(round(num(c["lat"]), 3), round(num(c["lon"]), 3)) for c in centros
                   if str(c.get("activo")) == "1" and num(c.get("lat")) is not None}
    abiertos = {c["hospital_id"] for c in centros if str(c.get("activo")) == "1"}
    print(f"Centros abiertos: {antes_nombres} nombres normalizados -> {len(abiertos)} hospitales | "
          f"puntos en el mapa: {len(antes_pts)} -> {len(despues_pts)}")
    print("\nFusiones por nombres DISTINTOS (revisa que sean el mismo hospital):")
    for h in regs:
        if h["nn_distintos"] > 1 and h["id"] in abiertos:
            print(f"  * {h['nombre']} ({h['localidad']})")
            for v in h["variantes"]: print(f"       - {v}")
    print("\nHospitales a >2 km de los demás de su código postal (coordenada sospechosa):")
    for h in regs:
        if h.get("sospechoso") and h["id"] in abiertos:
            print(f"  * {km((h['lat'], h['lon']), h['cp_ref']):4.1f} km | {h['id']} | fuente={h['fuente']}")
    print(f"\nHospitales cuyas variantes discrepan más de {UMBRAL_CONFLICTO_M} m (coordenada dudosa):")
    for h in sorted(regs, key=lambda x: -x["dispersion_m"]):
        if h["dispersion_m"] > UMBRAL_CONFLICTO_M and h["id"] in abiertos:
            print(f"  * {h['dispersion_m']:5d} m | {h['id']} | fuente={h['fuente']}")

if __name__ == "__main__":
    main()
