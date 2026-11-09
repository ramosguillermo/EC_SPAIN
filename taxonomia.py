#!/usr/bin/env python3
"""Taxonomía de enfermedades para la web, agrupada según la clasificación OMS de tumores
hematolinfoides (WHO-HAEM5, 2022) y, para lo no neoplásico, por grandes grupos clínicos.

Se clasifica con TÍTULO + INDICACIÓN + TÍTULO CIENTÍFICO a la vez, porque el campo
«indicación» del REEC suele ser genérico (p. ej. «Myeloproliferative Neoplasms») mientras que
el título nombra la enfermedad concreta («mielofibrosis o trombocitemia esencial»).

Un ensayo puede tener varias entidades. Si el texto solo dice algo genérico, se asigna la
entidad GENÉRICA (p. ej. «NMP sin especificar») y la web la muestra como «posible» para las
entidades concretas que abarca (campo `cubre`)."""
import re, unicodedata

GRUPOS = [  # (id, etiqueta, nota)
    ("nmp", "Neoplasias mieloproliferativas (NMP)", "OMS"),
    ("masto", "Mastocitosis", "OMS"),
    ("smd", "Neoplasias mielodisplásicas (SMD) y SMD/NMP", "OMS"),
    ("lma", "Leucemia mieloide aguda y neoplasias relacionadas", "OMS"),
    ("lla", "Leucemias y linfomas linfoblásticos (precursores B/T)", "OMS"),
    ("bmad", "Neoplasias de células B maduras (LLC y linfomas B)", "OMS"),
    ("hodgkin", "Linfoma de Hodgkin clásico", "OMS"),
    ("tnk", "Neoplasias de células T y NK maduras", "OMS"),
    ("pc", "Neoplasias de células plasmáticas (mieloma, amiloidosis AL)", "OMS"),
    ("inm", "Trastornos linfoproliferativos asociados a inmunodeficiencia", "OMS"),
    ("hist", "Histiocitosis y linfohistiocitosis hemofagocítica", "OMS"),
    ("multi", "Neoplasias hematológicas de varios tipos o sin especificar", "OMS"),
    ("cit", "Citopenias inmunes (PTI, anemia hemolítica autoinmune)", "No neoplásico"),
    ("hem", "Trastornos hemorrágicos congénitos (hemofilia, von Willebrand)", "No neoplásico"),
    ("hbp", "Hemoglobinopatías (drepanocitosis, talasemia)", "No neoplásico"),
    ("comp", "Enfermedades mediadas por complemento y microangiopatías", "No neoplásico"),
    ("anem", "Anemias y fallo medular", "No neoplásico"),
    ("hemo", "Trombosis y anticoagulación", "No neoplásico"),
    ("tph", "Trasplante de progenitores hematopoyéticos y sus complicaciones", "Otros"),
    ("sop", "Infección, neutropenia y toxicidad de la inmunoterapia", "Otros"),
    ("otro", "Otros / estudios no exclusivamente hematológicos", "Otros"),
]

