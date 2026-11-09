#!/usr/bin/env python3
"""Utilidades para preparar_web.py:
 - nombre_estudio(): detecta el nombre «oficial» del ensayo (RAFTING-2019, OLYMPIA-3…) y limpia el título
 - partir_criterios(): convierte el texto de criterios de inclusión/exclusión del REEC en una lista de puntos
Las propuestas de nombre se pueden corregir a mano en datos/nombres_manual.csv (identificador;nombre)."""
import re, html

# --- nombre oficial -------------------------------------------------------------
_CODIGO = re.compile(r"^[A-Za-z]{1,5}[- ]?\d{3,}[A-Za-z0-9\-/]*$")              # INCB039110, APG-2575, MK-2140-010
_PALABRAS_NO = {"GENETICALLY", "MODIFIED", "CELLS", "STUDY", "PHASE", "TRIAL", "SAFETY", "EFFICACY", "RANDOMIZED",
                "RANDOMISED", "OPEN", "LABEL", "DOUBLE", "BLIND", "PLACEBO", "CONTROLLED", "MULTICENTER", "MULTICENTRE"}
_SIGLAS = {"AML", "CLL", "SLL", "MDS", "NHL", "DLBCL", "ASCT", "AHSCT", "TMLI", "HMA", "CMML", "ITP", "FIH", "LTFU", "CART",
           "BCMA", "GVHD", "HSCT", "PCNSL", "NPM1", "FLT3", "KMT2A"}


_TERMINOS = {"lymphoma", "leukemia", "leukaemia", "cell", "cells", "antibody", "events", "oral", "antagonista", "amiloidosis", "estudio",
             "ensayo", "venetoclax", "azacitidine", "azacitidina", "hodgkin", "lymphoid", "myeloma", "mieloma", "linfoma", "leucemia",
             "large", "b-cell", "t-cell", "related", "plus", "antigen", "bispecific", "inhibitor", "inhibidor", "study", "trial"}
_SIGLAS_SUBCAD = ("GVHD", "EICH", "EICR", "AIHA", "ITP")


def es_nombre(s, protocolo=False):
    s = (s or "").strip().strip("()[]\"'.,;: ")
    if not re.fullmatch(r"[A-Za-z0-9\-_/. ]+", s or "x!"):                   # sin «+», paréntesis ni símbolos raros
        return False
    if any(p.lower() in _TERMINOS for p in re.split(r"[\s/_]", s)):
        return False
    if any(x in s.upper() for x in _SIGLAS_SUBCAD):
        return False
    if re.fullmatch(r"[A-Za-z]+(mab|nib|ciclib|clax|stat|tinib|degib|limab)", s, flags=re.I):
        return False                                                      # nombre de fármaco
    if protocolo:                                                         # un protocolo solo vale si parece un nombre, no un código
        if sum(c.isdigit() for c in s) > 4 or s.count("-") > 1 or re.search(r"[A-Za-z]{4,}\d{3,}", s):
            return False
    if not (4 <= len(s) <= 28):
        return False
    if " " in s:
        partes = s.split()
        if len(partes) > 3 or any(len(p) > 8 for p in partes[1:]):
            return False
    if any(p.upper() in _PALABRAS_NO for p in re.split(r"[\s\-/_]", s)):
        return False
    if _CODIGO.match(s):
        return False
    if not s[0].isalpha() or s.islower():
        return False
    if sum(c.isupper() for c in s) < 2:                                    # «Lisaftoclax» no es un acrónimo
        return False
    if s.upper() in _SIGLAS:
        return False
    return max((len(x) for x in re.findall(r"[A-Za-z]+", s)), default=0) >= 5   # alguna palabra de ≥5 letras


def candidatos(tit_pub, tit_cie, protocolo):
    tp, tc = html.unescape(tit_pub or "").strip(), html.unescape(tit_cie or "").strip()
    out = []
    for t in (tc, tp):                                                     # (NOMBRE) en el título
        out += re.findall(r"\(([^()]{3,30})\)", t)
    for t in (tp, tc):                                                     # «NOMBRE: …» al principio
        m = re.match(r"^([A-Za-z][A-Za-z0-9\-_]{3,24})\s*[:：]\s", t)
        if m: out.append(m.group(1))
        m = re.match(r"^[A-Za-z0-9\-_/.]{4,24}\s+-\s+([A-Z][A-Za-z0-9\-]{4,24})\s", t)   # «C1071032 - MAGNETISMM-32 …»
        if m: out.append(m.group(1))
    for t in (tp, tc):                                                     # «… - NOMBRE» al final
        m = re.search(r"[\-–—:]\s*([A-Za-z][A-Za-z0-9\-_/]{3,24})\s*\.?$", t)
        if m: out.append(m.group(1))
    return out


def nombre_estudio(tit_pub, tit_cie, protocolo):
    for c in candidatos(tit_pub, tit_cie, protocolo):
        if es_nombre(c):
            return c.strip().strip("()[]\"'.,;: ")
    if es_nombre(protocolo, protocolo=True):                               # a veces el protocolo ya es el nombre (PLATO, PATROL)
        return protocolo.strip()
    return ""


