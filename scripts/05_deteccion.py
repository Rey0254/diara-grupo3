"""
Paso 5 · Detección de personas y vehículos con un modelo abierto (YOLO11s, gratuito, corre en CPU).
El modelo se convierte a OpenVINO la primera vez (~0,4 s por foto en lugar de ~1,3 s, con los mismos resultados).

Entrada : data/limoncito/calidad_fotos.csv + data/limoncito/fotos/
Salida  : data/limoncito/deteccion_fotos.csv   (una fila por foto usable)

Detalles:
- Procesa las fotos usables y también las "borrosas" (lente empañado). En las borrosas, ver personas
  sí es evidencia de trabajo, pero no verlas no prueba nada (regla asimétrica, ver paso 6).
  No se usa una versión "mejorada" de la foto: en pruebas, mejorar el contraste o quitar la neblina
  bajó las detecciones (4 de 20 fotos con personas en la original contra 1 o 2 en las mejoradas).
- Si la foto está invertida, la gira 180°.
- Las personas en estas fotos son muy pequeñas (la cámara está lejos), así que la foto se divide
  en 6 partes (3x2, con 20 % de traslape), se detecta en cada parte y se unen los resultados.
  Con la foto completa, el modelo veía muchas menos personas.
- Guarda el avance en un caché, así que si se interrumpe se puede volver a correr y sigue donde quedó.

Clases COCO usadas: 0 persona, 2 auto, 7 camión (incluye vagonetas y camiones mixer).
El modelo genérico NO conoce grúas, excavadoras ni equipo de seguridad: eso viene de Gemini (paso 4).
"""
import csv
import json
import time
from pathlib import Path

import cv2
import torch
import torchvision
from ultralytics import YOLO

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "limoncito"
CACHE = DATOS / "cache_deteccion.jsonl"
MODELO = "yolo11s.pt"
MODELO_RAPIDO = RAIZ / "yolo11s_openvino_model"  # mismo modelo convertido a OpenVINO: ~3 veces más rápido en CPU
CONF = 0.15
MOSAICO = (3, 2)
TRASLAPE = 0.2
CLASES = {0: "persona", 2: "auto", 7: "camion"}


def detectar(modelo, img):
    alto, ancho = img.shape[:2]
    nx, ny = MOSAICO
    tw, th = int(ancho / nx * (1 + TRASLAPE)), int(alto / ny * (1 + TRASLAPE))
    partes, origenes = [], []
    for i in range(nx):
        for j in range(ny):
            x0, y0 = min(int(i * ancho / nx), ancho - tw), min(int(j * alto / ny), alto - th)
            partes.append(img[y0:y0 + th, x0:x0 + tw])
            origenes.append((x0, y0))
    cajas = {c: ([], []) for c in CLASES}
    for res, (x0, y0) in zip(modelo.predict(partes, imgsz=640, conf=CONF, classes=list(CLASES), verbose=False), origenes):
        for b, conf, cls in zip(res.boxes.xyxy.tolist(), res.boxes.conf.tolist(), res.boxes.cls.tolist()):
            cajas[int(cls)][0].append([b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0])
            cajas[int(cls)][1].append(conf)
    salida = {}
    for c, nombre in CLASES.items():
        b, s = cajas[c]
        if not b:
            salida[nombre], salida[f"conf_{nombre}"] = 0, ""
            continue
        keep = torchvision.ops.nms(torch.tensor(b), torch.tensor(s), 0.4)
        confs = [s[k] for k in keep.tolist()]
        salida[nombre], salida[f"conf_{nombre}"] = len(confs), round(max(confs), 3)
    return salida


def main():
    torch.set_num_threads(max(1, torch.get_num_threads()))
    hechas = {}
    if CACHE.exists():
        for linea in CACHE.read_text().splitlines():
            r = json.loads(linea)
            hechas[r["archivo"]] = r
    fotos = [f for f in csv.DictReader(open(DATOS / "calidad_fotos.csv", encoding="utf-8"))
             if f["usable"] == "sí" or f["motivo"] == "borrosa"]
    # Primero las usables, después las borrosas.
    fotos.sort(key=lambda f: f["usable"] != "sí")
    pendientes = [f for f in fotos if f["archivo"] not in hechas]
    print(f"{len(fotos)} fotos a procesar (usables + borrosas), {len(pendientes)} pendientes", flush=True)
    if not MODELO_RAPIDO.exists():
        exportado = YOLO(MODELO).export(format="openvino", imgsz=640, batch=6)
        Path(exportado).rename(MODELO_RAPIDO)
    modelo = YOLO(str(MODELO_RAPIDO), task="detect")
    t0 = time.time()
    with open(CACHE, "a", encoding="utf-8") as cache:
        for n, f in enumerate(pendientes, 1):
            img = cv2.imread(str(DATOS / "fotos" / f["fecha"] / f["archivo"]))
            if img is None:
                continue
            if f["orientacion"] == "invertida":
                img = cv2.rotate(img, cv2.ROTATE_180)
            r = {"archivo": f["archivo"], "fecha": f["fecha"], "hora": f["hora"], **detectar(modelo, img)}
            cache.write(json.dumps(r) + "\n")
            hechas[f["archivo"]] = r
            if n % 200 == 0:
                cache.flush()
                print(f"{n}/{len(pendientes)} · {(time.time() - t0) / n:.2f} s/foto", flush=True)
    campos = ["fecha", "hora", "archivo", "persona", "conf_persona", "camion", "conf_camion", "auto", "conf_auto"]
    filas = sorted(hechas.values(), key=lambda r: (r["fecha"], r["hora"]))
    with open(DATOS / "deteccion_fotos.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    print(f"Listo: {len(filas)} fotos con detección -> {DATOS / 'deteccion_fotos.csv'}")


if __name__ == "__main__":
    main()
