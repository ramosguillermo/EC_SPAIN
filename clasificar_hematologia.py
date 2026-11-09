#!/usr/bin/env python3
"""
Clasifica los ensayos de datos/busqueda.json en: hematología / dudosos / excluidos.
Usa título e indicación (ES y EN) que devuelve la búsqueda del REEC.

Salidas (en datos/):
  clasificacion_hematologia.xlsx   hojas: Resumen, Hematología, Dudosos, Excluidos
  ids_hematologia.json             lo que lee `extraer_reec.py --hematologia`
  revision_manual.csv              TUS decisiones (separador ';'): columna decision = incluir / excluir
                                   Se conserva entre ejecuciones y manda sobre las reglas.

Uso:  python clasificar_hematologia.py
      python clasificar_hematologia.py --entrada otra.json --salida carpeta
"""
import argparse, csv, json, re, unicodedata
from collections import Counter
from pathlib import Path
from openpyxl import Workbook

# ---------------------------------------------------------------------------
# REGLAS. (subárea, términos en minúsculas y SIN acentos [coinciden por prefijo de palabra],
#          abreviaturas sensibles a mayúsculas)
# ---------------------------------------------------------------------------
DEFINITIVOS = [
    ("Leucemias agudas", [
        "leucemia mieloide aguda", "leucemia linfoblastica", "leucemia linfoide aguda", "leucemia aguda",
        "leucemia promielocitica", "acute myeloid", "acute lymphoblastic", "acute lymphocytic",
        "acute promyelocytic", "acute leukemia", "acute leukaemia", "blastic plasmacytoid"],
        ["AML", "APL"]),
    ("LMC y LLC", [
        "leucemia mieloide cronica", "leucemia linfocitica cronica", "leucemia linfoide cronica",
        "chronic myeloid", "chronic myelogenous", "chronic lymphocytic", "small lymphocytic",
        "leucemia mielomonocitica", "chronic myelomonocytic"],
        ["CML", "CLL", "CMML"]),
    ("Leucemias (sin especificar)", ["leucemia", "leukemia", "leukaemia"], []),
    ("Linfomas", [
        "linfoma", "lymphoma", "hodgkin", "waldenstrom", "macroglobulinemia", "burkitt",
        "linfoproliferativ", "lymphoproliferative"],
        ["DLBCL", "CTCL", "PTCL", "MALT"]),
    ("Mieloma y discrasias", [
        "mieloma", "myeloma", "gammapatia", "gammopathy", "plasmocitoma", "plasmacytoma",
        "amiloidosis al", "al amyloidosis", "light chain amyloidosis", "amiloidosis de cadenas ligeras"],
        ["MGUS", "NDMM", "RRMM"]),
    ("SMD y NMP", [
        "mielodisplas", "myelodysplas", "mielofibrosis", "myelofibrosis", "policitemia vera",
        "polycythemia vera", "trombocitemia esencial", "essential thrombocythemia", "mieloproliferativ",
        "myeloproliferative", "mastocitosis sistemica", "systemic mastocytosis", "neoplasia mieloide",
        "myeloid neoplasm"],
        ["MDS", "MPN", "NMP", "SMD"]),
    ("TPH y EICR", [
        "trasplante de progenitores", "trasplante de medula", "trasplante alogenico",
        "trasplante hematopoyetico", "stem cell transplant", "hematopoietic stem cell",
        "hematopoietic cell transplant", "bone marrow transplant", "graft-versus-host",
        "graft versus host", "injerto contra huesped", "injerto contra el huesped"],
        ["HSCT", "TPH", "GVHD", "EICH", "EICR"]),
    ("Hematología benigna", [
        "anemia falciforme", "celulas falciformes", "drepanocitosis", "sickle cell", "talasemia",
        "thalassemia", "thalassaemia", "anemia aplasica", "aplastic anemia", "aplasia medular",
        "hemoglobinuria paroxistica", "paroxysmal nocturnal", "trombocitopenia inmune",
        "immune thrombocytopeni", "purpura trombocitopenica", "thrombotic thrombocytopenic",
        "hemofilia", "haemophilia", "hemophilia", "von willebrand", "anemia hemolitica",
        "hemolytic anemia", "aglutininas frias", "cold agglutinin", "hemofagocitica", "hemophagocytic",
        "sindrome hemolitico uremico", "hemolytic uremic", "hemocromatosis", "hemochromatosis",
        "neutropenia cronica", "chronic neutropenia"],
        ["PNH", "HPN", "ITP", "PTI", "TTP", "aHUS", "HLH"]),
]
# Si SOLO coincide algo de esto -> "dudoso" (decides tú en revision_manual.csv)
DUDOSOS = [
    ("Hemostasia / trombosis", ["trombosis", "thrombosis", "tromboembol", "thromboembol", "anticoagul",
                                "embolia pulmonar", "pulmonary embol"], []),
    ("Anemia (sin especificar)", ["anemia", "anaemia"], []),
    ("Déficit de hierro", ["deficit de hierro", "deficiencia de hierro", "iron deficiency", "ferropenia"], []),
    ("Citopenias", ["neutropenia", "trombocitopenia", "thrombocytopeni", "pancitopenia", "pancytopenia"], []),
    ("Amiloidosis (sin especificar)", ["amiloidosis", "amyloidosis"], []),
    ("Hematología (genérico)", ["hematolog", "haematolog", "hematopoy", "medula osea", "bone marrow"], []),
    ("Terapia celular (CAR-T)", ["car-t", "car t", "chimeric antigen receptor", "receptor quimerico"], []),
]
# ---------------------------------------------------------------------------