# id, grupo, etiqueta, regex sobre texto SIN tildes y en minúsculas, abreviaturas (mayúsculas, exactas), opciones
E = [
    # --- Neoplasias mieloproliferativas
    ("lmc", "nmp", "Leucemia mieloide crónica (LMC)", r"leucemia (mieloide|mielogena) cronica|chronic myel(oid|ogenous) leuk", ["CML", "LMC"], {}),
    ("pv", "nmp", "Policitemia vera", r"policitemia vera|polyc[yi]th(a)?emia vera", [], {}),
    ("te", "nmp", "Trombocitemia esencial", r"trombocitemia esencial|essential thrombocyth(a)?emia", [], {}),
    ("mf", "nmp", "Mielofibrosis", r"mielofibrosis|myelofibrosis", [], {}),
    ("nmp", "nmp", "NMP sin especificar", r"mieloproliferativ|myeloproliferative", ["MPN", "NMP"],
     {"cubre": ["lmc", "pv", "te", "mf"]}),
    ("masto", "masto", "Mastocitosis sistémica", r"mastocitosis|mastocytosis", [], {}),
    # --- SMD
    ("smd", "smd", "Síndrome mielodisplásico (SMD)", r"mielodisplasic|myelodysplastic", ["MDS", "SMD"], {}),
    ("lmmc", "smd", "Leucemia mielomonocítica crónica (LMMC)", r"mielomonocitica cronica|chronic myelomonocytic", ["CMML", "LMMC"], {}),
    # --- LMA
    ("lma", "lma", "Leucemia mieloide aguda (LMA)", r"leucemia mieloide aguda|acute myel(oid|ogenous)", ["AML", "LMA"], {}),
    ("lpa", "lma", "Leucemia promielocítica aguda (LPA)", r"promielocitica|promyelocytic", ["LPA"], {}),
    ("mieloide", "lma", "Neoplasia mieloide sin especificar", r"neoplasias? (malignas? )?mieloides|myeloid (malignanc|neoplasm)", [],
     {"cubre": ["lma", "smd", "lmmc", "lmc", "pv", "te", "mf", "nmp"]}),
    # --- Linfoblásticos
    ("lla_b", "lla", "LLA de precursores B", r"b[- ]cell acute lymphoblastic|b[- ]all\b|precursor b|b-cell precursor|linfoblastica aguda b|cd19.{0,80}(acute lymphoblastic|acute lymphoid|linfoblastica)|(acute lymphoblastic|acute lymphoid|linfoblastica).{0,80}cd19", ["B-ALL", "BCP-ALL", "LLA-B"], {}),
    ("lla_t", "lla", "LLA de precursores T", r"t[- ]cell acute lymphoblastic|t[- ]cell acute lymphoid|acute lymphoblastic t\b|linfoblastica aguda t\b|\bt-all\b|\blla-t\b", ["T-ALL", "LLA-T"], {}),
    ("lla_ph", "lla", "LLA Ph+ (BCR::ABL1)", r"philadelphia", [], {"requiere": "lla"}),
    ("lla", "lla", "LLA sin especificar linaje", r"leucemia linfoblastica aguda|leucemia linfoide aguda|acute lymphoblastic|acute lymphoid leuk|acute lymphocytic", ["ALL", "LLA"],
     {"cubre": ["lla_b", "lla_t", "lla_ph"]}),
    ("lbl", "lla", "Linfoma linfoblástico", r"linfoma linfoblastico|lymphoblastic lymphoma", ["LBL"], {}),
    # --- B maduras
    ("llc", "bmad", "LLC / linfoma linfocítico de células pequeñas", r"linfocitica cronica|chronic lymphocytic|linfoma linfocitico|small lymphocytic|linfocitos pequenos", ["LLC", "CLL", "SLL", "LLP"], {}),
    ("lcm", "bmad", "Linfoma de células del manto", r"celulas del manto|mantle cell", ["LCM", "MCL"], {}),
    ("lf", "bmad", "Linfoma folicular", r"linfoma folicular|follicular lymphoma", [], {}),
    ("lbdcg", "bmad", "Linfoma B difuso de células grandes", r"celulas b grandes|large b[- ]cell|difuso de celulas grandes", ["LBDCG", "DLBCL", "LBCL"], {}),
    ("lpsnc", "bmad", "Linfoma primario del SNC", r"central nervous system lymph|linfoma.{0,40}sistema nervioso central|sistema nervioso central.{0,40}linfoma", ["PCNSL", "LPSNC"], {}),
    ("lzm", "bmad", "Linfoma de la zona marginal", r"zona marginal|marginal zone", ["LZM", "MZL"], {}),
    ("wm", "bmad", "Macroglobulinemia de Waldenström", r"waldenstrom|macroglobulinemia", [], {}),
    ("lb", "bmad", "Linfoma / neoplasia B sin especificar",
     r"linfoma (no hodgkin )?de (linfocitos|celulas) b|b[- ]cell (non[- ]hodgkin )?lymphoma|b[- ]cell nhl|b[- ]cell malignanc|neoplasias? (malignas? )?de (celulas|linfocitos) b|mature b[- ]cell|linfoma b\b|cancer de (las )?celulas b|advanced b cell|any type of b-cell",
     ["B-NHL"], {"cubre": ["llc", "lcm", "lf", "lbdcg", "lpsnc", "lzm", "wm"]}),
    # --- Hodgkin y T/NK
    ("hodgkin", "hodgkin", "Linfoma de Hodgkin clásico", r"(?<!non[- ])(?<!no[- ])hodgkin", ["cHL"], {}),
    ("lt", "tnk", "Linfoma T/NK periférico o cutáneo", r"large granular|granulares grandes|linfomas? t\b|t[- ]cell lymphoma|peripheral t|linfoma de celulas t|micosis fungoide|mycosis fungoides|sezary|anaplastic large", ["PTCL", "CTCL"], {}),
    ("lnh", "bmad", "Linfoma sin especificar", r"linfoma|lymphoma|lymphoid malignanc|neoplasias linfoides", ["NHL", "NHLs", "LNH"],
     {"cubre": ["llc", "lcm", "lf", "lbdcg", "lpsnc", "lzm", "wm", "lb", "hodgkin", "lt", "lbl", "ptld"]}),
    # --- Células plasmáticas
    ("mm", "pc", "Mieloma múltiple", r"mieloma|myeloma", ["MM", "MMRR", "MMND", "RRMM", "NDMM"], {}),
    ("lcp", "pc", "Leucemia de células plasmáticas", r"plasma cell leuk|leucemia de celulas plasmaticas|plasmocitaria", [], {}),
    ("mgus", "pc", "Gammapatía monoclonal / mieloma latente", r"gammapatia monoclonal|monoclonal gammopathy|smoldering|mieloma latente|quiescente", ["MGUS"], {}),
    ("al", "pc", "Amiloidosis AL", r"amiloidosis|amyloidosis", [], {}),
    # --- Inmunodeficiencia / histiocitosis
    ("ptld", "inm", "Enfermedad linfoproliferativa postrasplante (EBV+)", r"linfoproliferativ|lymphoproliferative", ["PTLD"], {}),
    ("hlh", "hist", "Linfohistiocitosis hemofagocítica (HLH)", r"hemofagocitic|hemophagocytic|linfohistiocitosis", ["HLH", "sHLH"], {}),
    ("histio", "hist", "Histiocitosis", r"histiocitosis|histiocytosis|langerhans|erdheim", [], {"cubre": ["hlh"]}),
    # --- Multi / genéricos
    ("leucemia_ag", "multi", "Leucemia aguda sin especificar", r"leucemias? agudas?|acute leuk(a)?emia", [], {"cubre": ["lma", "lla", "lla_b", "lla_t", "lla_ph"]}),
    ("leucemias", "multi", "Leucemias (varios tipos)", r"leucemias|leuk(a)?emias", [], {"cubre": ["lma", "lla", "lla_b", "lla_t", "lla_ph", "lmc", "llc", "lmmc", "leucemia_ag"]}),
    ("hem_malig", "multi", "Neoplasias hematológicas (varios tipos)",
     r"hematicas|hematolog\w* malignanc|haematolog\w* malignanc|neoplasias? (malignas? )?hematologicas?|cancer(es)? de la sangre|cancer de sangre|blood cancer|certain blood|ciertos canceres de la sangre|hematologic\w* neoplas",
     [], {"cubre": ["*"]}),
    # --- No neoplásico
    ("pti", "cit", "Trombocitopenia inmune (PTI)", r"trombocitopenia (inmun|autoinmun)|purpura trombocitopenica|immune[- ](mediated )?thrombocytopeni|autoimmune thrombocytopeni", ["ITP", "PTI"], {}),
    ("ahai", "cit", "Anemia hemolítica autoinmune (AHAI)", r"anemia hemolitica autoinmune|autoimmune h(a)?emolytic|cold agglutinin|crioaglutininas", ["AIHA", "AHAI"], {}),
    ("cit", "cit", "Citopenias autoinmunes sin especificar", r"autoimmune blood cell|citopenias? autoinmune|autoimmune cytopeni|\bevans\b", [], {"cubre": ["pti", "ahai"]}),
    ("hemofilia", "hem", "Hemofilia A / B", r"hemofilia|h(a)?emophilia", [], {}),
    ("evw", "hem", "Enfermedad de von Willebrand", r"von willebrand", [], {}),
    ("coag", "hem", "Otros déficits de coagulación congénitos", r"deficit de factor|factor (vii|x|xiii|v) deficiency|glanzmann|afibrinogenemia", [], {}),
    ("scd", "hbp", "Drepanocitosis (anemia falciforme)", r"falciforme|drepanocit|sickle", [], {}),
    ("talasemia", "hbp", "Talasemia", r"talasemia|thalass(a)?emia", [], {}),
    ("hpn", "comp", "Hemoglobinuria paroxística nocturna (HPN)", r"hemoglobinuria paroxistica|paroxysmal nocturnal", ["HPN", "PNH"], {}),
    ("shua", "comp", "Síndrome hemolítico urémico atípico", r"hemolitico uremico|h(a)?emolytic ura?emic", ["SHUa", "aHUS"], {}),
    ("ttp", "comp", "Púrpura trombótica trombocitopénica (PTT)", r"purpura trombocitopenica trombotica|thrombotic thrombocytopenic", ["TTP", "cTTP", "PTT"], {}),
    ("mat", "comp", "Microangiopatía trombótica (MAT)", r"microangiopatia trombotica|thrombotic microangiopathy", ["TMA"], {}),
    ("aplasia", "anem", "Aplasia medular / fallo medular", r"anemia aplasica|aplastic an(a)?emia|aplasia medular|fanconi|fallo medular|bone marrow failure|diamond[- ]blackfan", [], {}),
    ("anemia", "anem", "Otras anemias y alteraciones del hierro", r"an(a)?emia|iron|hierro|hemocromatosis|hemochromatosis", [], {"fallback": True}),
    ("trombosis", "hemo", "Trombosis y anticoagulación", r"trombosis|thrombosis|tromboembol|thromboembol|anticoagul|antiphospholipid|antifosfolip", [], {}),
    # --- Trasplante y soporte
    ("eich", "tph", "Enfermedad injerto contra receptor (EICR)", r"injerto contra|graft[- ]versus[- ]host|graft[- ]vs[- ]host", ["GVHD", "cGVHD", "aGVHD", "EICH", "EICR", "EICHc", "EICHa"], {}),
    ("tph_inf", "tph", "Infecciones tras trasplante (CMV, adenovirus…)", r"citomegalovirus|cytomegalovirus|adenovir|epstein", ["CMV", "EBV"],
     {"ctx": r"tr[ae]nsplant|trasplante|\btph\b|\bhsct\b|stem cell|progenitores"}),
    ("tph", "tph", "Trasplante de progenitores hematopoyéticos (TPH)", r"trasplante de (progenitores|celulas madre|precursores)|stem cell transplant|hematopoietic (stem )?cell transplant|haematopoietic stem cell|alogenic|allogeneic|alogenico", ["HSCT", "TPH", "alo-TPH"], {}),
    ("infeccion", "sop", "Infección, neutropenia e inmunodeficiencia secundaria", r"neutropeni|infection prophylaxis|prophylaxis of infection|profilaxis de la infeccion|infecci|infection|hipogammaglobulinemia|hypogammaglobulinemia|deficiencia secundaria de anticuerpos|secondary antibody deficiency", [], {}),
    ("crs", "sop", "Toxicidad de inmunoterapia (SLC, neurotoxicidad)", r"liberacion de citocinas|cytokine release|gprc5d-related", ["CRS", "ICANS"], {}),
    # --- Otros
    ("solidos", "otro", "Tumores sólidos (estudio multi-tumor)", r"tumores solidos|solid tumou?rs?|non-small cell|cancer de pulmon|lung cancer|sarcoma|neuroblastoma|prostat|rhabdomyo|cancer avanzado|advanced cancer", ["NSCLC", "SCLC"], {}),
    ("inmuno", "otro", "Enfermedades inmunomediadas no hematológicas", r"dermatomyositis|myopathy|pemphig|behcet|enfermedades del sistema inmunitario|immunological diseases", [], {}),
    ("sin", "otro", "Sin clasificar", r"$^", [], {"ultimo": True}),
]