def limpia_titulo(titulo, nombre):
    """Quita del título el nombre cuando ya va delante («RAFTING-2019 ·») para no repetirlo."""
    if not nombre or not titulo:
        return titulo
    t = titulo.strip()
    for n in dict.fromkeys([nombre, re.sub(r"[-_ ]?\d+$", "", nombre), nombre.split()[0]]):
        if len(n) < 4: continue
        t = re.sub(r"^\S{4,24}\s+-\s+" + re.escape(n) + r"\s+", "", t, flags=re.I)      # «C1071032 - NOMBRE Estudio…»
        t2 = re.sub(r"^\s*" + re.escape(n) + r"\s*[:：\-–]\s*", "", t, flags=re.I)
        t2 = re.sub(r"\s*[\-–—:(]\s*" + re.escape(n) + r"[\s\-0-9]*\)?\s*\.?$", "", t2, flags=re.I)
        if t2 != t and len(t2) > 15:
            t = t2
    return t


# --- criterios --------------------------------------------------------------------
_VIÑETA = re.compile(r"^\s*(?:[\-•·▪●■◦*–—]+|\(?\d{1,2}[\.\)]|\(?[a-zA-Z][\.\)]|\(?[ivx]{1,4}[\.\)])\s+")


def partir_criterios(txt):
    """Texto del REEC (con <br/>, entidades HTML…) -> lista de criterios. Los encabezados llevan el prefijo «§ »."""
    t = txt or ""
    # 1) etiquetas HTML reales (antes de decodificar, para no confundir «< 2,0 x LSN» con una etiqueta)
    t = re.sub(r"(?i)<\s*br\s*/?\s*>|</?\s*p\s*/?>|</?\s*li\s*>|</?\s*ul\s*>|</?\s*div\s*>|\r", "\n", t)
    t = re.sub(r"(?i)</?\s*(?:b|i|u|strong|em|span|font|ol|sup|sub|table|tr|td|th|a)\b[^<>]*>", "", t)
    t = html.unescape(html.unescape(t)).replace("\xa0", " ")
    lineas = [re.sub(r"[ \t]+", " ", l).strip() for l in t.split("\n")]
    lineas = [l for l in lineas if l]
    if len(lineas) <= 2 and len(t) > 350:                                  # todo en un bloque numerado: «1. … 2. … 3. …»
        trozos = re.split(r"\s(?=\(?\d{1,2}[\.\)]\s+[A-ZÁÉÍÓÚÑ¿a-z])", " ".join(lineas))
        if len(trozos) >= 3:
            lineas = [x.strip() for x in trozos if x.strip()]
    items = []
    for l in lineas:
        cont = bool(items) and l[:1].islower() and not _VIÑETA.match(l) and not re.search(r"[.;:]$", items[-1])
        l = _VIÑETA.sub("", l, count=1).strip()
        if not l:
            continue
        if cont and not items[-1].startswith("§ "):
            items[-1] += " " + l                                           # línea que continúa la anterior
        elif l.endswith(":") and len(l) <= 90:
            items.append("§ " + l.rstrip(":"))
        else:
            items.append(l)
    return items


def _textos(nodo):
    """Saca los textos de un nodo de CTIS (lista de dicts, lista de str o str)."""
    out = []
    if isinstance(nodo, str):
        out.append(nodo)
    elif isinstance(nodo, list):
        for x in nodo:
            out += _textos(x)
    elif isinstance(nodo, dict):
        claves = [k for k in nodo if "riteri" in k and "ranslation" not in k]
        if claves:
            for k in claves:
                out += _textos(nodo[k])
        else:
            for k, v in nodo.items():
                if isinstance(v, str) and k not in ("number", "id", "uuid", "language", "languageDescription") and len(v) > 3:
                    out.append(v)
    return out


def _buscar(o, clave):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == clave:
                return v
            r = _buscar(v, clave)
            if r is not None:
                return r
    elif isinstance(o, list):
        for x in o:
            r = _buscar(x, clave)
            if r is not None:
                return r
    return None


def criterios_ctis(js):
    """JSON de CTIS -> (inclusión, exclusión) como listas de puntos (criterios principales)."""
    res = []
    for clave in ("principalInclusionCriteria", "principalExclusionCriteria"):
        textos = _textos(_buscar(js, clave))
        puntos = []
        for t in textos:
            puntos += partir_criterios(t)
        res.append(puntos)
    return res[0], res[1]


def nct_de_ctis(js):
    """Número NCT (ClinicalTrials.gov) que figura en el registro de CTIS, si hay uno inequívoco."""
    n = _buscar(js, "nctNumber")
    if isinstance(n, dict):
        n = n.get("number")
    if isinstance(n, str) and re.fullmatch(r"NCT\d{8}", n.strip()):
        return n.strip()
    return ""


