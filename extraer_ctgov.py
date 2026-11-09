#!/usr/bin/env python3
"""ClinicalTrials.gov (API pública v2) como fuente principal del CONTENIDO de cada ensayo: criterios de inclusión/exclusión,
diseño, brazos, objetivos y acrónimo oficial. El REec sigue siendo la fuente de qué ensayos/centros están abiertos en España.

Cruce REec -> NCT (en este orden, verificando siempre que el estudio devuelto lleva ese identificador):
  1) el número europeo (EU CT / EudraCT) como «otro identificador» del estudio en ClinicalTrials.gov
  2) el NCT que indica CTIS (datos/raw_ctis, si lo descargaste con extraer_ctis.py)
  3) el código de protocolo del promotor

Uso (PowerShell, con internet):
    python extraer_ctgov.py                 # cruza y descarga lo que falte (se puede interrumpir y reanudar)
    python extraer_ctgov.py --reintentar    # vuelve a buscar los que no se encontraron
    python extraer_ctgov.py --forzar        # descarga todo de nuevo
    python extraer_ctgov.py --descubrir     # además, lista estudios con centros en España que NO están en tu lista del REec
Después:  python preparar_web.py"""
import csv, json, re, sys, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path
from enriquecer import nct_de_ctis
D = Path(__file__).parent
OUT = D / "datos/raw_ctgov"; OUT.mkdir(exist_ok=True)
MAPA_F = D / "datos/mapa_nct.json"
BASE = "https://clinicaltrials.gov/api/v2/studies"


def get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "ensayos-hematologia-web (uso academico)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def norm_id(s):
    s = re.sub(r"\s+", "", str(s or "")).upper()
    return re.sub(r"^(\d{4}-\d{6}-\d{2})-\d{2}$", r"\1", s)          # 2022-502514-86-00 == 2022-502514-86


def ids_estudio(st):
    ip = (st.get("protocolSection") or {}).get("identificationModule") or {}
    out = {norm_id((ip.get("orgStudyIdInfo") or {}).get("id"))}
    for s in ip.get("secondaryIdInfos") or []:
        out.add(norm_id(s.get("id")))
    return out


def buscar(term, objetivo):
    url = f"{BASE}?query.term={urllib.parse.quote(term)}&pageSize=10&format=json"
    for st in get(url).get("studies", []):
        if norm_id(objetivo) in ids_estudio(st):
            return st
    return None


def por_nct(nct):
    try:
        return get(f"{BASE}/{nct}?format=json")
    except urllib.error.HTTPError:
        return None


