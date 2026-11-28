# Módulo de datos y automatización

Responsable: Luis Rodríguez Dávila
Grupo 3 · Visualización de Datos · LEAD University · 2026

> Versión del 28-nov-2026. Datos reales de la Escuela Barrio Limoncito, del 11-sep-2025 al 2-jul-2026.

## 1. Fuentes

| Fuente | Qué aporta | Acceso |
|---|---|---|
| Carpeta de Google Drive de la CGR, "2025-2026 Escuela Barrio Limoncito, Limón" | Todas las fotos de la cámara dIAra: **6.575 fotos** en 293 días | Pública por enlace: https://drive.google.com/drive/folders/1m878MoosJ0GY_Agkh0dBenwX-S7LTCAK |
| obrapublica.info (Escuela de Limoncito) | Análisis de Gemini hecho por la CGR: 385 fotos (5 por día hábil, del 1-ene al 17-abr-2026) y un resumen por día | Archivos públicos en `https://www.obrapublica.info/static/limoncito/data/` |
| Repositorio de la CGR (github.com/cgrcostarica/dIAra) | Modelo original, imágenes etiquetadas de ejemplo y documentación técnica | Público |

Las fotos de obrapublica.info son una muestra de las del Drive; se unen por fecha y hora de captura.

## 2. Cómo correrlo

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r scripts/requirements.txt
bash scripts/actualizar.sh          # corre los 7 pasos; cada uno procesa solo lo nuevo
```

En GitHub corre solo con el workflow `.github/workflows/datos-limoncito.yml`: a mano, al cambiar los scripts y todos los días a las 6:15 a. m. (hora de Costa Rica). La programación diaria funciona cuando el workflow está en la rama principal. La clave de Gemini se guarda como secreto del repositorio (`GEMINI_API_KEY`) y **nunca** va en el código.

## 3. Proceso

| Paso | Script | Qué hace | Salida |
|---|---|---|---|
| 1 | `01_inventario.py` | Lista la carpeta de Drive (~75 s) y saca la fecha y la hora del nombre de cada foto (hay 3 formatos de nombre) | `data/limoncito/inventario_fotos.csv` |
| 2 | `02_descargar.py` | Descarga solo las fotos nuevas (712 MB en total) | `data/limoncito/fotos/` (no se sube al repositorio) |
| 3 | `03_calidad.py` | Control de calidad con OpenCV, sin IA y sin costo | `data/limoncito/calidad_fotos.csv` |
| 4 | `04_obrapublica.py` | Descarga el análisis de Gemini de la CGR | `data/limoncito/gemini_fotos.csv` y `gemini/` |
| 5 | `05_deteccion.py` | Detecta personas y camiones con YOLO11s (modelo abierto, gratuito), con la foto dividida en 6 partes y convertida a OpenVINO (0,22 s por foto en CPU) | `data/limoncito/deteccion_fotos.csv` |
| 6 | `06_gemini_muestra.py` | Gemini en una muestra de 5 fotos usables por día, desde el 18-abr-2026; registra los tokens reales usados | `data/limoncito/gemini_grupo3/`, `gemini_uso_tokens.csv` |
| 7 | `07_agregar.py` | Une todo, aplica la regla del día y genera las alertas | `data/datos_limoncito.json`, `data/fotos_limoncito.json`, `data/alertas_limoncito.json`, `data/limoncito/dias.csv` |

## 4. Control de calidad

| Medida | Qué detecta | Umbral |
|---|---|---|
| Brillo promedio | Noche o lente tapado | < 40 = "oscura" |
| % de píxeles casi blancos | Sobreexposición | > 35 % = "sobreexpuesta" |
| Contraste | Imagen plana | < 18 = "sin_contraste" |
| Nitidez (varianza del Laplaciano) | Lente empañado, sucio o desenfocado | < 20 = "borrosa" |
| Similitud con las fotos de ±3 días | Fotos que no muestran la obra (pruebas, algo tapando la vista) | < 0,40 = "fuera_de_encuadre" |
| Orientación | Cámara de cabeza | Si girada 180° se parece más al encuadre de referencia, se marca "invertida" y **se corrige** |

La similitud se compara con la misma semana porque la obra cambia: en oct-2025 todavía no existía el edificio que se ve en 2026.

**Resultado:** 4.109 de 6.575 fotos usables (62 %), incluidas 2.154 invertidas que se corrigen. No usables: 1.701 borrosas, 599 sobreexpuestas, 104 oscuras, 32 sin contraste, 28 fuera de encuadre y 2 dañadas.

**¿Se pueden mejorar?**
- **Borrosas (lente empañado):** se probaron cinco técnicas (quitar neblina, ecualización CLAHE, estirar niveles y combinaciones). La versión mejorada **sirve para que una persona vea la foto** (el 10-dic-2025 se ve un colado de concreto con unos 10 trabajadores), pero **empeora el detector** (de 4 a entre 1 y 2 fotos con personas en una muestra de 20). Por eso el detector usa la original y la galería puede mostrar la mejorada.
- **Sobreexpuestas:** no se pueden recuperar; 495 de 599 tienen más del 80 % quemado.
- **De noche:** la cámara solo toma fotos de ~6 a. m. a 5 p. m. Las 40 fotos nocturnas que hay son pruebas de sep–nov-2025. **No es posible saber si hubo trabajo nocturno.**

### La historia de la cámara

| Periodo | Qué pasó |
|---|---|
| 11 al 18-sep-2025 | Instalación y pruebas: fotos negras, fotos de oficina |
| 19-sep al 1-nov-2025 | Fotos sobreexpuestas (casi blancas) y con tono verde: **44 días** |
| 6-nov-2025 al 10-feb-2026 | Lente empañado o sucio: **97 días** |
| 11-feb al 17-abr-2026 | La cámara se limpió o reajustó: fotos nítidas |
| 18-abr al 2-jul-2026 | Mismo encuadre, **cámara invertida** (se corrige con un giro de 180°) |

## 5. Regla del día (decisión de Luis, 28-nov-2026)

1. **Sin ninguna foto** → "Sin datos".
2. **¿Hay evidencia suficiente?** Al menos 4 fotos usables entre las 7:00 y las 16:59, con al menos 1 en la mañana y 1 en la tarde.
   - Personas en **al menos 2 fotos** → "Con actividad".
   - Si no → "Sin actividad visible (según lo que muestran las fotos)".
3. **Sin evidencia suficiente** (fotos borrosas, quemadas o pocas):
   - Personas en al menos 2 fotos, aunque sean borrosas → "Con actividad (fotos de baja calidad)".
   - Si no → "No se puede saber".

Ver personas en una foto mala sí es evidencia de trabajo; no verlas no prueba nada. La maquinaria se informa, pero no decide el estado, porque la grúa torre está fija y aparece en casi todas las fotos. Se eligieron 2 fotos para no quedarse con muy pocos días disponibles. Con fotos cada ~21 minutos, 2 fotos equivalen a al menos 20 minutos de presencia.

**Resultado (295 días):** con actividad 134; con actividad con fotos de baja calidad 47; no se puede saber 105; sin actividad visible 7 (Semana Santa, del 1 al 5-abr, y del 26 al 28-jun); sin datos 2. Se trabajó en 16 de los 20 domingos de feb–jun-2026.

## 6. Costo y desempeño: modelo abierto vs. Gemini

Comparación en las 237 fotos usables que también analizó Gemini (CGR). Primero se revisaron fotos a mano: Gemini cuenta bien, porque ve trabajadores muy pequeños y lejanos que el modelo abierto no detecta.

| | YOLO11s (abierto) | Gemini (por tokens) |
|---|---|---|
| Fotos con personas detectadas | 68 % de las que Gemini marca con personas | Referencia |
| Personas contadas | 322 (menos de la mitad) | 681 |
| Estado del día (regla de 2 fotos, solo con la muestra de 5 fotos) | Coincide en 40 de 47 días (85 %) | Referencia |
| Costo | US$0; 0,22 s por foto en una laptop y 0,86 s en el servidor gratuito de GitHub | Gemini 3.5 Flash-Lite: US$0,30 por millón de tokens de entrada y US$2,50 por millón de salida, razonamiento incluido (precio estándar consultado el 28-nov-2026). Medido el 28-nov-2026 en 47 fotos: 1.388 tokens de entrada y 194 de salida por foto, en promedio, o sea **US$0,0009 por foto**: US$0,005 por día con la muestra de 5 fotos y ≈ US$0,02 por día si se mandaran todas (≈ 22 por día). Detalle en `gemini_uso_tokens.csv` |
| Qué ve | Personas y camiones | Personas, maquinaria, casco, chaleco, arnés, clima, etapa |

**Con el lente empañado:** en 145 fotos borrosas de la muestra, Gemini dijo "0 trabajadores" en 114, no pudo analizar 18 y vio personas en 13. obrapublica.info muestra esos días como 0 trabajadores, aunque en realidad no se puede saber.

**Conclusión:** esquema híbrido.
1. El control de calidad clásico filtra gratis (el 38 % de las fotos no sirve).
2. El modelo abierto decide el estado del día en todas las fotos.
3. Gemini analiza solo una muestra de fotos que ya pasaron el filtro, para los detalles que el modelo abierto no ve.

## 7. Alertas (`data/alertas_limoncito.json`)

**Para el equipo dIAra (mantenimiento de la cámara):**
- Más de 2 días seguidos con menos del 30 % de fotos usables, agrupadas por motivo. Nivel alto desde 7 días.
- Cambio de orientación: la cámara empieza a llegar invertida y sigue así al menos 3 días.
- Días sin ninguna foto (energía o conexión).

Con los datos reales, el sistema habría avisado del sobreexpuesto desde el 19-sep-2025, del lente empañado desde el 6-nov-2025 (97 días hasta que se arregló) y del giro de la cámara el 18-abr-2026.

**Para la ciudadanía y el fiscalizador (obra):** 5 o más días con evidencia y sin actividad visible (nivel alto desde 10). Los días sin evidencia no cuentan ni cortan la racha. En este periodo no se activó ninguna: la racha más larga fue Semana Santa, con 4 días.

## 8. Formato de `datos_limoncito.json`

Es compatible con `datos_demo.json`: tiene los mismos campos, y los nuevos son opcionales.
- Campos que ya usa el frontend: `fecha`, `personas_detectadas`, `maquinaria_detectada` (número), `casco`, `chaleco`, `estado_datos` ("disponible" / "sin datos"), `fotografias` (hasta 4 fotos destacadas: hora, url, url_grande, usable, invertida, motivo).
- Campos nuevos: `estado_dia` y `estado_dia_texto` (los 5 estados de la regla), `calidad_fotos`, `n_fotos`, `n_fotos_usables`, `n_fotos_con_personas`, `fuente_personas` (Gemini o modelo abierto), `maquinaria_lista`, `lluvia_observada`, `resumen_dia` (en lenguaje sencillo, generado a partir de los datos, sin IA), `resumen_gemini_cgr` y `alertas`.
- Nivel superior: `procedencia`, `notas` (aclaraciones para el ciudadano) y `estados_dia`.
- `fotos_limoncito.json` trae las 6.575 fotos para la galería. Las URL son miniaturas públicas de Drive (`https://drive.google.com/thumbnail?id=…&sz=w800`). Si `invertida` es verdadero, la foto se muestra girada 180°.

