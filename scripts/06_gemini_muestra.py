"""
Paso 6 · Análisis con Gemini (modelo por tokens) de una MUESTRA de fotos usables.

Por qué una muestra: el modelo abierto (paso 5) revisa todas las fotos gratis; Gemini aporta el
detalle que el modelo abierto no ve (casco, chaleco, maquinaria específica, etapa constructiva),
pero cuesta tokens. Se usa el mismo muestreo que la CGR en obrapublica.info:
5 fotos por día (2 en la mañana, de 7 a 12; 3 en la tarde, de 12 a 16), solo fotos que pasaron el
control de calidad (paso 3) y solo en días que la CGR no analizó (desde el 18-abr-2026).

Requiere la variable de entorno GEMINI_API_KEY (en GitHub: secreto del repositorio). La clave
NUNCA va en el código.

Entrada : data/limoncito/calidad_fotos.csv, data/limoncito/gemini_fotos.csv (lo que ya hizo la CGR)
Salida  : data/limoncito/gemini_grupo3/AAAAMMDD.json   (mismo formato que obrapublica.info)
          data/limoncito/gemini_uso_tokens.csv         (tokens reales por foto, para medir el costo)
"""
import base64
import csv
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import requests

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "limoncito"
SALIDA = DATOS / "gemini_grupo3"
USO = DATOS / "gemini_uso_tokens.csv"

# gemini-2.5-* ya no está disponible para claves nuevas (responde 404); Google recomienda 3.5 Flash-Lite
# para proyectos nuevos, y es el modelo más barato con nivel gratuito.
MODELO = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
DESDE = os.environ.get("GEMINI_DESDE", "2026-04-18")
FOTOS_MANANA, FOTOS_TARDE = 2, 3
URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

INSTRUCCION = """Sos un analista de fiscalización de obra pública. Analizá esta foto de la cámara de monitoreo
de la construcción de la Escuela de Limoncito (Limón, Costa Rica). Respondé SOLO con un JSON con esta estructura:
{
 "maquinaria": [lista de maquinaria o equipo visible, en español, sin tildes, p. ej. "Grua torre", "Camion mixer"],
 "personas_trabajadoras": número entero de personas visibles (0 si no se ve ninguna),
 "seguridad_laboral": {"uso_casco": "Si"|"No"|"Parcial"|"No determinable",
                       "uso_chaleco": "Si"|"No"|"Parcial"|"No determinable",
                       "uso_arnes_altura": "Si"|"No"|"Parcial"|"No determinable"|"No aplica",
                       "observaciones": texto corto},
 "actividad_desarrollada": texto corto,
 "condiciones_climaticas": {"clima_general": "Despejado"|"Parcialmente nublado"|"Nublado"|"Lluvioso"|"No determinable",
                            "visibilidad": "Buena"|"Regular"|"Mala"},
 "etapa_constructiva": texto corto,
 "certeza": "Alta"|"Media"|"Baja"
}
Si la imagen no permite ver con claridad, decilo en "certeza" y no inventes conteos."""


def elegir_muestra():
    ya = {r["fecha"] for r in csv.DictReader(open(DATOS / "gemini_fotos.csv", encoding="utf-8"))}
    por_dia = defaultdict(list)
    for f in csv.DictReader(open(DATOS / "calidad_fotos.csv", encoding="utf-8")):
        if f["usable"] == "sí" and f["fecha"] >= DESDE and f["fecha"] not in ya and f["hora"]:
            por_dia[f["fecha"]].append(f)
    muestra = []
    for dia, fotos in sorted(por_dia.items()):
        manana = [f for f in fotos if "07" <= f["hora"][:2] < "12"]
        tarde = [f for f in fotos if "12" <= f["hora"][:2] < "16"]
        for grupo, n in ((manana, FOTOS_MANANA), (tarde, FOTOS_TARDE)):
            if grupo:  # fotos repartidas a lo largo del bloque
                paso = len(grupo) / n
                muestra += [grupo[int(paso * i + paso / 2)] for i in range(min(n, len(grupo)))]
    return muestra


class CuotaAgotada(Exception):
    """El nivel gratuito de Gemini llegó a su límite: se sigue en la próxima ejecución."""


class ErrorDeConsulta(Exception):
    """Gemini rechazó la consulta (se guarda el mensaje completo para poder diagnosticar)."""


class ErrorDeConfiguracion(Exception):
    """Modelo inexistente, clave inválida o sin permiso: no tiene sentido seguir con las demás fotos."""


CONFIG_COMPLETA = {"responseMimeType": "application/json", "temperature": 0.2,
                   "thinkingConfig": {"thinkingBudget": 0}}
CONFIG_MINIMA = {"responseMimeType": "application/json"}
config_actual = dict(CONFIG_COMPLETA)


