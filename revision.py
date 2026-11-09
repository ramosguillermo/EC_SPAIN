#!/usr/bin/env python3
"""Reúne en una sola cola (web/revision/pendientes.json) todo lo que el sistema marca como dudoso,
y guarda una «foto» de los ensayos publicados (datos/snapshot.json) para detectar novedades la semana siguiente.
Las decisiones tomadas (revision/decisiones.json) suprimen su aviso mientras el contenido no cambie."""
import json, re, csv, hashlib, difflib, datetime
from pathlib import Path

D = Path(__file__).parent
DATOS = D / "datos"

def leer_ensayos():
    s = (D / "web/data/ensayos.js").read_text(encoding="utf-8")
    return json.loads(s[s.index("{"):s.rindex("}") + 1])

def h(*partes):
    return hashlib.md5("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()[:8]

def csv_filas(f):
    return list(csv.DictReader(open(f, encoding="utf-8-sig"), delimiter=";")) if Path(f).exists() else []

def construir():
    js = leer_ensayos(); E = js["ensayos"]; meta = js["meta"]
    por_id = {e["identificador"]: e for e in E}
    decis = {}
    fd = D / "revision/decisiones.json"
    if fd.exists():
        decis = {x["key"]: x for x in json.loads(fd.read_text(encoding="utf-8")).get("decisiones", [])}
    items = []
    def add(tipo, ref, prioridad, titulo, detalle, propuesta, opciones, campos=None, enlaces=None, extra=None):
        key = f"{tipo}:{ref}"
        it = {"key": key, "tipo": tipo, "prioridad": prioridad, "titulo": titulo, "detalle": detalle, "propuesta": propuesta,
              "opciones": opciones, "campos": campos or [], "enlaces": enlaces or [], "ref": extra or {}}
        it["hash"] = h(titulo, propuesta, json.dumps(extra or {}, sort_keys=True, ensure_ascii=False))
        d = decis.get(key)
        if d and d.get("hash") == it["hash"]:
            return
        items.append(it)
    reec = lambda i: {"t": "Ficha en el REec", "u": f"https://reec.aemps.es/reec/estudio/{i}"}
    nom = lambda e: (e.get("nombre") + " · " if e.get("nombre") else "") + (e.get("titulo") or e["identificador"])[:150]
    ENT = {x["id"]: x["n"] for x in meta["taxonomia"]["entidades"]}
    GEN = {x["id"] for x in meta["taxonomia"]["entidades"] if x.get("c")}

    # --- novedades respecto a la semana anterior ---
    nuevos, desaparecidos, cambios = [], [], []
    fs = DATOS / "snapshot.json"
    snap = json.loads(fs.read_text(encoding="utf-8")) if fs.exists() else None
    if snap is not None:
        for i, e in por_id.items():
            if i not in snap:
                nuevos.append(i)
                add("nuevo", i, 1, nom(e), "Ensayo nuevo desde la última actualización.",
                    "Publicado como: " + ", ".join(ENT.get(x, x) for x in e["entidades"]) + " · promotor " + (e.get("promotor_c") or ""),
                    [{"id": "ok", "label": "Es de hematología"}, {"id": "excluir", "label": "No es de hematología (quitar)"}],
                    enlaces=[reec(i)], extra={"identificador": i, "titulo": e.get("titulo", "")})
            else:
                antes = snap[i].get("recl", "reclutando"); ahora = (e.get("reclutamiento") or {}).get("estado", "reclutando")
                if antes != ahora: cambios.append((i, antes, ahora))
        desaparecidos = [i for i in snap if i not in por_id]

    # --- dudosos de hematología (la clasificación no se atreve) ---
    try:
        ids = json.loads((DATOS / "ids_hematologia.json").read_text(encoding="utf-8"))
        bus = {str(b.get("identificador")): b for b in json.loads((DATOS / "busqueda.json").read_text(encoding="utf-8"))}
        hechos = {r["identificador"]: r.get("decision", "") for r in csv_filas(DATOS / "revision_manual.csv")}
        for i in ids.get("dudosos_pendientes", []):
            if hechos.get(i): continue
            b = bus.get(i, {})
            add("dudoso_hematologia", i, 2, (b.get("titulo_es") or b.get("titulo_en") or i)[:170], "Indicación: " + str(b.get("indicacion_es") or b.get("indicacion_en") or "")[:200],
                "Coincide con términos ambiguos: no se ha incluido de forma automática.",
                [{"id": "incluir", "label": "Incluir (es hematología)"}, {"id": "excluir", "label": "Excluir"}],
                enlaces=[reec(i)], extra={"identificador": i, "titulo": (b.get("titulo_es") or "")[:200]})
    except FileNotFoundError:
        pass

    for i, e in por_id.items():
        # --- clasificación de enfermedad dudosa ---
        ents = e["entidades"]
        if not e.get("entidades_manual") and (ents == ["sin"] or all(x in GEN or x in ("sin", "otro") for x in ents)):
            add("clasificacion", i, 2, nom(e), "Indicación REec: " + str(e.get("indicacion", ""))[:200],
                "Asignado: " + (", ".join(ENT.get(x, x) for x in ents) or "ninguna") + (" (el registro solo da la enfermedad de forma general)" if ents != ["sin"] else " (no se reconoce la enfermedad)"),
                [{"id": "ok", "label": "Correcto"}, {"id": "cambiar", "label": "Cambiar enfermedades", "input": "entidades"}],
                enlaces=[reec(i)], extra={"identificador": i})
        # --- nombre detectado automáticamente ---
        if e.get("nombre_fuente") == "detectado" and e.get("nombre_tipo") == "nombre":
            add("nombre", i, 3, nom(e), "Título: " + str(e.get("titulo", ""))[:200], "Nombre detectado en el título: «" + e["nombre"] + "»",
                [{"id": "ok", "label": "Correcto"}, {"id": "corregir", "label": "Corregir nombre", "input": "texto"}, {"id": "sin_nombre", "label": "No es un nombre"}],
                enlaces=[reec(i)], extra={"identificador": i, "nombre": e["nombre"]})
        # --- reclutamiento: fuentes que discrepan ---
        r = e.get("reclutamiento")
        if r and (r["estado"] == "dudoso" or not any(m.startswith("REec") for m in r["motivos"])):
            add("reclutamiento", i, 2, nom(e), "Estado en el REec: " + str(e.get("estado")),
                "Los registros discrepan: " + "; ".join(r["motivos"]),
                [{"id": "abierto", "label": "Reclutando"}, {"id": "no_recluta", "label": "En seguimiento, sin reclutar"}, {"id": "cerrado", "label": "Cerrado (retirar)"}],
                enlaces=[reec(i)] + ([{"t": "ClinicalTrials.gov", "u": "https://clinicaltrials.gov/study/" + e["nct"]}] if e.get("nct") else []),
                extra={"identificador": i})
        # --- sin criterios ---
        if not e["criterios"]["inc"] and not e["criterios"]["exc"]:
            add("sin_criterios", i, 3, nom(e), "No hay criterios de inclusión/exclusión en REec, CTIS ni ClinicalTrials.gov.", "Se enlaza a CTIS desde la ficha.",
                [{"id": "ok", "label": "Visto"}], enlaces=[reec(i)] + ([{"t": "CTIS", "u": e["ctis"]}] if e.get("ctis") else []), extra={"identificador": i})
    for x in csv_filas(DATOS / "reclutamiento_revision.csv"):
        if x["estado"] == "cerrado" and x["identificador"] not in por_id:
            add("reclutamiento", x["identificador"], 3, (x["nombre"] + " · " if x["nombre"] else "") + x["titulo"][:150], "Retirado de la web por cierre.",
                "Motivos: " + x["motivos"],
                [{"id": "cerrado", "label": "Confirmar cierre"}, {"id": "abierto", "label": "Mantener (reclutando)"}, {"id": "no_recluta", "label": "Mantener (en seguimiento)"}],
                enlaces=[reec(x["identificador"])], extra={"identificador": x["identificador"]})

    # --- promotores e investigadores ---
    fdu = DATOS / "dudas.json"
    if fdu.exists():
        du = json.loads(fdu.read_text(encoding="utf-8"))
        TIPOS = [{"id": "industria", "label": "Industria"}, {"id": "academico", "label": "Hospital / universidad"}, {"id": "cooperativo", "label": "Grupo cooperativo"}]
        for p in du["promotores"]:
            if p["origen"] == "auto" and p["tipo"] != "industria":
                add("promotor_tipo", p["canonico"], 3, p["canonico"], "Aparece en el REec como: " + "; ".join(p["variantes"]),
                    "Tipo asignado automáticamente: " + p["tipo"],
                    [{"id": "ok", "label": "Correcto"}] + [{"id": "tipo:" + t["id"], "label": "Es " + t["label"].lower()} for t in TIPOS if t["id"] != p["tipo"]],
                    extra={"canonico": p["canonico"], "variantes": p["variantes"]})
        canons = sorted(du["promotores"], key=lambda x: x["canonico"])
        for a in range(len(canons)):
            for b in range(a + 1, len(canons)):
                x, y = canons[a], canons[b]
                if "auto" not in (x["origen"], y["origen"]): continue
                nx, ny = re.sub(r"[^a-z0-9 ]", "", x["canonico"].lower()), re.sub(r"[^a-z0-9 ]", "", y["canonico"].lower())
                if difflib.SequenceMatcher(None, nx, ny).ratio() > .86 or (len(nx) > 5 and (nx in ny or ny in nx)):
                    add("promotor_union", x["canonico"] + "|" + y["canonico"], 2, x["canonico"] + "  ⇄  " + y["canonico"], "¿Son el mismo promotor?",
                        "Nombres muy parecidos en el REec.",
                        [{"id": "unir_a", "label": "Unir como «" + x["canonico"] + "»"}, {"id": "unir_b", "label": "Unir como «" + y["canonico"] + "»"}, {"id": "distintos", "label": "Son distintos"}],
                        extra={"a": x["canonico"], "b": y["canonico"], "variantes_a": x["variantes"], "variantes_b": y["variantes"], "tipo_a": x["tipo"], "tipo_b": y["tipo"]})
        for d in du["investigadores"]:
            if d["tipo"] == "duplicado":
                add("investigador", "dup:" + "|".join(d["variantes"]), 2, " ⇄ ".join(d["variantes"]), "Mismo hospital, mismo apellido: ¿es la misma persona?",
                    "Aparecen como investigadores distintos.",
                    [{"id": "unir_a", "label": "Unir como «" + d["variantes"][0] + "»"}, {"id": "unir_b", "label": "Unir como «" + d["variantes"][1] + "»"}, {"id": "distintos", "label": "Son distintos"}],
                    extra={"a": d["variantes"][0], "b": d["variantes"][1]})
            else:
                add("investigador", "fus:" + d["canonico"], 3, d["canonico"], "Variantes unidas en una sola persona: " + "; ".join(d["variantes"]),
                    "Se han fusionado porque un nombre es parte del otro en el mismo hospital.",
                    [{"id": "ok", "label": "Correcto"}, {"id": "separar", "label": "Hay personas distintas"}],
                    extra={"canonico": d["canonico"], "variantes": d["variantes"]})

    # --- hospitales con coordenadas dudosas ---
    fi = DATOS / "informe_fusion.txt"
    if fi.exists():
        hs = {r["hospital_id"]: r for r in csv_filas(DATOS / "hospitales.csv")}
        for m in re.finditer(r"\*\s+(\d+) m \| (\S+) \|", fi.read_text(encoding="utf-8")):
            dist, hid = int(m.group(1)), m.group(2)
            if dist < 2000: continue
            r = hs.get(hid) or next((v for k, v in hs.items() if k.startswith(hid)), None)
            if not r: continue
            add("hospital", r["hospital_id"], 2, r["nombre"], f"Las variantes del REec sitúan este hospital a hasta {dist} m unas de otras.",
                f"Coordenadas actuales: {r['lat']}, {r['lon']}",
                [{"id": "ok", "label": "Bien situado"}, {"id": "coordenadas", "label": "Corregir coordenadas", "input": "coordenadas"}],
                enlaces=[{"t": "Ver en el mapa", "u": f"https://www.openstreetmap.org/?mlat={r['lat']}&mlon={r['lon']}#map=17/{r['lat']}/{r['lon']}"}],
                extra={"hospital_id": r["hospital_id"], "nombre": r["nombre"]})

    items.sort(key=lambda x: (x["prioridad"], x["tipo"], x["titulo"]))
    # foto para la próxima semana
    snap_nuevo = {i: {"recl": (e.get("reclutamiento") or {}).get("estado", "reclutando"), "nombre": e.get("nombre", "")} for i, e in por_id.items()}
    return items, meta, {"nuevos": nuevos, "desaparecidos": desaparecidos, "cambios": cambios, "primera_vez": snap is None, "total": len(por_id)}, snap_nuevo, E

def main():
    items, meta, nov, snap, E = construir()
    out = D / "web/revision"; out.mkdir(parents=True, exist_ok=True)
    tax = [{"id": x["id"], "n": x["n"]} for x in meta["taxonomia"]["entidades"]]
    (out / "pendientes.json").write_text(json.dumps({"generado": datetime.date.today().isoformat(), "items": items, "entidades": tax}, ensure_ascii=False), encoding="utf-8")
    (DATOS / "snapshot.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    nombre = {e["identificador"]: (e.get("nombre") or e["identificador"]) for e in E}
    cuenta = {}
    for it in items: cuenta[it["tipo"]] = cuenta.get(it["tipo"], 0) + 1
    L = [f"## Actualización de ensayos — {datetime.date.today().strftime('%d/%m/%Y')}", "", f"- **{nov['total']}** ensayos publicados."]
    if nov["primera_vez"]:
        L.append("- Primera ejecución: se ha guardado el punto de partida para detectar novedades desde la próxima semana.")
    else:
        L += [f"- **{len(nov['nuevos'])}** ensayos nuevos" + (": " + ", ".join(nombre[i] for i in nov["nuevos"][:15]) if nov["nuevos"] else ""),
              f"- **{len(nov['desaparecidos'])}** ya no figuran (cerrados o retirados)" + (": " + ", ".join(nov["desaparecidos"][:10]) if nov["desaparecidos"] else ""),
              f"- **{len(nov['cambios'])}** han cambiado de estado de reclutamiento" + (": " + ", ".join(f"{nombre.get(i, i)} ({a}→{b})" for i, a, b in nov["cambios"][:10]) if nov["cambios"] else "")]
    L += ["", f"### Pendiente de revisar: {len(items)}", ""] + [f"- {t}: {n}" for t, n in sorted(cuenta.items(), key=lambda x: -x[1])]
    (DATOS / "novedades.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))

if __name__ == "__main__":
    main()
