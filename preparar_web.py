#!/usr/bin/env python3
"""Genera web/data/ensayos.js a partir de datos/ensayos.json.
- Solo se publican ensayos con al menos un centro ABIERTO (activo=1) y geocodificado.
- Solo se incluyen los centros abiertos.
- No se publican nombres/teléfonos/correos de personas de contacto ni investigadores:
  la web remite a la ficha oficial del REEC para contactar."""
import json, datetime, re, html, csv
from enriquecer import nombre_estudio, es_nombre, limpia_titulo, partir_criterios, criterios_ctis, nct_de_ctis, criterios_ctgov, contenido_ctgov
from promotores import canon_detalle as _canon_prom_d
from investigadores import construir_mapa as _mapa_ip
from taxonomia import clasificar, meta_taxonomia, E as _E
from pathlib import Path
D = Path(__file__).parent
datos = json.loads((D / "datos/ensayos.json").read_text(encoding="utf-8"))
CAMPOS_CENTRO = ("hospital_id", "centro", "domicilio", "localidad", "cod_postal", "provincia", "ccaa", "servicio", "investigador", "lat", "lon", "precision")
por = {}
_estado_reec = {x["identificador"]: x.get("estado", "") for x in datos["ensayos"]}
_activos = {c["identificador"] for c in datos["centros"] if str(c.get("activo")) == "1"}
for c in datos["centros"]:
    # «Fin reclutamiento»: los centros que siguen con pacientes pueden figurar como no activos; si no hay ninguno activo se muestran todos
    ok = str(c.get("activo")) == "1" or (_estado_reec.get(c["identificador"]) == "Fin reclutamiento" and c["identificador"] not in _activos)
    if ok and c.get("lat") not in ("", None):
        por.setdefault(c["identificador"], []).append({k: c.get(k, "") for k in CAMPOS_CENTRO})
# Investigador principal por centro (dato público del REec). Poner False para no publicarlo.
PUBLICAR_INVESTIGADORES = True
_pares = [(c["investigador"], c["hospital_id"]) for cs in por.values() for c in cs]
IPMAP, _grupos_ip, IP_DUDAS = _mapa_ip(_pares)
for cs in por.values():
    for c in cs:
        _ip = IPMAP.get(c.pop("investigador"), "")
        if PUBLICAR_INVESTIGADORES and _ip:
            c["ip"] = _ip
PRIVADOS = {"contacto", "email_contacto", "telefono_contacto"}
# Estudios de seguimiento / extensión: figuran como "Reclutando" pero solo admiten a quien ya participó antes.
SEGUIMIENTO = re.compile(
    r"long[- ]term follow|long[- ]term extension|seguimiento a largo|largo plazo|extension study|"
    r"estudio (abierto )?de extensi|estudio de seguimiento|estudio (maestro )?de continuaci|"
    r"rollover|roll-over|tratamiento continuado|continued access|acceso continuado", re.I)
# Solo se publican los ensayos que la clasificación de hematología ha incluido
f_ids = D / "datos/ids_hematologia.json"
INCLUIR = set(json.loads(f_ids.read_text(encoding="utf-8"))["incluir"]) if f_ids.exists() else None
def desescapa(x):
    if isinstance(x, str):
        for _ in range(2):
            x = html.unescape(x)
        return x
    if isinstance(x, list):
        return [desescapa(i) for i in x]
    if isinstance(x, dict):
        return {k: desescapa(v) for k, v in x.items()}
    return x
# Nombres oficiales corregidos a mano: datos/nombres_manual.csv (identificador;nombre). Nombre vacío = sin nombre.
MANUAL = {}
fm = D / "datos/nombres_manual.csv"
if fm.exists():
    for r in csv.DictReader(open(fm, encoding="utf-8-sig"), delimiter=";"):
        if r.get("identificador"):
            MANUAL[r["identificador"].strip()] = (r.get("nombre") or "").strip()
MAPA_NCT = {}
fmn = D / "datos/mapa_nct.json"
if fmn.exists():
    MAPA_NCT = json.loads(fmn.read_text(encoding="utf-8"))
RECL_MANUAL = {}
_frm = D / "datos/reclutamiento_manual.csv"
if _frm.exists():
    for _r in csv.DictReader(_frm.open(encoding="utf-8-sig"), delimiter=";"):
        RECL_MANUAL[_r["identificador"].strip()] = _r["estado"].strip()
