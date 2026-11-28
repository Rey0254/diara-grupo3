"""
Paso 7 · Agregación por día y archivo final para la plataforma.

Une: inventario (paso 1) + control de calidad (paso 3) + Gemini de la CGR (paso 4)
     + modelo abierto (paso 5) + Gemini del Grupo 3 (paso 6, si ya corrió).

Salidas:
  data/datos_limoncito.json         un registro por día, compatible con el frontend (mismos campos que
                                    datos_demo.json) + campos nuevos opcionales
  data/fotos_limoncito.json         todas las fotos, con URL de Drive, calidad y detecciones (galería)
  data/alertas_limoncito.json       alertas de la cámara (mantenimiento) y de la obra
  data/limoncito/dias.csv           la misma tabla diaria en CSV, para revisarla en Excel

REGLA DEL DÍA (decidida por Luis, 28-nov-2026):
  1. Sin ninguna foto                                  -> "sin_datos"
  2. Evidencia suficiente = al menos 4 fotos usables en horario de trabajo (7:00-16:59)
     y al menos 1 en la mañana (7-11) y 1 en la tarde (12-16).
     - personas en >= 2 fotos usables                  -> "con_actividad"
     - si no                                           -> "sin_actividad_visible"
  3. Sin evidencia suficiente (fotos borrosas, quemadas, pocas):
     - personas en >= 2 fotos (aunque sean borrosas)   -> "con_actividad_baja_calidad"
     - si no                                           -> "no_se_puede_saber"
  Ver personas en una foto mala sí es evidencia de trabajo; no verlas no prueba nada.
  La maquinaria se informa, pero no decide el estado (la grúa torre está fija en la obra).
"""
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "limoncito"
SALIDA = RAIZ / "data"

MIN_FOTOS_EVIDENCIA = 4
MIN_FOTOS_CON_PERSONAS = 2
HORA_INICIO, HORA_MEDIODIA, HORA_FIN = 7, 12, 17
DIAS_ALERTA_MEDIA, DIAS_ALERTA_ALTA = 5, 10

ETIQUETAS = {
    "con_actividad": "Con actividad",
    "con_actividad_baja_calidad": "Con actividad (fotos de baja calidad)",
    "sin_actividad_visible": "Sin actividad visible (según lo que muestran las fotos)",
    "no_se_puede_saber": "No se puede saber (las fotos no permiten ver la obra)",
    "sin_datos": "Sin datos (la cámara no envió fotos)",
}
MOTIVOS = {
    "oscura": "muy oscura", "sobreexpuesta": "sobreexpuesta (casi blanca)", "borrosa": "borrosa (lente empañado o sucio)",
    "sin_contraste": "sin contraste", "fuera_de_encuadre": "no muestra la obra", "sin_imagen": "archivo dañado",
}
MOTIVOS_PLURAL = {
    "oscura": "muy oscuras", "sobreexpuesta": "sobreexpuestas (casi blancas)", "borrosa": "borrosas (lente empañado o sucio)",
    "sin_contraste": "sin contraste", "fuera_de_encuadre": "que no muestran la obra", "sin_imagen": "con el archivo dañado",
}


def leer_csv(ruta):
    return list(csv.DictReader(open(ruta, encoding="utf-8"))) if ruta.exists() else []


def url_drive(drive_id, ancho=800):
    return f"https://drive.google.com/thumbnail?id={drive_id}&sz=w{ancho}"


def moda(valores):
    v = [x for x in valores if x and x != "No determinable"]
    return Counter(v).most_common(1)[0][0] if v else ("No determinable" if valores else None)


