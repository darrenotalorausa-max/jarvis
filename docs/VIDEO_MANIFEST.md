# Manifiesto de proyecto de video (`jarvis-video-manifest`, versión 1)

Formato JSON propio para documentar y trasladar un proyecto. **No es** un proyecto de Premiere, DaVinci Resolve ni EDL/XML:
no hay exportación nativa a esos editores.

| Campo | Contenido |
|---|---|
| `formato`, `version`, `generado` | Identificador, versión del formato y fecha |
| `proyecto` | `id`, `titulo`, `modo` (clipping, publicidad, marca_personal, formacion), `campana_id` |
| `origenes[]` | Archivos de origen: `id`, `nombre`, `sha256`, `duracion` (s), `ancho`, `alto` |
| `recursos_propios[]` | Material autorizado asociado (mismos campos) |
| `segmentos[]` | `id`, `file_id`, `start`, `end` (segundos), `label`, `enabled` |
| `subtitulos` | Por `file_id`: lista de `{start, end, text}` en tiempo del archivo de origen |
| `ajustes` | `formatos` (ancho/alto por preset), `encuadre`, `punto_interes` [x, y] de 0 a 1, `normalizar_audio`, `subtitulos_incrustados`, `unir_segmentos`, `codificacion` (argumentos de FFmpeg) |
| `recursos_faltantes[]` | Texto libre |
| `salidas[]` | Archivos exportados: `id`, `nombre`, `sha256`, `preset`, `duration`, `width`, `height` |

Presets: `9:16` = 1080×1920, `1:1` = 1080×1080, `16:9` = 1920×1080. Encuadres: `recorte`, `relleno_desenfocado`, `barras`.
Codificación: H.264 (libx264, CRF 20, 30 fps, yuv420p) + AAC 160 kb/s 48 kHz estéreo, `+faststart`.
Normalización: `loudnorm` EBU R128 a −14 LUFS, pico −1,5 dBTP (una pasada).