CLAS_MANUAL = {}
_fcm = D / "datos/clasificacion_manual.csv"
if _fcm.exists():
    for _r in csv.DictReader(_fcm.open(encoding="utf-8-sig"), delimiter=";"):
        CLAS_MANUAL[_r["identificador"].strip()] = [x.strip() for x in (_r.get("entidades") or "").split("|") if x.strip()]
CERRADOS = []
PROM_ORIGEN = {}
salida = []
for e in datos["ensayos"]:
    if INCLUIR is not None and e["identificador"] not in INCLUIR:
        continue
    cs = por.get(e["identificador"])
    if not cs:
        continue
    e = {k: v for k, v in e.items() if k not in PRIVADOS}
    e["centros"] = cs
    e.pop("subareas", None)
    raw = {}
    fr = D / "datos/raw" / (e["identificador"] + ".json")
    if fr.exists():
        raw = json.loads(fr.read_text(encoding="utf-8"))
    inf = raw.get("informacion", {})
    ac = (raw.get("acronimo") or "").strip()
    ct = None
    nct0 = (MAPA_NCT.get(e["identificador"]) or {}).get("nct")
    fct = D / "datos/raw_ctgov" / ((nct0 or "x") + ".json")
    if nct0 and fct.exists():
        ct = contenido_ctgov(json.loads(fct.read_text(encoding="utf-8")))
    nombre = MANUAL.get(e["identificador"])
    e["nombre_fuente"] = "manual"
    if nombre is None and ct and ct["acronimo"]:
        nombre = ct["acronimo"]; e["nombre_fuente"] = "ctgov"
    if nombre is None:
        e["nombre_fuente"] = "reec" if es_nombre(ac) else "detectado"
        nombre = ac if es_nombre(ac) else nombre_estudio(inf.get("tituloPublico"), inf.get("tituloCientifico"), raw.get("protocolo"))
    org = raw.get("organismo") or {}
    _tel = re.sub(r"\s+", " ", str(org.get("telefono") or "")).strip()
    _dom = re.sub(r"\s+", " ", str(org.get("domicilio") or "")).strip()
    _dig = re.sub(r"\D", "", _tel)
    _es = bool(re.search(r"espa[nñ]a|spain|madrid|barcelona|valencia|sevilla|m[aá]laga|bilbao|zaragoza|alcobendas|sant cugat|las rozas|pozuelo|tres cantos|getafe|alcal[aá] de henares|\b(0[1-9]|[1-4]\d|5[0-2])\d{3}\b", _dom, re.I)
               or _tel.startswith(("+34", "0034", "34 ")) or (not _tel.startswith("+") and len(_dig) == 9 and _dig[0] in "6789"))
    e["contacto"] = {"dom": _dom, "tel": _tel, "mail": str(org.get("mail") or "").strip(), "persona": re.sub(r"\s+", " ", str(org.get("personaContacto") or "")).strip(), "es": _es}
    e["protocolo"] = re.sub(r"\s+", " ", (raw.get("protocolo") or "")).strip()
    e["nombre_tipo"] = "nombre"
    if not nombre and 2 <= len(e["protocolo"]) <= 40 and e["protocolo"].upper() not in ("NA", "N/A", "NO APLICA", "-"):
        nombre, e["nombre_tipo"] = e["protocolo"], "protocolo"      # sin nombre oficial: va delante el código de protocolo
    e["nombre"] = nombre
    e["titulo"] = limpia_titulo(e.get("titulo", ""), nombre)
    inc = partir_criterios(inf.get("criteriosInclusion") or inf.get("criteriosInclusion_en") or e.get("criterios_inclusion"))
    exc = partir_criterios(inf.get("criteriosExclusion") or inf.get("criteriosExclusion_en") or e.get("criterios_exclusion"))
    fuente = "REec"
    if ct and (ct["inc"] or ct["exc"]):                        # ClinicalTrials.gov primero: criterios mejor estructurados
        inc, exc, fuente = ct["inc"], ct["exc"], "ClinicalTrials.gov"
    if ct:
        e["nct"] = ct["nct"]
        e["resumen"], e["elegibilidad"], e["diseno"], e["brazos"], e["objetivos"], e["n_secundarios"] = (
            ct["resumen"], ct["elegibilidad"], ct["diseno"], ct["brazos"], ct["objetivos"], ct["n_secundarios"])
    fc = D / "datos/raw_ctis" / (e["identificador"] + ".json")
    if not inc and not exc and fc.exists():                    # ni ClinicalTrials.gov ni el REec los tienen: se toman de CTIS (criterios principales)
        inc, exc = criterios_ctis(json.loads(fc.read_text(encoding="utf-8")))
        fuente = "CTIS"
    if not inc and not exc and fc.exists():                    # tampoco en CTIS: ClinicalTrials.gov, por el NCT que indica CTIS
        nct = nct_de_ctis(json.loads(fc.read_text(encoding="utf-8")))
        fg = D / "datos/raw_ctgov" / (nct + ".json")
        if nct and fg.exists():
            inc, exc = criterios_ctgov(json.loads(fg.read_text(encoding="utf-8")))
            fuente = "ClinicalTrials.gov"
            e["nct"] = nct
    e["criterios"] = {"inc": inc, "exc": exc, "fuente": fuente}
    e["promotor_c"], e["promotor_t"], _pori = _canon_prom_d(e.get("promotor"))
    PROM_ORIGEN.setdefault(e["promotor_c"], {"t": e["promotor_t"], "o": _pori, "v": set()})["v"].add(e.get("promotor") or "")
    # --- ¿Sigue reclutando? Se cruzan REec (fechas), CTIS (estado y eventos en España) y ClinicalTrials.gov ---
    _firme, _suave = [], []
    _cal = raw.get("calendario") or {}
    for _k, _t in (("fechaFinRealEspana", "fin en España"), ("fechaFinRealGlobal", "fin global"), ("fechaFinPrematuro", "fin prematuro")):
        if _cal.get(_k):
            _firme.append(f"REec: {_t} el {_cal[_k]}")
    if _cal.get("fechaInterrupcion") and not _cal.get("fechaReinicio"):
        _firme.append(f"REec: interrumpido el {_cal['fechaInterrupcion']}")
    _fci = D / "datos/raw_ctis" / (e["identificador"] + ".json")
    if _fci.exists():
        _j = json.loads(_fci.read_text(encoding="utf-8"))
        if str(_j.get("ctStatus", "")).lower() in ("ended", "terminated", "revoked", "withdrawn"):
            _firme.append("CTIS: ensayo finalizado (" + str(_j.get("ctStatus")) + ")")
        for _m in ((_j.get("events") or {}).get("trialEvents") or []):
            if "spain" not in str(_m.get("mscName", "")).lower() and "espa" not in str(_m.get("mscName", "")).lower():
                continue
            _ev = _m.get("events") or []
            _fin = [x for x in _ev if re.search(r"END_OF_TRIAL|EARLY_TERM", str(x.get("notificationType", "")))]
            _rec = [x for x in _ev if re.search(r"END_OF_RECRUITMENT", str(x.get("notificationType", "")))]
            _hlt = [x for x in _ev if re.search(r"TEMPORARY_HALT", str(x.get("notificationType", "")))]
            _rei = [x for x in _ev if re.search(r"RESTART", str(x.get("notificationType", "")))]
            if _fin and not _rei:
                _firme.append("CTIS: " + _fin[-1]["notificationType"].lower().replace("_", " ") + " en España (" + str(_fin[-1].get("date", "")) + ")")
            elif _rec and not _rei:
                _suave.append("CTIS: fin de reclutamiento sin reclutar en España (" + str(_rec[-1].get("date", "")) + ")")
            if _hlt and not _rei:
                _suave.append("CTIS: parada temporal en España (" + str(_hlt[-1].get("date", "")) + ")")
        if (_j.get("events") or {}).get("temporaryHaltList"):
            _suave.append("CTIS: parada temporal registrada")
    if fct.exists():
        _st = json.loads(fct.read_text(encoding="utf-8"))["protocolSection"]["statusModule"].get("overallStatus", "")
        if _st in ("TERMINATED", "COMPLETED", "WITHDRAWN", "SUSPENDED"):
            _firme.append("ClinicalTrials.gov: " + _st)
        elif _st == "ACTIVE_NOT_RECRUITING":
            _suave.append("ClinicalTrials.gov: «activo, sin reclutar»")
        elif _st == "UNKNOWN":
            _suave.append("ClinicalTrials.gov: estado sin verificar desde hace tiempo")
    if e.get("estado") == "Fin reclutamiento":
        _suave.append("REec: estado «Fin reclutamiento» (sin reclutar)")
    _est = "cerrado" if _firme else ("no_recluta" if any("sin reclutar" in x or "parada" in x for x in _suave) else ("dudoso" if _suave else "abierto"))
    _est = RECL_MANUAL.get(e["identificador"], _est)
    e["_recl"] = (_est, _firme + _suave)
    if _est in ("no_recluta", "dudoso"):
        e["reclutamiento"] = {"estado": _est, "motivos": _firme + _suave}
    e.pop("criterios_inclusion", None); e.pop("criterios_exclusion", None)
    if not inc and not exc and re.match(r"^\d{4}-\d{6}-\d{2}-\d{2}$", e["identificador"]):
        e["ctis"] = "https://euclinicaltrials.eu/search-for-clinical-trials/?lang=en&EUCT=" + e["identificador"]
    e["entidades"] = clasificar(e.get("titulo"), e.get("indicacion"), e.get("titulo_cientifico"))
    # Si el registro solo indica la enfermedad en general (p. ej. «leucemia aguda»), los criterios de inclusión
    # concretan a qué pacientes se dirige: se sustituye el genérico por lo que citan los criterios.
    _ops = {x[0]: x[5] for x in _E}
    _neo = {x[0] for x in _E if x[1] in ("nmp", "masto", "smd", "lma", "lla", "bmad", "hodgkin", "tnk", "pc", "inm", "hist")}
    gen = [i for i in e["entidades"] if _ops.get(i, {}).get("cubre")]
    if gen and inc:
        en_inc = set(clasificar(" ".join(l[2:] if l.startswith("§ ") else l for l in inc))) - {"sin"}
        for g in gen:
            cub = _ops[g]["cubre"]
            cub = (_neo - {g, "hem_malig", "lpa"}) if cub == ["*"] else set(cub)
            hits = (en_inc & cub) - {g}
            if hits:
                e["entidades"] = [i for i in e["entidades"] if i != g] + [h for h in sorted(hits) if h not in e["entidades"]]
                e["entidades_por_criterios"] = True
        orden = [x[0] for x in _E]
        e["entidades"] = sorted(set(e["entidades"]), key=orden.index)
    e["seguimiento"] = bool(SEGUIMIENTO.search(e.get("titulo", "") or ""))
    if e["identificador"] in CLAS_MANUAL:                       # corrección manual de la clasificación (datos/clasificacion_manual.csv)
        _ok = {x[0] for x in _E}
        e["entidades"] = [i for i in CLAS_MANUAL[e["identificador"]] if i in _ok] or ["sin"]
        e["entidades_manual"] = True
    _est, _mot = e.pop("_recl")
    if _est == "cerrado":
        CERRADOS.append((e["identificador"], e.get("nombre") or e.get("protocolo") or "", "cerrado", " | ".join(_mot), e.get("titulo", "")))
        continue
    if _est != "abierto":
        CERRADOS.append((e["identificador"], e.get("nombre") or e.get("protocolo") or "", _est, " | ".join(_mot), e.get("titulo", "")))
    salida.append(desescapa(e))