def cargar_gemini():
    """Análisis de Gemini por (fecha, hora): primero el de la CGR, luego el del Grupo 3."""
    g = {}
    for r in leer_csv(DATOS / "gemini_fotos.csv"):
        if r["error"]:
            continue
        g[(r["fecha"], r["hora"])] = {
            "fuente": "Gemini (CGR, obrapublica.info)", "personas": int(r["personas"]) if r["personas"] else None,
            "maquinaria": [m for m in r["maquinaria"].split("|") if m], "casco": r["casco"], "chaleco": r["chaleco"],
            "clima": r["clima"], "certeza": "",
        }
    carpeta = DATOS / "gemini_grupo3"
    if carpeta.exists():
        for f in sorted(carpeta.glob("*.json")):
            dia = json.loads(f.read_text())
            for im in dia.get("images", []):
                if "error" in im:
                    continue
                fecha, hora = im["fecha_hora"].split(" ")
                seg = im.get("seguridad_laboral") or {}
                g[(fecha, hora)] = {
                    "fuente": f"Gemini (Grupo 3, {dia.get('modelo', '')})", "personas": im.get("personas_trabajadoras"),
                    "maquinaria": im.get("maquinaria") or [], "casco": seg.get("uso_casco", ""),
                    "chaleco": seg.get("uso_chaleco", ""),
                    "clima": (im.get("condiciones_climaticas") or {}).get("clima_general", ""),
                    "certeza": im.get("certeza", ""),
                }
    return g


def cargar_deteccion():
    det = {}
    cache = DATOS / "cache_deteccion.jsonl"
    if cache.exists():
        for linea in cache.read_text().splitlines():
            r = json.loads(linea)
            det[r["archivo"]] = r
    return det


def resumen_cgr(fecha):
    t = DATOS / "gemini" / f"{fecha.replace('-', '')}.txt"
    if not t.exists():
        return None
    return re.sub(r"\*\*(.+?)\*\*", r"\1", t.read_text(encoding="utf-8")).strip()


