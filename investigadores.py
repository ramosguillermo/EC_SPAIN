"""Unifica los nombres de investigador principal del REec (mayúsculas, acentos, «Apellidos, Nombre», nombre incompleto)."""
import re, csv, unicodedata, html
from pathlib import Path

_PARTICULAS = {"de", "del", "la", "las", "los", "y", "i", "d", "da", "do", "dos", "van", "von"}
_VACIO = re.compile(r"^(|-+|n/?a|na|tbd|tba|ninguno|desconocido|no aplica|no procede)$|pendiente|designar|determinar|to be (determined|assigned)|por confirmar", re.I)

def _sa(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def limpia(raw):
    """-> nombre de pila + apellidos, bien escrito; '' si no hay investigador."""
    s = str(raw or "")
    for _ in range(2):
        s = html.unescape(s)
    s = re.sub(r"\(([^)]*)\)", " ", s)                      # «Pau (Pablo) Abrisqueta»: se quita el alias
    s = re.sub(r"(?i)\b(n/?a|nan|null)\b", " ", s)           # huecos rellenados con «NA»
    s = re.sub(r"\s+", " ", s).strip(" .;")
    s = re.sub(r"(?i)^((dr|dra|prof|profa|d|dña)\.?\s+|profesor(a)?\s+|doctor(a)?\s+)+", "", s).strip()
    if _VACIO.search(s):
        return ""
    if s.count(",") == 1:                       # «Apellidos, Nombre»
        a, b = [x.strip() for x in s.split(",")]
        if a and b:
            s = b + " " + a
    if s.isupper() or s.islower():
        s = " ".join(w if w.lower() in _PARTICULAS and i else w.capitalize() for i, w in enumerate(s.lower().split()))
    return s

def tokens(s):
    return frozenset(t for t in re.sub(r"[^a-z0-9 ]+", " ", _sa(s).lower()).split() if t not in _PARTICULAS)

def _manual():
    f = Path(__file__).parent / "datos" / "investigadores_manual.csv"
    m = {}
    if f.exists():
        for r in csv.DictReader(f.open(encoding="utf-8-sig"), delimiter=";"):
            m[tokens(limpia(r["variante"]))] = limpia(r["canonico"])
    return m

def _no_unir():
    f = Path(__file__).parent / "datos" / "investigadores_separar.csv"
    s = set()
    if f.exists():
        for r in csv.DictReader(f.open(encoding="utf-8-sig"), delimiter=";"):
            s.add(frozenset((tokens(limpia(r["a"])), tokens(limpia(r["b"])))))
    return s

def construir_mapa(pares):
    """pares: [(nombre_crudo, hospital_id)] -> {nombre_crudo: nombre canónico}. Une variantes de la misma persona."""
    man = _manual()
    NO = _no_unir()
    var = {}                                    # nombre limpio -> nº de apariciones
    en_hosp = {}                                # hospital -> {nombre limpio}
    crudos = {}
    for raw, h in pares:
        n = limpia(raw)
        crudos[raw] = n
        if not n:
            continue
        var[n] = var.get(n, 0) + 1
        en_hosp.setdefault(h, set()).add(n)
    padre = {n: n for n in var}
    def raiz(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]; x = padre[x]
        return x
    def une(a, b):
        ra, rb = raiz(a), raiz(b)
        if ra != rb: padre[ra] = rb
    por_tok = {}
    for n in var:
        por_tok.setdefault(tokens(n), []).append(n)
    for ns in por_tok.values():                 # mismas palabras (acentos, orden de mayúsculas…)
        for n in ns[1:]: une(n, ns[0])
    for ns in en_hosp.values():                 # en el mismo hospital, «Pau Abrisqueta» ⊂ «Pau Abrisqueta Costa»
        for a in ns:
            ta = tokens(a)
            if len(ta) < 2: continue
            for b in ns:
                tb = tokens(b)
                if a != b and ta < tb and frozenset((ta, tb)) not in NO: une(a, b)
    for t, canon in man.items():                # correcciones manuales
        for n in por_tok.get(t, []):
            if canon in var: une(n, canon)
    grupos = {}
    for n in var: grupos.setdefault(raiz(n), []).append(n)
    canon = {}
    for ns in grupos.values():
        mejor = max(ns, key=lambda x: (len(tokens(x)), sum(not c.isascii() for c in x), var[x]))
        for n in ns: canon[n] = mejor
    dudas = []
    for ns in grupos.values():                  # fusiones arriesgadas: alguna variante tiene solo nombre y un apellido
        if len({tokens(x) for x in ns}) > 1 and min(len(tokens(x)) for x in ns) <= 2:
            dudas.append({"tipo": "fusion", "canonico": canon[ns[0]], "variantes": sorted(ns), "hospitales": sorted({h for h, s in en_hosp.items() if s & set(ns)})})
    for h, ns in en_hosp.items():               # posibles duplicados sin fusionar: mismo hospital, mismo último apellido y nombre de pila parecido
        porape = {}
        for n in ns:
            porape.setdefault(_sa(limpia(n)).lower().split()[-1], set()).add(canon[n])
        for ap, cs in porape.items():
            cs = sorted(cs)
            for i in range(len(cs)):
                for j in range(i + 1, len(cs)):
                    a_, b_ = _sa(cs[i]).lower().split()[0], _sa(cs[j]).lower().split()[0]
                    if a_ == b_ or a_[:3] == b_[:3]:
                        dudas.append({"tipo": "duplicado", "canonico": cs[i], "variantes": [cs[i], cs[j]], "hospitales": [h]})
    return {raw: (canon.get(n, "") if n else "") for raw, n in crudos.items()}, grupos, dudas
