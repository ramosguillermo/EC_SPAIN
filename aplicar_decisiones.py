#!/usr/bin/env python3
"""Vuelca revision/decisiones.json en los archivos de correcciones manuales de datos/ (idempotente).
Uso: python aplicar_decisiones.py [--datos carpeta]"""
import argparse, csv, json, sys
from pathlib import Path

D = Path(__file__).parent
ap = argparse.ArgumentParser(); ap.add_argument("--datos", default=str(D / "datos")); ap.add_argument("--decisiones", default=str(D / "revision/decisiones.json"))
A = ap.parse_args(); DATOS = Path(A.datos)

def upsert(nombre, cols, clave, fila):
    """Añade o actualiza una fila de un CSV (separador ';'). clave = columnas que identifican la fila."""
    f = DATOS / nombre
    filas, cab = [], cols
    if f.exists():
        r = csv.DictReader(f.open(encoding="utf-8-sig"), delimiter=";"); cab = r.fieldnames or cols; filas = list(r)
    for c in cols:
        if c not in cab: cab = list(cab) + [c]
    for x in filas:
        if all((x.get(k) or "") == (fila.get(k) or "") for k in clave):
            x.update({k: v for k, v in fila.items()}); break
    else:
        filas.append({c: fila.get(c, "") for c in cab})
    with f.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cab, delimiter=";", extrasaction="ignore"); w.writeheader()
        for x in filas: w.writerow({c: x.get(c, "") for c in cab})

def aplica(d):
    t, acc, v, ref = d["tipo"], d["accion"], d.get("valor", ""), d.get("ref") or {}
    if acc in ("ok", "visto", "distintos") and t not in ("promotor_union", "investigador"):
        return
    if t in ("nuevo", "dudoso_hematologia"):
        if acc in ("incluir", "excluir"):
            upsert("revision_manual.csv", ["identificador", "titulo", "decision"], ["identificador"],
                   {"identificador": ref["identificador"], "titulo": ref.get("titulo", ""), "decision": acc})
    elif t == "clasificacion" and acc == "cambiar":
        upsert("clasificacion_manual.csv", ["identificador", "entidades"], ["identificador"],
               {"identificador": ref["identificador"], "entidades": "|".join(v) if isinstance(v, list) else v})
    elif t == "nombre":
        if acc == "corregir": upsert("nombres_manual.csv", ["identificador", "nombre"], ["identificador"], {"identificador": ref["identificador"], "nombre": v})
        elif acc == "sin_nombre": upsert("nombres_manual.csv", ["identificador", "nombre"], ["identificador"], {"identificador": ref["identificador"], "nombre": ""})
    elif t == "reclutamiento" and acc in ("abierto", "no_recluta", "cerrado"):
        upsert("reclutamiento_manual.csv", ["identificador", "estado"], ["identificador"], {"identificador": ref["identificador"], "estado": acc})
    elif t == "promotor_tipo" and acc.startswith("tipo:"):
        for var in ref.get("variantes", []):
            upsert("promotores_manual.csv", ["promotor", "canonico", "tipo"], ["promotor"], {"promotor": var, "canonico": ref["canonico"], "tipo": acc[5:]})
    elif t == "promotor_union" and acc in ("unir_a", "unir_b"):
        c = ref["a"] if acc == "unir_a" else ref["b"]
        for var in (ref["a"], ref["b"]):
            upsert("promotores_manual.csv", ["promotor", "canonico", "tipo"], ["promotor"], {"promotor": var, "canonico": c, "tipo": ""})
    elif t == "investigador":
        if acc in ("unir_a", "unir_b"):
            c = ref["a"] if acc == "unir_a" else ref["b"]
            for var in (ref["a"], ref["b"]):
                upsert("investigadores_manual.csv", ["variante", "canonico"], ["variante"], {"variante": var, "canonico": c})
        elif acc == "distintos" and "a" in ref:
            upsert("investigadores_separar.csv", ["a", "b"], ["a", "b"], {"a": ref["a"], "b": ref["b"]})
        elif acc == "separar":
            vs = sorted(ref.get("variantes", []), key=len)
            for i in range(len(vs)):
                for j in range(i + 1, len(vs)):
                    upsert("investigadores_separar.csv", ["a", "b"], ["a", "b"], {"a": vs[i], "b": vs[j]})
    elif t == "hospital" and acc == "coordenadas":
        try:
            lat, lon = [x.strip().replace(",", ".") for x in str(v).replace(";", ",").split(",")[:2]] if str(v).count(",") == 1 else str(v).split()
            float(lat); float(lon)
        except Exception:
            print("  coordenadas no válidas:", ref.get("hospital_id"), v, file=sys.stderr); return
        upsert("hospitales_manual.csv", ["hospital_id", "nombre", "lat", "lon", "fusionar_con"], ["hospital_id"], {"hospital_id": ref["hospital_id"], "lat": lat, "lon": lon})

def main():
    f = Path(A.decisiones)
    if not f.exists():
        print("Sin decisiones que aplicar."); return
    ds = json.loads(f.read_text(encoding="utf-8")).get("decisiones", [])
    for d in ds: aplica(d)
    print(f"{len(ds)} decisiones aplicadas a {DATOS}")

if __name__ == "__main__":
    main()