def analizar(foto, clave, sesion):
    global config_actual
    img = cv2.imread(str(DATOS / "fotos" / foto["fecha"] / foto["archivo"]))
    if foto["orientacion"] == "invertida":
        img = cv2.rotate(img, cv2.ROTATE_180)
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cuerpo = {
        "contents": [{"parts": [
            {"text": INSTRUCCION},
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpg.tobytes()).decode()}},
        ]}],
        "generationConfig": dict(config_actual),
    }
    for intento in range(6):
        r = sesion.post(URL.format(modelo=MODELO), json=cuerpo, timeout=120,
                        headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
        if r.status_code == 429 and "PerDay" in r.text:
            raise CuotaAgotada(r.text[:200])
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(15 * (intento + 1))
            continue
        if r.status_code == 400 and len(cuerpo["generationConfig"]) > 1 and "API key" not in r.text:
            # Los modelos Gemini 3 no aceptan algunos parámetros de los 2.5 (p. ej. thinkingBudget):
            # se reintenta una vez con la configuración mínima y se deja constancia en el log.
            print(f"Gemini 400 con la configuración completa; se reintenta con la mínima. Detalle: {r.text[:300]}", flush=True)
            # gemini-3.5-flash-lite responde 400 a temperature/thinkingBudget de los 2.5: desde aquí se usa
            # la configuración mínima para todas las fotos (así no se gasta una solicitud extra por foto).
            config_actual = dict(CONFIG_MINIMA)
            cuerpo["generationConfig"] = dict(config_actual)
            continue
        if r.status_code in (401, 403, 404) or (r.status_code == 400 and "API key" in r.text):
            raise ErrorDeConfiguracion(f"{r.status_code}: {r.text[:300]}")
        if r.status_code >= 400:
            raise ErrorDeConsulta(f"{r.status_code}: {r.text[:500]}")
        data = r.json()
        texto = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(texto), data.get("usageMetadata", {})
    raise CuotaAgotada("Gemini siguió respondiendo 429/5xx después de varios intentos")


def modelos_disponibles(clave, sesion):
    """Lista los modelos Flash que esta clave puede usar (sirve para diagnosticar un 400/404)."""
    try:
        r = sesion.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                       headers={"x-goog-api-key": clave}, timeout=30)
        nombres = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                   if "generateContent" in m.get("supportedGenerationMethods", [])]
        return [n for n in nombres if "flash" in n]
    except Exception as e:  # noqa: BLE001
        return [f"(no se pudo listar: {e})"]


def main():
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        sys.exit("Falta GEMINI_API_KEY (configurarla como secreto del repositorio en GitHub).")
    SALIDA.mkdir(parents=True, exist_ok=True)
    muestra = elegir_muestra()
    hechos = set()
    if USO.exists():
        # Las filas sin tokens fueron errores: se reintentan.
        hechos = {r["archivo"] for r in csv.DictReader(open(USO, encoding="utf-8")) if r["tokens_entrada"]}
    pendientes = [f for f in muestra if f["archivo"] not in hechos]
    print(f"Muestra: {len(muestra)} fotos en {len({f['fecha'] for f in muestra})} días; pendientes: {len(pendientes)}")
    sesion = requests.Session()
    print(f"Modelo: {MODELO}. Modelos Flash disponibles para esta clave: {', '.join(modelos_disponibles(clave, sesion))}")
    rechazos_seguidos = 0
    nuevo = not USO.exists()
    with open(USO, "a", newline="", encoding="utf-8") as fu:
        wu = csv.writer(fu)
        if nuevo:
            wu.writerow(["fecha", "hora", "archivo", "modelo", "tokens_entrada", "tokens_salida", "segundos"])
        for n, f in enumerate(pendientes, 1):
            t0 = time.time()
            try:
                res, uso = analizar(f, clave, sesion)
                res = {"nombre_imagen": f["archivo"], "fecha_hora": f"{f['fecha']} {f['hora']}", **res}
            except CuotaAgotada as e:
                print(f"Se alcanzó el límite gratuito de Gemini ({n - 1} fotos hoy). Se continúa en la próxima ejecución. {e}")
                break
            except ErrorDeConfiguracion as e:
                print(f"Gemini rechazó la consulta por configuración (modelo {MODELO}), no por la foto. "
                      f"Se detiene sin marcar fotos como no analizables. Detalle: {e}")
                break
            except ErrorDeConsulta as e:
                rechazos_seguidos += 1
                print(f"Gemini rechazó {f['archivo']}: {e}", flush=True)
                if rechazos_seguidos >= 3:
                    print("Tres rechazos seguidos: el problema es la consulta, no las fotos. Se detiene aquí.")
                    break
                res, uso = {"nombre_imagen": f["archivo"], "fecha_hora": f"{f['fecha']} {f['hora']}",
                            "error": f"Imagen no analizable: {e}"}, {}
            except Exception as e:  # noqa: BLE001
                res, uso = {"nombre_imagen": f["archivo"], "fecha_hora": f"{f['fecha']} {f['hora']}",
                            "error": f"Imagen no analizable: {e}"}, {}
            else:
                rechazos_seguidos = 0
            dia = SALIDA / f"{f['fecha'].replace('-', '')}.json"
            actual = json.loads(dia.read_text()) if dia.exists() else {"fecha": f["fecha"].replace("-", ""), "images": []}
            actual["images"] = [i for i in actual["images"] if i["nombre_imagen"] != f["archivo"]] + [res]
            actual["total"] = len(actual["images"])
            actual["modelo"] = MODELO
            dia.write_text(json.dumps(actual, ensure_ascii=False, indent=1))
            wu.writerow([f["fecha"], f["hora"], f["archivo"], MODELO, uso.get("promptTokenCount", ""),
                         (uso.get("candidatesTokenCount", 0) + uso.get("thoughtsTokenCount", 0)) if uso else "", round(time.time() - t0, 2)])
            fu.flush()
            if n % 25 == 0:
                print(f"{n}/{len(pendientes)}", flush=True)
            time.sleep(4)  # respetar el límite gratuito de solicitudes por minuto
    print("Listo.")


if __name__ == "__main__":
    main()