meta = {"taxonomia": meta_taxonomia(), "generado": datetime.date.today().isoformat(),
        "total_hematologia": len(datos["ensayos"]), "mostrados": len(salida),
        "seguimiento": sum(1 for x in salida if x["seguimiento"])}
js = "window.DATOS = " + json.dumps({"meta": meta, "ensayos": salida}, ensure_ascii=False) + ";\n"
(D / "web/data/ensayos.js").write_text(js, encoding="utf-8")
print(f"{len(salida)} de {len(datos['ensayos'])} ensayos tienen centros abiertos con ubicación -> web/data/ensayos.js")

# Informe para revisión por el hematólogo: qué entidades se ha asignado a cada ensayo
et = {x[0]: x[2] for x in _E}
with open(D / "datos/clasificacion_oms.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["identificador", "entidades", "titulo", "indicacion_REEC"])
    for x in salida:
        w.writerow([x["identificador"], " | ".join(et[i] for i in x["entidades"]), x.get("titulo", ""), x.get("indicacion", "")])
print("Revisión de la clasificación -> datos/clasificacion_oms.csv")

with open(D / "datos/nombres_propuestos.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f, delimiter=";"); w.writerow(["identificador", "nombre", "tipo", "protocolo", "titulo"])
    for x in salida:
        w.writerow([x["identificador"], x["nombre"], x["nombre_tipo"], x["protocolo"], x.get("titulo", "")])
sin = [x for x in salida if not x["criterios"]["inc"] and not x["criterios"]["exc"]]
print(f"Nombre oficial en {sum(1 for x in salida if x['nombre_tipo'] == 'nombre' and x['nombre'])}, código de protocolo en {sum(1 for x in salida if x['nombre_tipo'] == 'protocolo')} de {len(salida)} ensayos -> datos/nombres_propuestos.csv")
print(f"Criterios recogidos en {len(salida) - len(sin)} de {len(salida)} ({sum(1 for x in salida if x['criterios']['fuente'] == 'CTIS' and x['criterios']['inc'])} desde CTIS, {sum(1 for x in salida if x['criterios']['fuente'] == 'ClinicalTrials.gov' and x['criterios']['inc'])} desde ClinicalTrials.gov); {len(sin)} sin criterios (se enlaza a CTIS)")

# Informe de promotores unificados (revisar y corregir en datos/promotores_manual.csv: promotor;canonico;tipo)
import collections as _c
_g = _c.defaultdict(set)
for _e in salida:
    _g[(_e["promotor_c"], _e["promotor_t"])].add(_e.get("promotor") or "")
with open(D / "datos/promotores_unificados.csv", "w", encoding="utf-8-sig", newline="") as _f:
    _w = csv.writer(_f, delimiter=";"); _w.writerow(["canonico", "tipo", "n_ensayos", "nombres_en_REec"])
    for (_c1, _t1), _v in sorted(_g.items(), key=lambda x: -sum(1 for _e in salida if _e["promotor_c"] == x[0][0])):
        _w.writerow([_c1, _t1, sum(1 for _e in salida if _e["promotor_c"] == _c1), " | ".join(sorted(_v))])
print("Promotores unificados ->", "datos/promotores_unificados.csv")

# Informe de estado de reclutamiento. Para forzar un estado: datos/reclutamiento_manual.csv (identificador;estado = abierto|cerrado|no_recluta)
with open(D / "datos/reclutamiento_revision.csv", "w", encoding="utf-8-sig", newline="") as _f:
    _w = csv.writer(_f, delimiter=";"); _w.writerow(["identificador", "nombre", "estado", "motivos", "titulo"])
    for _x in sorted(CERRADOS, key=lambda x: (x[2], x[0])): _w.writerow(_x)
print("Reclutamiento: %d retirados por cierre firme, %d marcados como «ya no recluta»/dudosos -> datos/reclutamiento_revision.csv" % (
    sum(1 for x in CERRADOS if x[2] == "cerrado"), sum(1 for x in CERRADOS if x[2] != "cerrado")))

# Informe de investigadores unificados: revisa las fusiones y corrige en datos/investigadores_manual.csv (variante;canonico)
_cnt = {}
for _e in salida:
    for _c in _e["centros"]:
        if _c.get("ip"):
            _cnt.setdefault(_c["ip"], {"e": set(), "h": set()})
            _cnt[_c["ip"]]["e"].add(_e["identificador"]); _cnt[_c["ip"]]["h"].add(_c["centro"])
with open(D / "datos/investigadores_unificados.csv", "w", encoding="utf-8-sig", newline="") as _f:
    _w = csv.writer(_f, delimiter=";"); _w.writerow(["investigador", "n_ensayos", "centros", "variantes_unificadas"])
    for _n, _v in sorted(_cnt.items(), key=lambda x: -len(x[1]["e"])):
        _vs = sorted({x for x in next((g for g in _grupos_ip.values() if _n in g), [_n]) if x != _n})
        _w.writerow([_n, len(_v["e"]), " | ".join(sorted(_v["h"])), " | ".join(_vs)])
print("Investigadores principales: %d distintos -> datos/investigadores_unificados.csv" % len(_cnt))

# Dudas que lee revision.py
import dataclasses as _dc
(D / "datos/dudas.json").write_text(json.dumps({
    "promotores": [{"canonico": k, "tipo": v["t"], "origen": v["o"], "variantes": sorted(v["v"])} for k, v in PROM_ORIGEN.items()],
    "investigadores": IP_DUDAS}, ensure_ascii=False, indent=1), encoding="utf-8")