## 9. Recomendaciones

**Para la cámara y su operación (equipo dIAra):**
1. **Activar alertas automáticas de calidad** como las de este módulo, para no perder meses de evidencia sin enterarse.
2. **Validar la instalación** los primeros días con el control de calidad (exposición, balance de blancos, orientación) antes de dar la cámara por instalada.
3. **Proteger el lente de la condensación** (capucha, desecante, limpieza programada), sobre todo en zonas húmedas como Limón.
4. **Verificar la orientación** cada vez que se mueve la cámara.
5. **Estandarizar el nombre de los archivos** (ID de cámara + fecha + hora): hoy hay 3 formatos distintos.

**Para futuras obras:**
6. **Definir el horario de captura con el horario de trabajo del constructor desde el inicio**, y usar una cámara con visión nocturna si hay trabajo de noche (chorreas de madrugada, por ejemplo).
7. **Vincular cada cámara con su contrato** (SICOP o PROERI) y su plan de trabajo: sin eso se puede medir actividad, pero no avance.
8. **Registrar la lluvia en sitio** (sensor de lluvia en el ESP32), porque las estaciones del IMN pueden estar a 15 km.

**Para el análisis con IA:**
9. **Filtrar antes de pagar tokens** y usar Gemini en una muestra diaria.
10. **Registrar el modelo y su versión:** Gemini 2.5 Flash ya no acepta claves nuevas (nuestra primera ejecución recibió 404 en las 380 fotos), así que usamos 3.5 Flash-Lite. La CGR no publica qué modelo usa; cada cambio de modelo obliga a volver a validar los conteos contra la referencia humana.
11. **Ajustar un modelo abierto con fotos de la propia obra** (la CGR ya tiene imágenes etiquetadas) para contar trabajadores pequeños y lejanos sin costo por foto.
12. **Revisar la regla de 2 fotos** con más datos: algunos domingos tienen solo 2 o 3 fotos con personas, que podrían ser vigilancia y no trabajo.

**Para comunicar a la ciudadanía:**
13. **Separar "no se puede saber" de "sin actividad"**, y nunca mostrar "0 trabajadores" cuando la foto no permite ver.
14. **Decir siempre que las fotos muestran presencia de trabajo, no avance.**
