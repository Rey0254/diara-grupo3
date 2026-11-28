"""
Paso 4 · Descarga del análisis de Gemini que la CGR publica en obrapublica.info (Escuela de Limoncito).

Fuente : https://www.obrapublica.info/static/limoncito/data/
Salida : data/limoncito/gemini/manifest.json
         data/limoncito/gemini/AAAAMMDD.json        (análisis por foto)
         data/limoncito/gemini/AAAAMMDD.txt         (resumen del día)
         data/limoncito/gemini_fotos.csv            (una fila por foto, aplanado)
"""
import csv
import json
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "limoncito"
DESTINO = DATOS / "gemini"
BASE = "https://www.obrapublica.info/static/limoncito/data/"


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    manifest = s.get(BASE + "json/manifest.json", timeout=30).json()
    (DESTINO / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    filas = []
    for d in manifest["dates"]:
        j = DESTINO / f"{d}.json"
        if not j.exists():
            j.write_text(s.get(f"{BASE}json/{d}/index.json", timeout=30).text)
        t = DESTINO / f"{d}.txt"
        if not t.exists():
            r = s.get(f"{BASE}resumenes/{d}.txt", timeout=30)
            if r.ok:
                t.write_text(r.text)
        dia = json.loads(j.read_text())
        for im in dia.get("images", []):
            seg = im.get("seguridad_laboral") or {}
            clima = im.get("condiciones_climaticas") or {}
            h = im.get("nombre_imagen", "")[9:15]
            filas.append({
                "fecha": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                "hora": f"{h[:2]}:{h[2:4]}:{h[4:]}" if len(h) == 6 else "",
                "nombre_obrapublica": im.get("nombre_imagen", ""),
                "error": im.get("error", "") or ("" if "personas_trabajadoras" in im else "sin_analisis"),
                "personas": im.get("personas_trabajadoras", ""),
                "maquinaria": "|".join(im.get("maquinaria") or []),
                "casco": seg.get("uso_casco", ""),
                "chaleco": seg.get("uso_chaleco", ""),
                "arnes": seg.get("uso_arnes_altura", ""),
                "clima": clima.get("clima_general", ""),
                "visibilidad": clima.get("visibilidad", ""),
                "actividad": im.get("actividad_desarrollada", ""),
                "etapa": im.get("etapa_constructiva", ""),
            })
    with open(DATOS / "gemini_fotos.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    print(f"Listo: {len(manifest['dates'])} días, {len(filas)} fotos -> {DATOS / 'gemini_fotos.csv'}")


if __name__ == "__main__":
    main()
