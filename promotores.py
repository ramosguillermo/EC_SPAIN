"""Unifica los nombres de promotor del REec y los clasifica (industria / grupo cooperativo / hospital-universidad)."""
import re, csv, unicodedata
from pathlib import Path

def _sa(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

# (patrón sobre el nombre sin tildes en minúsculas) -> (nombre canónico, tipo). Se evalúan en orden.
REGLAS = [
    (r"janssen|johnson & johnson", "Janssen (Johnson & Johnson)", "industria"),
    (r"merck sharp|msd\b", "Merck Sharp & Dohme (MSD)", "industria"),
    (r"hoffmann|roche|genentech|chugai", "Roche / Genentech", "industria"),
    (r"astra ?zeneca", "AstraZeneca", "industria"),
    (r"celgene|bristol", "Bristol-Myers Squibb (incl. Celgene)", "industria"),
    (r"novartis", "Novartis", "industria"),
    (r"pfizer", "Pfizer", "industria"),
    (r"sanofi", "Sanofi", "industria"),
    (r"abbvie", "AbbVie", "industria"),
    (r"glaxo", "GlaxoSmithKline", "industria"),
    (r"takeda", "Takeda", "industria"),
    (r"beone|beigene", "BeOne (BeiGene)", "industria"),
    (r"novo nordisk", "Novo Nordisk", "industria"),
    (r"regeneron", "Regeneron", "industria"),
    (r"eli lilly", "Eli Lilly", "industria"),
    (r"pethema", "PETHEMA", "cooperativo"),
    (r"geltamo", "GELTAMO", "cooperativo"),
    (r"hovon", "HOVON", "cooperativo"),
    (r"european myeloma network", "European Myeloma Network", "cooperativo"),
    (r"trasplante hematopoyetico", "GETH-TC", "cooperativo"),
    (r"\bgela\b|lymphoma study association|\blysa\b|eortc|\bgimema\b|german.*(group|study)|\bgmmg\b|nordic|\bgrupo\b|(study|research|working|trial|trials) group|\bnetwork\b|cooperative", None, "cooperativo"),
]
_ACAD = r"universit|univerzit|klinikum|charit|hospital|institut|fundaci|stichting|centrum|center|centre|medical university|clinic|zentrum|zentrale|sjukhus|fondazione|foundation|istituto|assistance publique|\bchu\b|\bnhs\b|cancer research|gustave|netherlands|karolinska"
_SUF = r"\b(inc|llc|ltd|limited|gmbh|ag|sa|s\.a|s a|s l|s\.l|nv|bv|b\.v|plc|corp|corporation|co|kgaa|kg|spa|s\.p\.a|srl|s\.r\.l|a/s|ab|oy|pty|lp|sl|se|unlimited company|group|therapeutics|pharmaceuticals?|pharma|biopharma|oncology|medicines|development|research|international|services|americas|center|deutschland|usa|us)\b"

def _manual():
    f = Path(__file__).parent / "datos" / "promotores_manual.csv"
    m = {}
    if f.exists():
        for r in csv.DictReader(f.open(encoding="utf-8-sig"), delimiter=";"):
            m[_sa(r["promotor"]).lower().strip()] = (r["canonico"].strip(), (r.get("tipo") or "").strip())
    return m
MANUAL = _manual()

def canon_detalle(raw):
    """-> (nombre canónico, tipo, origen): origen = 'manual' | 'regla' | 'auto' (asignado por heurística: conviene revisarlo)"""
    raw = (raw or "").strip()
    if not raw:
        return "Sin promotor", "otro", "regla"
    k = _sa(raw).lower().strip()
    if k in MANUAL:
        c, t = MANUAL[k]
        return c, t or clasifica(c), "manual"
    for rx, c, t in REGLAS:
        if re.search(rx, k):
            return (c or limpia(raw)), t, ("regla" if c else "auto")
    return limpia(raw), clasifica(raw), "auto"

def canon(raw):
    """-> (nombre canónico, tipo)"""
    c, t, _ = canon_detalle(raw)
    return c, t

def clasifica(raw):
    return "academico" if re.search(_ACAD, _sa(raw).lower()) else "industria"

def limpia(raw):
    s = _sa(raw).replace("¿", "'")
    s = re.sub(r"[,.]", " ", s)
    prev = None
    while prev != s:                       # quita sufijos societarios repetidos al final
        prev = s
        s = re.sub(_SUF + r"\s*$", "", s.strip(), flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    return s.title() if s.isupper() or s.islower() else s
