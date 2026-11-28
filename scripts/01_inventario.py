"""
Paso 1 · Inventario de fotos de la cámara dIAra en la Escuela Barrio Limoncito.

Fuente: carpeta pública de la CGR en Google Drive
"2025-2026 Escuela Barrio Limoncito, Limón"
https://drive.google.com/drive/folders/1m878MoosJ0GY_Agkh0dBenwX-S7LTCAK
  -> acceso directo a "diara_limoncito" (id 1w6fWxTcVRGztNyb7f1TNcPwR2iOijZTr), que contiene:
     imagenes_tratadas/AAAA-MM-DD/*.jpg   (sep-2025 a abr-2026, ya preprocesadas por la CGR)
     AAAA-MM-DD/*.jpg                     (abr-2026 en adelante, fotos crudas de la cámara)

Salida: data/limoncito/inventario_fotos.csv  (una fila por foto, con su id de Drive y fecha-hora)

No descarga fotos: solo lista la carpeta completa (~75 s). Cada vez que se corre, aparecen las
carpetas nuevas que haya subido la cámara.
"""
import csv
import re
import time
from datetime import datetime
from pathlib import Path

import gdown

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "limoncito"
CARPETA_DRIVE = "1w6fWxTcVRGztNyb7f1TNcPwR2iOijZTr"

# Los nombres de archivo traen la fecha y la hora de captura en tres formatos distintos.
PATRONES = [
    re.compile(r"^(?P<f>\d{8})-(?P<h>\d{6})\.jpe?g$", re.I),                   # 20260216-071816.jpg
    re.compile(r"^IMG_CAM_\d+_(?P<f>\d{8})_(?P<h>\d{6})\.jpe?g$", re.I),      # IMG_CAM_01_20260515_070908.jpg
    re.compile(r"^IMG_(?P<h>\d{2}-\d{2}-\d{2})(?: \(\d+\))?\.jpe?g$", re.I),  # IMG_07-55-26.jpg (fecha = carpeta)
]
FECHA_CARPETA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fecha_hora(nombre: str, fecha_carpeta: str):
    """Devuelve (fecha ISO, hora HH:MM:SS) a partir del nombre del archivo."""
    for p in PATRONES:
        m = p.match(nombre)
        if not m:
            continue
        h = m.group("h").replace("-", "")
        f = m.groupdict().get("f")
        fecha = datetime.strptime(f, "%Y%m%d").date().isoformat() if f else fecha_carpeta
        return fecha, f"{h[0:2]}:{h[2:4]}:{h[4:6]}"
    return fecha_carpeta, ""


def listar_drive():
    for intento in range(3):
        try:
            return gdown.download_folder(id=CARPETA_DRIVE, skip_download=True, quiet=True)
        except Exception as e:  # noqa: BLE001
            print(f"reintento {intento + 1}: {e}")
            time.sleep(10)
    raise RuntimeError("No se pudo listar la carpeta de Drive")


def main():
    DATOS.mkdir(parents=True, exist_ok=True)
    filas = []
    for item in listar_drive():
        partes = item.path.split("/")
        nombre = partes[-1]
        carpeta = next((p for p in partes[:-1] if FECHA_CARPETA.match(p)), None)
        if not carpeta or not nombre.lower().endswith((".jpg", ".jpeg")):
            continue  # control.csv, carpeta "Pruebas", etc.
        fecha, hora = fecha_hora(nombre, carpeta)
        filas.append({
            "fecha": fecha, "hora": hora, "archivo": nombre, "drive_id": item.id,
            "origen": "imagenes_tratadas" if partes[0] == "imagenes_tratadas" else "crudas",
            "carpeta": carpeta,
        })

    # Una misma foto puede estar en dos carpetas: se queda la de imagenes_tratadas.
    vistos, unicas = set(), []
    for f in sorted(filas, key=lambda r: (r["fecha"], r["hora"], r["origen"] != "imagenes_tratadas")):
        clave = (f["fecha"], f["hora"])
        if f["hora"] and clave in vistos:
            continue
        vistos.add(clave)
        unicas.append(f)

    salida = DATOS / "inventario_fotos.csv"
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(unicas[0].keys()))
        w.writeheader()
        w.writerows(unicas)
    print(f"Listo: {len(unicas)} fotos únicas ({len(filas) - len(unicas)} duplicadas), "
          f"del {unicas[0]['fecha']} al {unicas[-1]['fecha']} -> {salida}")


if __name__ == "__main__":
    main()