def sin_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()

def limpia(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(s or ""))).strip()

def g(d, *claves):
    m = {k.lower(): k for k in d}
    for c in claves:
        if c.lower() in m and d[m[c.lower()]] not in (None, ""):
            return d[m[c.lower()]]
    return ""

# Abreviaturas con otros significados frecuentes (MDS = también síndrome de duplicación de MECP2,
# NMP = nefropatía membranosa primaria, APL = prefijo de códigos de fármaco…).
# Si solo coincide una de estas, el ensayo va a "dudoso" en lugar de entrar directamente.
AMBIGUAS = {"MDS", "SMD", "APL", "NMP", "MALT"}

def busca(reglas, texto, texto_n, ambiguas=None):
    """Devuelve {subárea: [términos]}. Las abreviaturas ambiguas se apartan en `ambiguas`."""
    res = {}
    for nombre, terminos, abrevs in reglas:
        hit = [t for t in terminos if re.search(r"(?<![a-z])" + re.escape(t), texto_n)]
        for a in abrevs:
            # no cuenta si va seguida de "-123" (código de fármaco: APL-101)
            if re.search(r"(?<![A-Za-z0-9])" + re.escape(a) + r"(?![A-Za-z0-9]|-\d)", texto):
                if a in AMBIGUAS:
                    if ambiguas is not None:
                        ambiguas.setdefault(nombre, []).append(a)
                else:
                    hit.append(a)
        if hit:
            res[nombre] = hit
    return res

def clasifica(b):
    texto = limpia(" ".join(str(g(b, k)) for k in ("titulo_es", "titulo_en", "indicacion_es", "indicacion_en")))
    tn = sin_acentos(texto)
    amb = {}
    d = busca(DEFINITIVOS, texto, tn, amb)
    if len(d) > 1 and "Leucemias (sin especificar)" in d:      # ya hay una leucemia concreta
        d.pop("Leucemias (sin especificar)")
    if d:
        return "hematologia", d
    du = busca(DUDOSOS, texto, tn)
    for k, v in amb.items():
        du.setdefault(k + " (abreviatura ambigua)", []).extend(v)
    return ("dudoso", du) if du else ("excluido", {})