def criterios_ctgov(js):
    """JSON de la API v2 de ClinicalTrials.gov -> (inclusión, exclusión)."""
    txt = ((js.get("protocolSection") or {}).get("eligibilityModule") or {}).get("eligibilityCriteria") or ""
    txt = txt.replace("\r", "")
    m = re.search(r"(?im)^\s*\W*\s*exclusion criteria\s*:?\s*$", txt)
    if m:
        inc_t, exc_t = txt[:m.start()], txt[m.end():]
    else:
        inc_t, exc_t = txt, ""
    inc_t = re.sub(r"(?im)^\s*\W*\s*inclusion criteria\s*:?\s*$", "", inc_t)
    return partir_criterios(inc_t), partir_criterios(exc_t)


# --- contenido de ClinicalTrials.gov ------------------------------------------------
_ES = {
    "RANDOMIZED": "Aleatorizado", "NON_RANDOMIZED": "No aleatorizado", "NA": "No aplica",
    "SINGLE_GROUP": "Un solo grupo", "PARALLEL": "Grupos paralelos", "CROSSOVER": "Cruzado", "SEQUENTIAL": "Secuencial", "FACTORIAL": "Factorial",
    "NONE": "Abierto (sin enmascaramiento)", "SINGLE": "Simple ciego", "DOUBLE": "Doble ciego", "TRIPLE": "Triple ciego", "QUADRUPLE": "Cuádruple ciego",
    "TREATMENT": "Tratamiento", "PREVENTION": "Prevención", "SUPPORTIVE_CARE": "Cuidados de soporte", "DIAGNOSTIC": "Diagnóstico",
    "BASIC_SCIENCE": "Ciencia básica", "HEALTH_SERVICES_RESEARCH": "Servicios sanitarios", "SCREENING": "Cribado", "OTHER": "Otro",
    "EXPERIMENTAL": "Experimental", "ACTIVE_COMPARATOR": "Comparador activo", "PLACEBO_COMPARATOR": "Placebo", "SHAM_COMPARATOR": "Simulación",
    "NO_INTERVENTION": "Sin intervención",
    "ALL": "Ambos sexos", "FEMALE": "Solo mujeres", "MALE": "Solo hombres",
    "INTERVENTIONAL": "Intervencionista", "OBSERVATIONAL": "Observacional", "EXPANDED_ACCESS": "Acceso expandido",
}
_UNID = {"year": "año", "years": "años", "month": "mes", "months": "meses", "week": "semana", "weeks": "semanas", "day": "día", "days": "días"}


def _es(x):
    return _ES.get(str(x or ""), str(x or "").replace("_", " ").capitalize()) if x else ""


def _edad(s):
    m = re.match(r"^\s*(\d+)\s*([A-Za-z]+)", s or "")
    return f"{m.group(1)} {_UNID.get(m.group(2).lower(), m.group(2).lower())}" if m else ""


def _corta(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def contenido_ctgov(st):
    """Estudio de ClinicalTrials.gov (API v2) -> dict con lo que muestra la web."""
    p = st.get("protocolSection") or {}
    ident = p.get("identificationModule") or {}
    des = p.get("designModule") or {}
    di = des.get("designInfo") or {}
    el = p.get("eligibilityModule") or {}
    inc, exc = criterios_ctgov(st)
    fases = [("Fase " + f.replace("PHASE", "").replace("/", "/")) if f.startswith("PHASE") else _es(f) for f in (des.get("phases") or []) if f != "NA"]
    arms = (p.get("armsInterventionsModule") or {}).get("armGroups") or []
    outc = p.get("outcomesModule") or {}
    return {
        "nct": ident.get("nctId", ""),
        "acronimo": (ident.get("acronym") or "").strip(),
        "resumen": _corta((p.get("descriptionModule") or {}).get("briefSummary"), 1500),
        "inc": inc, "exc": exc,
        "elegibilidad": {"sexo": _es(el.get("sex")), "edad_min": _edad(el.get("minimumAge")), "edad_max": _edad(el.get("maximumAge")),
                         "voluntarios_sanos": {True: "Sí", False: "No"}.get(el.get("healthyVolunteers"), "")},
        "diseno": {"tipo": _es(des.get("studyType")), "fases": " / ".join(fases), "asignacion": _es(di.get("allocation")),
                   "modelo": _es(di.get("interventionModel")), "proposito": _es(di.get("primaryPurpose")),
                   "enmascaramiento": _es((di.get("maskingInfo") or {}).get("masking")), "n": (des.get("enrollmentInfo") or {}).get("count")},
        "brazos": [{"n": a.get("label", ""), "t": _es(a.get("type")), "d": _corta(a.get("description"), 450),
                    "i": a.get("interventionNames") or []} for a in arms[:8]],
        "objetivos": [{"m": _corta(o.get("measure"), 260), "p": _corta(o.get("timeFrame"), 80)} for o in (outc.get("primaryOutcomes") or [])[:6]],
        "n_secundarios": len(outc.get("secondaryOutcomes") or []),
    }
