"""
Paso 2 · Descarga de las fotos listadas en el inventario.

Entrada : data/limoncito/inventario_fotos.csv
Salida  : data/limoncito/fotos/AAAA-MM-DD/<archivo>.jpg   (NO se sube al repositorio; ver .gitignore)

Descarga desde la carpeta pública de la CGR en Google Drive. Solo baja lo que falta,
así que sirve tanto para la carga inicial como para las actualizaciones diarias.
"""
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "limoncito"
FOTOS = DATOS / "fotos"
URL = "https://drive.usercontent.google.com/download?id={id}&export=download"


def bajar(fila, sesion):
    destino = FOTOS / fila["fecha"] / fila["archivo"]
    if destino.exists() and destino.stat().st_size > 1000:
        return "existe"
    destino.parent.mkdir(parents=True, exist_ok=True)
    for intento in range(4):
        try:
            r = sesion.get(URL.format(id=fila["drive_id"]), timeout=60)
            if r.ok and r.headers.get("content-type", "").startswith("image/"):
                destino.write_bytes(r.content)
                return "ok"
        except requests.RequestException:
            pass
        time.sleep(2 * (intento + 1))
    return "error"


def main(hilos=8):
    filas = list(csv.DictReader(open(DATOS / "inventario_fotos.csv", encoding="utf-8")))
    sesion = requests.Session()
    conteo = {"ok": 0, "existe": 0, "error": 0}
    errores = []
    with ThreadPoolExecutor(hilos) as ex:
        futuros = {ex.submit(bajar, f, sesion): f for f in filas}
        for n, fut in enumerate(as_completed(futuros), 1):
            res = fut.result()
            conteo[res] += 1
            if res == "error":
                errores.append(futuros[fut]["drive_id"])
            if n % 500 == 0:
                print(f"{n}/{len(filas)} {conteo}", flush=True)
    print(f"Listo: {conteo}")
    if errores:
        (DATOS / "descarga_errores.txt").write_text("\n".join(errores))
        sys.exit(1)


if __name__ == "__main__":
    main()