def main():
    inventario = leer_csv(DATOS / "inventario_fotos.csv")
    calidad = {(r["fecha"], r["hora"], r["archivo"]): r for r in leer_csv(DATOS / "calidad_fotos.csv")}
    deteccion = cargar_deteccion()
    gemini = cargar_gemini()

    fotos_dia = defaultdict(list)
    todas = []
    for f in inventario:
        c = calidad.get((f["fecha"], f["hora"], f["archivo"]), {})
        d = deteccion.get(f["archivo"])
        g = gemini.get((f["fecha"], f["hora"]))
        foto = {
            "fecha": f["fecha"], "hora": f["hora"], "archivo": f["archivo"], "drive_id": f["drive_id"],
            "url": url_drive(f["drive_id"]), "url_grande": url_drive(f["drive_id"], 1600),
            "usable": c.get("usable") == "sí", "motivo": c.get("motivo", ""),
            "motivo_texto": MOTIVOS.get(c.get("motivo", ""), ""),
            "invertida": c.get("orientacion") == "invertida",
            "personas_modelo_abierto": d["persona"] if d else None,
            "camiones_modelo_abierto": d["camion"] if d else None,
            "gemini": g,
        }
        fotos_dia[f["fecha"]].append(foto)
        todas.append(foto)

    primero, ultimo = date.fromisoformat(min(fotos_dia)), date.fromisoformat(max(fotos_dia))
    registros = []
    for i in range((ultimo - primero).days + 1):
        dia = str(primero + timedelta(i))
        fotos = sorted(fotos_dia.get(dia, []), key=lambda x: x["hora"])
        en_horario = [x for x in fotos if x["hora"] and HORA_INICIO <= int(x["hora"][:2]) < HORA_FIN]
        usables = [x for x in en_horario if x["usable"]]
        manana = [x for x in usables if int(x["hora"][:2]) < HORA_MEDIODIA]
        tarde = [x for x in usables if int(x["hora"][:2]) >= HORA_MEDIODIA]
        procesadas = [x for x in en_horario if x["personas_modelo_abierto"] is not None]
        usables = [x for x in usables if x["personas_modelo_abierto"] is not None]  # solo las ya analizadas
        manana = [x for x in manana if x in usables]
        tarde = [x for x in tarde if x in usables]
        con_personas_usables = [x for x in usables if (x["personas_modelo_abierto"] or 0) > 0]
        con_personas_todas = [x for x in procesadas if (x["personas_modelo_abierto"] or 0) > 0]
        evidencia = len(usables) >= MIN_FOTOS_EVIDENCIA and manana and tarde

        if not fotos:
            estado = "sin_datos"
        elif evidencia:
            estado = "con_actividad" if len(con_personas_usables) >= MIN_FOTOS_CON_PERSONAS else "sin_actividad_visible"
        else:
            estado = "con_actividad_baja_calidad" if len(con_personas_todas) >= MIN_FOTOS_CON_PERSONAS else "no_se_puede_saber"

        gem = [x["gemini"] for x in fotos if x["gemini"]]
        personas_gem = [x["personas"] for x in gem if isinstance(x.get("personas"), int)]
        maq_gem = sorted({m for x in gem for m in x["maquinaria"]})
        if personas_gem:
            personas, fuente_personas = max(personas_gem), gem[0]["fuente"]
        elif con_personas_todas or procesadas:
            personas = max((x["personas_modelo_abierto"] or 0) for x in procesadas) if procesadas else None
            fuente_personas = "Modelo abierto YOLO11s (cuenta menos personas que Gemini)"
        else:
            personas, fuente_personas = None, None
        camiones = max(((x["camiones_modelo_abierto"] or 0) for x in procesadas), default=0)
        maquinaria = len(maq_gem) if gem else (camiones if procesadas else None)
        lluvia = any(x.get("clima") == "Lluvioso" for x in gem) if gem else None

        motivos = Counter(x["motivo"] for x in fotos if not x["usable"] and x["motivo"])
        partes = [f"La cámara tomó {len(fotos)} fotos; {len(usables)} sirvieron para analizar la obra."]
        if motivos:
            partes.append("No sirvieron: " + ", ".join(f"{n} {MOTIVOS_PLURAL[m]}" for m, n in motivos.most_common()) + ".")
        if estado.startswith("con_actividad"):
            partes.append(f"Se vieron personas en {len(con_personas_todas)} fotos"
                          + (f" (hasta {max(personas_gem)} en una misma foto, según Gemini)" if personas_gem else "") + ".")
        elif estado == "sin_actividad_visible":
            partes.append("No se vieron personas trabajando en las fotos de ese día; eso no significa necesariamente que la obra esté detenida.")
        elif estado == "no_se_puede_saber":
            partes.append("Las fotos no permiten saber si hubo trabajo.")
        if maq_gem:
            partes.append("Maquinaria visible: " + ", ".join(maq_gem[:5]).lower() + ".")
        if estado.startswith("con_actividad"):
            partes.append("Esto indica presencia de trabajo, no avance de la obra.")

        destacadas = [x for x in usables if (x["personas_modelo_abierto"] or 0) > 0] or usables or fotos
        paso = max(1, len(destacadas) // 4)
        registros.append({
            # --- campos que ya usa el frontend (mismo formato que datos_demo.json) ---
            "fecha": dia,
            "personas_detectadas": personas,
            "maquinaria_detectada": maquinaria,
            "casco": moda([x["casco"] for x in gem]) if gem else "No determinable",
            "chaleco": moda([x["chaleco"] for x in gem]) if gem else "No determinable",
            "estado_datos": "disponible" if estado in ("con_actividad", "con_actividad_baja_calidad", "sin_actividad_visible") else "sin datos",
            "fotografias": [{k: x[k] for k in ("hora", "url", "url_grande", "usable", "invertida", "motivo_texto")}
                            for x in destacadas[::paso][:4]],
            # --- campos nuevos (opcionales) ---
            "estado_dia": estado,
            "estado_dia_texto": ETIQUETAS[estado],
            "calidad_fotos": "normal" if evidencia else ("baja" if fotos else None),
            "n_fotos": len(fotos),
            "n_fotos_usables": len(usables),
            "n_fotos_con_personas": len(con_personas_todas),
            "fuente_personas": fuente_personas,
            "maquinaria_lista": maq_gem,
            "lluvia_observada": lluvia,
            "resumen_dia": " ".join(partes) if fotos else "La cámara no envió fotos este día.",
            "resumen_gemini_cgr": resumen_cgr(dia),
        })

    alertas = generar_alertas(registros, fotos_dia)
    for a in alertas:
        for r in registros:
            if a["desde"] <= r["fecha"] <= a["hasta"]:
                r.setdefault("alertas", []).append(a["id"])

    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    datos = {
        "tipo_datos": "REALES · Fotos de la cámara dIAra (CGR) · Procesamiento: Grupo 3, LEAD University",
        "generado": ahora,
        "obra": {
            "id": "limoncito",
            "nombre": "Escuela Barrio Limoncito",
            "ubicacion": "Cieneguita, Limón, Costa Rica",
            "institucion_responsable": None,
            "avance_contractual": None,
            "ultima_actualizacion": registros[-1]["fecha"],
        },
        "procedencia": {
            "fotos": "Carpeta pública de la CGR en Google Drive: https://drive.google.com/drive/folders/1m878MoosJ0GY_Agkh0dBenwX-S7LTCAK",
            "analisis_gemini_cgr": "https://www.obrapublica.info/limoncito (muestra de 5 fotos por día hábil, ene-abr 2026)",
            "analisis_gemini_grupo3": "Muestra de 5 fotos por día desde el 18-abr-2026 (scripts/06_gemini_muestra.py)",
            "modelo_abierto": "YOLO11s (Ultralytics), foto dividida en 6 partes; scripts/05_deteccion.py",
            "control_calidad": "OpenCV; scripts/03_calidad.py",
        },
        "notas": [
            "Las fotos muestran presencia de trabajo, no avance de obra. El avance solo se puede medir contra el plan de trabajo del contrato.",
            "La cámara solo toma fotos de 6 a. m. a 5 p. m.: no es posible saber si hubo trabajo nocturno.",
            "Del 18-abr-2026 en adelante la cámara quedó invertida; las fotos se corrigen girándolas 180°.",
            "Los conteos de personas de Gemini son más completos que los del modelo abierto; por eso se indica la fuente de cada día.",
        ],
        "estados_dia": ETIQUETAS,
        "registros": registros,
    }
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "datos_limoncito.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1))
    (SALIDA / "fotos_limoncito.json").write_text(json.dumps(
        {"generado": ahora, "fotos": [{k: v for k, v in x.items() if k != "gemini"} | {"gemini": x["gemini"]} for x in todas]},
        ensure_ascii=False))
    (SALIDA / "alertas_limoncito.json").write_text(json.dumps({"generado": ahora, "alertas": alertas}, ensure_ascii=False, indent=1))
    campos = ["fecha", "estado_dia", "n_fotos", "n_fotos_usables", "n_fotos_con_personas", "personas_detectadas",
              "fuente_personas", "maquinaria_detectada", "casco", "chaleco", "lluvia_observada", "resumen_dia"]
    with open(DATOS / "dias.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(registros)
    print("Estados:", dict(Counter(r["estado_dia"] for r in registros)))
    print("Alertas:", dict(Counter(f"{a['tipo']}/{a['nivel']}" for a in alertas)))


def generar_alertas(registros, fotos_dia):
    """Alertas de mantenimiento de la cámara (para el equipo dIAra) y de la obra (para la ciudadanía)."""
    alertas = []

    def tramo(fechas, tipo, nivel, titulo, detalle, para):
        alertas.append({"id": f"{tipo}-{len(alertas) + 1}", "tipo": tipo, "nivel": nivel, "desde": fechas[0],
                        "hasta": fechas[-1], "dias": len(fechas), "titulo": titulo, "detalle": detalle, "para": para})

    # 1) Cámara: tramos de >= 2 días seguidos con menos del 30 % de fotos usables, agrupados por motivo.
    actual, motivo_actual = [], None
    for r in registros:
        fotos = fotos_dia.get(r["fecha"], [])
        if not fotos:
            continue
        malas = Counter(x["motivo"] for x in fotos if not x["usable"] and x["motivo"])
        pct_usable = sum(x["usable"] for x in fotos) / len(fotos)
        motivo = malas.most_common(1)[0][0] if malas and pct_usable < 0.3 else None
        if motivo and motivo == motivo_actual:
            actual.append(r["fecha"])
            continue
        if len(actual) >= 2:
            tramo(actual, "camara", "alta" if len(actual) >= 7 else "media",
                  f"Fotos {MOTIVOS_PLURAL[motivo_actual]} durante {len(actual)} días",
                  "La cámara está enviando fotos que no permiten ver la obra. Revisar el lente, la exposición o la posición.",
                  "Equipo dIAra (CGR)")
        actual, motivo_actual = ([r["fecha"]], motivo) if motivo else ([], None)
    if len(actual) >= 2:
        tramo(actual, "camara", "alta" if len(actual) >= 7 else "media",
              f"Fotos {MOTIVOS_PLURAL[motivo_actual]} durante {len(actual)} días",
              "La cámara está enviando fotos que no permiten ver la obra.", "Equipo dIAra (CGR)")

    # 2) Cámara: cambio de orientación (empieza a llegar invertida y sigue así al menos 3 días).
    serie = []
    for r in registros:
        fotos = [x for x in fotos_dia.get(r["fecha"], []) if x["usable"]]
        if len(fotos) >= 4:
            serie.append((r["fecha"], sum(x["invertida"] for x in fotos) / len(fotos) > 0.5))
    for i in range(1, len(serie) - 2):
        if not serie[i - 1][1] and all(v for _, v in serie[i:i + 3]):
            tramo([serie[i][0]], "camara", "media", "La cámara quedó invertida",
                  "Las fotos llegan de cabeza desde este día. Se corrigen girándolas, pero conviene reinstalar la cámara.",
                  "Equipo dIAra (CGR)")

    # 3) Cámara: días sin ninguna foto.
    for r in registros:
        if r["estado_dia"] == "sin_datos":
            tramo([r["fecha"]], "camara", "baja", "La cámara no envió fotos",
                  "Revisar energía (panel solar/batería) o conexión (MiFi).", "Equipo dIAra (CGR)")

    # 4) Obra: días seguidos sin actividad visible (solo días con evidencia suficiente).
    racha = []
    for r in registros + [{"fecha": "9999-12-31", "estado_dia": "fin"}]:
        if r["estado_dia"] == "sin_actividad_visible":
            racha.append(r["fecha"])
            continue
        if r["estado_dia"] in ("sin_datos", "no_se_puede_saber") and racha:
            continue  # un día sin evidencia no corta ni alarga la racha
        if len(racha) >= DIAS_ALERTA_MEDIA:
            tramo(racha, "obra", "alta" if len(racha) >= DIAS_ALERTA_ALTA else "media",
                  f"{len(racha)} días sin actividad visible",
                  "En las fotos de esos días no se vio gente trabajando. Puede deberse a lluvia, feriados u otra causa: "
                  "la institución ejecutora es quien puede explicarlo.", "Ciudadanía y fiscalizador")
        racha = []
    # Unir tramos con el mismo problema separados por 3 días o menos.
    unidas = []
    for a in sorted(alertas, key=lambda a: (a["tipo"], a["titulo"].split(" durante")[0], a["desde"])):
        b = unidas[-1] if unidas else None
        if (b and a["tipo"] == b["tipo"] == "camara" and " durante " in a["titulo"]
                and a["titulo"].split(" durante")[0] == b["titulo"].split(" durante")[0]
                and (date.fromisoformat(a["desde"]) - date.fromisoformat(b["hasta"])).days <= 3):
            b["hasta"] = a["hasta"]
            b["dias"] = (date.fromisoformat(b["hasta"]) - date.fromisoformat(b["desde"])).days + 1
            b["titulo"] = b["titulo"].split(" durante")[0] + f" durante {b['dias']} días"
            b["nivel"] = "alta" if b["dias"] >= 7 else b["nivel"]
            continue
        unidas.append(dict(a))
    unidas.sort(key=lambda a: a["desde"])
    for i, a in enumerate(unidas, 1):
        a["id"] = f"{a['tipo']}-{i}"
    return unidas


if __name__ == "__main__":
    main()