def guardar(st):
    nct = st["protocolSection"]["identificationModule"]["nctId"]
    (OUT / f"{nct}.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    return nct


ids = json.loads((D / "datos/ids_hematologia.json").read_text(encoding="utf-8"))["incluir"]
mapa = json.loads(MAPA_F.read_text(encoding="utf-8")) if MAPA_F.exists() and "--forzar" not in sys.argv else {}
print(f"{len(ids)} ensayos del REec; {len(mapa)} ya cruzados")
nuevos = 0
for n, i in enumerate(ids, 1):
    if i in mapa and (mapa[i].get("nct") or "--reintentar" not in sys.argv):
        continue
    raw = {}
    f = D / "datos/raw" / f"{i}.json"
    if f.exists():
        raw = json.loads(f.read_text(encoding="utf-8"))
    prot = re.sub(r"\s+", " ", raw.get("protocolo") or "").strip()
    st, via = None, ""
    try:
        for term in dict.fromkeys([i, norm_id(i)]):
            st = buscar(term, i)
            if st: via = "id europeo"; break
            time.sleep(0.4)
        if not st:
            fc = D / "datos/raw_ctis" / f"{i}.json"
            nct = nct_de_ctis(json.loads(fc.read_text(encoding="utf-8"))) if fc.exists() else ""
            if nct:
                st = por_nct(nct); via = "NCT de CTIS" if st else ""
        if not st and len(prot) >= 5 and prot.upper() not in ("NA", "N/A"):
            st = buscar(prot, prot); via = "protocolo" if st else ""
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  [{n}/{len(ids)}] {i}: ERROR de red ({e}); se reintentará la próxima vez"); continue
    if st:
        nct = guardar(st); mapa[i] = {"nct": nct, "via": via}; nuevos += 1
        ac = (st["protocolSection"]["identificationModule"].get("acronym") or "")
        print(f"  [{n}/{len(ids)}] {i} -> {nct} ({via}) {ac}")
    else:
        mapa[i] = {"nct": "", "via": ""}
        print(f"  [{n}/{len(ids)}] {i}: no está en ClinicalTrials.gov")
    MAPA_F.write_text(json.dumps(mapa, ensure_ascii=False, indent=1), encoding="utf-8")
    time.sleep(0.6)
MAPA_F.write_text(json.dumps(mapa, ensure_ascii=False, indent=1), encoding="utf-8")
con = [i for i in ids if mapa.get(i, {}).get("nct")]
print(f"\nCruzados con ClinicalTrials.gov: {len(con)} de {len(ids)} (nuevos en esta ejecución: {nuevos})")

# Centros en España según ClinicalTrials.gov, para contrastar con el REec
with open(D / "datos/ctgov_sitios_espana.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.writer(fh, delimiter=";"); w.writerow(["identificador_reec", "nct", "centro", "ciudad", "estado_ctgov"])
    for i in con:
        st = json.loads((OUT / f"{mapa[i]['nct']}.json").read_text(encoding="utf-8"))
        for l in ((st.get("protocolSection") or {}).get("contactsLocationsModule") or {}).get("locations", []):
            if l.get("country") == "Spain":
                w.writerow([i, mapa[i]["nct"], l.get("facility", ""), l.get("city", ""), l.get("status", "")])
print("Centros españoles según ClinicalTrials.gov -> datos/ctgov_sitios_espana.csv")

if "--descubrir" in sys.argv:
    conocidos = {v["nct"] for v in mapa.values() if v.get("nct")}
    TERMINOS = ["leukemia", "lymphoma", "multiple myeloma", "myelodysplastic", "myeloproliferative", "myelofibrosis", "amyloidosis",
                "hemophilia", "thrombocytopenia", "anemia", "sickle cell", "thalassemia", "graft versus host", "hematopoietic stem cell transplant",
                "paroxysmal nocturnal hemoglobinuria", "mastocytosis", "von Willebrand", "aplastic anemia", "hemophagocytic"]
    vistos = {}
    for t in TERMINOS:
        tok = ""
        while True:
            q = {"query.cond": t, "query.locn": "Spain", "filter.overallStatus": "RECRUITING|NOT_YET_RECRUITING|ENROLLING_BY_INVITATION",
                 "pageSize": 200, "format": "json", "fields": "NCTId|BriefTitle|Condition|OverallStatus|LocationFacility|LocationCity|LocationCountry|SecondaryId"}
            if tok: q["pageToken"] = tok
            try:
                r = get(BASE + "?" + urllib.parse.urlencode(q))
            except (urllib.error.URLError, TimeoutError) as e:
                print("  descubrir:", t, "ERROR", e); break
            for st in r.get("studies", []):
                p = st["protocolSection"]; nct = p["identificationModule"]["nctId"]
                if nct not in conocidos and nct not in vistos:
                    vistos[nct] = (p["identificationModule"].get("briefTitle", ""), "; ".join((p.get("conditionsModule") or {}).get("conditions", [])[:3]),
                                   (p.get("statusModule") or {}).get("overallStatus", ""),
                                   "; ".join(sorted({(l.get("city") or "") for l in (p.get("contactsLocationsModule") or {}).get("locations", []) if l.get("country") == "Spain"})),
                                   "; ".join(s.get("id", "") for s in p["identificationModule"].get("secondaryIdInfos", []) or []))
            tok = r.get("nextPageToken")
            time.sleep(0.5)
            if not tok: break
    with open(D / "datos/ctgov_candidatos_nuevos.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";"); w.writerow(["nct", "titulo", "condiciones", "estado", "ciudades_espana", "otros_ids"])
        for nct, v in sorted(vistos.items()):
            w.writerow([nct, *v])
    print(f"{len(vistos)} estudios con centros en España que no están en tu lista -> datos/ctgov_candidatos_nuevos.csv (revísalos: algunos no son de hematología o no están en el REec)")