_RX = {}
for i, g, lab, rx, abbr, op in E:
    ab = re.compile(r"(?<![A-Za-z])(?:%s)(?![A-Za-z])" % "|".join(re.escape(a) for a in abbr)) if abbr else None
    _RX[i] = (re.compile(rx), ab, re.compile(op["ctx"]) if op.get("ctx") else None)

def _sin_tildes(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))

def clasificar(*textos):
    orig = _sin_tildes(" ".join(t for t in textos if t))
    orig = re.sub(r"(?i)(myeloid|mieloide) lymphoma", r"\1 leukemia", orig)   # errata frecuente: «acute myeloid lymphoma»
    low = orig.lower()
    crudo = set()
    for i, g, lab, rx, abbr, op in E:
        if op.get("ultimo"):
            continue
        r, ab, ctx = _RX[i]
        ok = bool(r.search(low)) or bool(ab and ab.search(orig))
        if ok and ctx and not ctx.search(low):
            ok = False
        if ok:
            crudo.add(i)
    ops = {x[0]: x[5] for x in E}
    res = set(crudo)
    for i in list(res):                                   # dependencias («requiere»)
        req = ops[i].get("requiere")
        if req and req not in crudo:
            res.discard(i)
    neoplasicos = {x[0] for x in E if x[1] in ("nmp", "masto", "smd", "lma", "lla", "bmad", "hodgkin", "tnk", "pc", "inm", "hist")}
    for i in list(res):                                   # genéricos que ya tienen un hijo concreto
        cub = ops[i].get("cubre")
        if not cub:
            continue
        cub = (neoplasicos - {i, "hem_malig", "lpa"}) if cub == ["*"] else set(cub)
        if any(c in res and c != i for c in cub):
            res.discard(i)
    if "tph" in res and (res & neoplasicos):                 # «trasplante» en un ensayo de mieloma/LMA describe el tratamiento, no una complicación
        res.discard("tph")
    if "lb" in res and ({"lla_b", "lla"} & res) and not ({"llc", "lcm", "lf", "lbdcg", "lpsnc", "lzm", "wm"} & res):
        res.discard("lb")                                 # «B-cell» de una LLA-B no es un linfoma B
    if res - {"anemia"} and "anemia" in res:              # «anemia» solo como último recurso
        res.discard("anemia")
    if not res:
        res = {"sin"}
    orden = [x[0] for x in E]
    return sorted(res, key=orden.index)

def meta_taxonomia():
    """Estructura para la web: grupos y entidades con su etiqueta y lo que abarcan los genéricos."""
    neoplasicos = [x[0] for x in E if x[1] in ("nmp", "masto", "smd", "lma", "lla", "bmad", "hodgkin", "tnk", "pc", "inm", "hist")]
    ents = []
    for i, g, lab, rx, abbr, op in E:
        cub = op.get("cubre")
        if cub == ["*"]:
            cub = [n for n in neoplasicos if n not in ("lnh", "lpa")]   # la LPA es un tratamiento aparte: los ensayos de LMA la suelen excluir
        ents.append({"id": i, "g": g, "n": lab, **({"c": cub} if cub else {})})
    return {"grupos": [{"id": g, "n": n, "t": t} for g, n, t in GRUPOS], "entidades": ents}
