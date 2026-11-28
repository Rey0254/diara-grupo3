"""
Paso 3 · Control de calidad de cada foto (procesamiento clásico, sin IA y sin costo).

Entrada : data/limoncito/inventario_fotos.csv + data/limoncito/fotos/
Salida  : data/limoncito/calidad_fotos.csv

Para cada foto mide:
  brillo      promedio de luminosidad (0-255). Muy bajo = noche o lente tapado.
  contraste   desviación estándar de grises. Muy bajo = imagen plana (niebla, lente tapado).
  nitidez     varianza del Laplaciano. Muy baja = borrosa o desenfocada.
  pct_quemado porcentaje de píxeles casi blancos. Muy alto = sobreexposición.
  similitud   parecido con las fotos de esa misma semana (-1 a 1). Bajo = la foto no se parece
              a las de sus días vecinos (pruebas fuera de obra, algo tapando la vista).
              Se compara con la misma semana y no con una referencia fija, porque la obra
              cambia: en oct-2025 todavía no existía el edificio que se ve en 2026.
  orientacion normal / invertida. Desde el 18-abr-2026 la cámara quedó de cabeza: si la foto
              girada 180° se parece más a la referencia, se marca "invertida" y se corrige
              (no se descarta).

Y asigna:
  usable = sí / no
  motivo = oscura | sobreexpuesta | borrosa | sin_contraste | fuera_de_encuadre | (vacío)

Los umbrales están al inicio del archivo y se documentan en documentacion/datos-automatizacion.md.
"""
import csv
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "limoncito"
FOTOS = DATOS / "fotos"

# ---- Umbrales (calibrados mirando muestras reales; ver documentación) ----
BRILLO_MIN = 40          # por debajo: noche o lente tapado
PCT_QUEMADO_MAX = 35.0   # % de píxeles casi blancos; oct-2025 llegó a ~99 %
NITIDEZ_MIN = 20.0       # nov-2025 a feb-2026 (lente empañado) quedó entre 2 y 8; el periodo nítido > 40
CONTRASTE_MIN = 18.0
SIMILITUD_MIN = 0.40     # contra la mediana de las fotos de ±3 días, ya corregida la orientación
VENTANA_DIAS = 3

# Periodo de referencia para detectar la orientación: la cámara limpia y al derecho
# (11-feb a 17-abr-2026). Si se reinstala la cámara en otra posición, hay que actualizar este rango.
REFERENCIA_DESDE, REFERENCIA_HASTA = "2026-02-11", "2026-04-17"


def descriptor(gris):
    """Huella pequeña del encuadre: 32x24 en grises, normalizada."""
    d = cv2.resize(gris, (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    d -= d.mean()
    n = np.linalg.norm(d)
    return d / n if n > 0 else d


def medir(ruta):
    img = cv2.imread(str(ruta))
    if img is None:
        return None
    h, w = img.shape[:2]
    img = cv2.resize(img, (640, int(h * 640 / w)), interpolation=cv2.INTER_AREA)
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return {
        "brillo": float(gris.mean()),
        "contraste": float(gris.std()),
        "nitidez": float(cv2.Laplacian(gris, cv2.CV_64F).var()),
        "pct_quemado": float((gris > 245).mean() * 100),
        "_desc": descriptor(gris),
        "_desc_rot": descriptor(cv2.rotate(gris, cv2.ROTATE_180)),
    }


def main():
    filas = list(csv.DictReader(open(DATOS / "inventario_fotos.csv", encoding="utf-8")))
    medidas = []
    for n, f in enumerate(filas, 1):
        m = medir(FOTOS / f["fecha"] / f["archivo"])
        medidas.append(m)
        if n % 1000 == 0:
            print(f"{n}/{len(filas)} medidas", flush=True)

    # Encuadre de referencia: la mediana de las fotos diurnas bien expuestas del periodo de referencia.
    buenas = [m["_desc"] for f, m in zip(filas, medidas)
              if m and REFERENCIA_DESDE <= f["fecha"] <= REFERENCIA_HASTA
              and m["brillo"] >= 80 and m["pct_quemado"] < 10 and m["nitidez"] >= NITIDEZ_MIN]
    ref = np.median(np.stack(buenas), axis=0)
    ref /= np.linalg.norm(ref)

    # 1) Orientación de cada foto (contra la referencia fija).
    for m in medidas:
        if m:
            m["invertida"] = float(np.dot(m["_desc_rot"], ref)) > float(np.dot(m["_desc"], ref)) + 0.2
            m["_d"] = m["_desc_rot"] if m["invertida"] else m["_desc"]

    # 2) Huella típica de cada día, con las fotos bien expuestas y nítidas.
    from collections import defaultdict
    from datetime import date, timedelta
    por_dia = defaultdict(list)
    for f, m in zip(filas, medidas):
        if m and m["brillo"] >= BRILLO_MIN and m["pct_quemado"] <= PCT_QUEMADO_MAX \
                and m["nitidez"] >= NITIDEZ_MIN and m["contraste"] >= CONTRASTE_MIN:
            por_dia[f["fecha"]].append(m["_d"])
    huella_dia = {d: np.median(np.stack(v), axis=0) for d, v in por_dia.items()}

    def referencia_semana(fecha):
        d0 = date.fromisoformat(fecha)
        vec = [huella_dia[k] for k in (str(d0 + timedelta(i)) for i in range(-VENTANA_DIAS, VENTANA_DIAS + 1))
               if k in huella_dia]
        if len(vec) < 2:
            return None
        r = np.median(np.stack(vec), axis=0)
        return r / np.linalg.norm(r)

    salida = DATOS / "calidad_fotos.csv"
    campos = ["fecha", "hora", "archivo", "drive_id", "brillo", "contraste", "nitidez",
              "pct_quemado", "similitud", "orientacion", "usable", "motivo"]
    resumen = {}
    refs = {}
    with open(salida, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for f, m in zip(filas, medidas):
            fila = {k: f[k] for k in ("fecha", "hora", "archivo", "drive_id")}
            if m is None:
                fila.update(usable="no", motivo="sin_imagen", orientacion="")
            else:
                if f["fecha"] not in refs:
                    refs[f["fecha"]] = referencia_semana(f["fecha"])
                rs = refs[f["fecha"]]
                sim = float(np.dot(m["_d"], rs)) if rs is not None else float("nan")
                if m["brillo"] < BRILLO_MIN:
                    motivo = "oscura"
                elif m["pct_quemado"] > PCT_QUEMADO_MAX:
                    motivo = "sobreexpuesta"
                elif m["contraste"] < CONTRASTE_MIN:
                    motivo = "sin_contraste"
                elif m["nitidez"] < NITIDEZ_MIN:
                    motivo = "borrosa"
                elif rs is not None and sim < SIMILITUD_MIN:
                    motivo = "fuera_de_encuadre"
                else:
                    motivo = ""
                fila.update(
                    brillo=round(m["brillo"], 1), contraste=round(m["contraste"], 1),
                    nitidez=round(m["nitidez"], 1), pct_quemado=round(m["pct_quemado"], 2),
                    similitud="" if rs is None else round(sim, 3),
                    orientacion="invertida" if m["invertida"] else "normal",
                    usable="no" if motivo else "sí", motivo=motivo,
                )
            resumen[fila["motivo"] or "usable"] = resumen.get(fila["motivo"] or "usable", 0) + 1
            w.writerow(fila)
    print("Listo:", resumen, "->", salida)


if __name__ == "__main__":
    main()