def leer_manual(f):
    man = {}
    if f.exists():
        with open(f, encoding="utf-8-sig", newline="") as fh:
            for fila in csv.DictReader(fh, delimiter=";"):
                if fila.get("identificador"):
                    man[fila["identificador"].strip()] = (fila.get("titulo", ""), (fila.get("decision") or "").strip().lower())
    return man

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default=str(Path(__file__).parent / "datos" / "busqueda.json"))
    ap.add_argument("--salida", default=str(Path(__file__).parent / "datos"))
    a = ap.parse_args()
    out = Path(a.salida); out.mkdir(parents=True, exist_ok=True)
    busq = json.loads(Path(a.entrada).read_text(encoding="utf-8"))
    manual = leer_manual(out / "revision_manual.csv")

    filas = {"hematologia": [], "dudoso": [], "excluido": []}
    incluir, subareas = [], {}
    for b in busq:
        ident = str(g(b, "identificador"))
        if not ident:
            continue
        estado, det = clasifica(b)
        titulo = limpia(g(b, "titulo_es") or g(b, "titulo_en"))
        ind = limpia(g(b, "indicacion_es") or g(b, "indicacion_en"))
        decision = manual.get(ident, ("", ""))[1]
        origen = "reglas"
        if decision == "incluir":
            estado, origen = "hematologia", "manual"
        elif decision == "excluir":
            estado, origen = "excluido", "manual"
        cats = list(det)
        if estado == "hematologia":
            incluir.append(ident)
            subareas[ident] = cats or ["Hematología (manual)"]
        filas[estado].append({
            "identificador": ident, "subareas": "; ".join(cats), "titulo": titulo, "indicacion": ind,
            "promotor": limpia(g(b, "promotor")), "terminos": "; ".join(t for v in det.values() for t in v),
            "origen": origen})

    # CSV de decisiones: conserva lo que ya había y añade los dudosos nuevos
    for f in filas["dudoso"]:
        manual.setdefault(f["identificador"], (f["titulo"], ""))
    with open(out / "revision_manual.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["identificador", "titulo", "decision"])
        for i, (t, dcs) in manual.items():
            w.writerow([i, t, dcs])

    (out / "ids_hematologia.json").write_text(json.dumps({
        "incluir": incluir, "subareas": subareas,
        "dudosos_pendientes": [f["identificador"] for f in filas["dudoso"]
                               if not manual.get(f["identificador"], ("", ""))[1]],
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    wb = Workbook(); ws = wb.active; ws.title = "Resumen"
    cuenta = Counter(s for v in subareas.values() for s in v)
    ws.append(["Total en la búsqueda", len(busq)])
    ws.append(["Hematología", len(filas["hematologia"])])
    ws.append(["Dudosos", len(filas["dudoso"])])
    ws.append(["Excluidos", len(filas["excluido"])])
    ws.append([]); ws.append(["Subárea (un ensayo puede tener varias)", "Ensayos"])
    for k, v in cuenta.most_common(): ws.append([k, v])
    for hoja, clave in (("Hematología", "hematologia"), ("Dudosos", "dudoso"), ("Excluidos", "excluido")):
        w = wb.create_sheet(hoja)
        w.append(["identificador", "subareas", "titulo", "indicacion", "promotor", "terminos", "origen"])
        for f in filas[clave]:
            w.append([f[k] for k in ("identificador", "subareas", "titulo", "indicacion", "promotor", "terminos", "origen")])
        w.freeze_panes = "A2"
        for col, ancho in zip("ABCDEFG", (20, 26, 60, 60, 30, 30, 9)): w.column_dimensions[col].width = ancho
    try:
        wb.save(out / "clasificacion_hematologia.xlsx")
    except PermissionError:
        wb.save(out / "clasificacion_hematologia_nuevo.xlsx")
        print("AVISO: el Excel estaba abierto; guardado como clasificacion_hematologia_nuevo.xlsx")

    print(f"Total {len(busq)} | hematología {len(filas['hematologia'])} | "
          f"dudosos {len(filas['dudoso'])} | excluidos {len(filas['excluido'])}")
    for k, v in cuenta.most_common(): print(f"   {k}: {v}")

if __name__ == "__main__":
    main()
