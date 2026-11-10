# Diseño de la interfaz

Rehecha siguiendo la skill «Anti-Slop (AJONAI)» que aportó el usuario: cada valor visible se deriva de este producto.
Si cambias algo, cambia primero esta hoja. Los tokens viven en `frontend/src/styles.css` (`:root`).

## Hoja de decisiones

| Eje | Decisión | Por qué aquí |
|---|---|---|
| Sujeto | Consola local de un solo operador que dirige trabajos de «empleados digitales» | El núcleo debe responder de un vistazo a «¿qué está haciendo el sistema ahora?» |
| Mundo | Telemetría, cola de trabajos, latido del worker, timecodes, IDs, micrófono abierto/cerrado | De ahí salen el anillo de progreso, la onda y la tipografía mono de las lecturas |
| Paleta | Fondo `#060A10`; superficies `#0B111A` / `#111A26` / `#18222F`; reglas `#1E2A38` / `#2C3B4D`; borde de control `#4D6379`; tinta `#E6EDF5` / `#9AABBD` / `#64768A`; acento azul arco `#4CC9F5`; ámbar `#F2A93B`; peligro `#F0616D`; correcto `#5FD3A0` | Neutros fríos teñidos hacia el acento. El acento solo marca lo activo y el núcleo; el ámbar se reserva a «requiere tu atención» |
| Tipografía | Inter Variable (texto y títulos, con eje óptico) + JetBrains Mono (IDs, timecodes, lecturas) | Inter por indicación del usuario; la jerarquía va por peso y tamaño, sin mayúsculas espaciadas. Ambas se sirven desde el propio equipo (licencia OFL) |
| Escala | 12 · 13.5 · 14 · 22 · 26 px | Pocos pasos y distintos; rango mayor de 2× |
| Espacio | Dentro de componente 4/8/12/16 · entre componentes 20/24 · entre regiones 40 | Dos registros con números distintos; en móvil el ritmo se comprime |
| Forma | Radio 12 en paneles, 8 en controles, 6 en etiquetas. Elevación **solo por escalón tonal**: sin sombras y sin borde + sombra | En fondo oscuro la sombra no separa; el escalón sí |
| Movimiento | Una curva (`cubic-bezier(0.16, 1, 0.3, 1)`), tres duraciones (120 / 200 / 320 ms). Momentos: núcleo (continuo), encendido del núcleo, entrada de vista, modal, aviso, pulsación | Presupuesto cerrado; cada animación tiene función (estado, continuidad o respuesta) |
| Firma | El núcleo, y solo el núcleo | Es el único elemento que emite luz; todo lo demás queda en silencio |

## El núcleo (`components/Core.tsx`)

Todo lo que muestra es un hecho del sistema, nunca decoración:

| Elemento | Dato real |
|---|---|
| Color y ritmo de los anillos | Estado: en espera, escuchando, procesando, hablando, error, esperando tu decisión |
| Anillo de progreso | Media del avance de los trabajos en ejecución |
| Barrido | Hay una petición o un trabajo en curso |
| Onda central | Nivel de volumen del micrófono mientras mantienes pulsado (se mide, no se graba) |
| Lectura central | Hora local, porcentaje y nº de trabajos, o nº de decisiones pendientes |

La animación se detiene con la pestaña oculta. Con `prefers-reduced-motion` desaparecen rotaciones y desplazamientos, pero el
cambio de estado sigue siendo legible por color, lectura y un fundido corto (no es un apagado total).

### Dial de módulos y sonido

El anillo exterior del núcleo son 14 sectores navegables (uno por módulo), inspirado en los diales de las referencias HUD que aportó
el usuario pero con función real: cada sector es un enlace con foco de teclado. Los sonidos (`sound.ts`) se sintetizan con Web Audio,
sin archivos ni material de terceros: un encendido de unos 2 s una vez por sesión y señales breves ligadas a hechos (trabajo
completado, fallo, micrófono abierto). Se desactivan desde la barra superior.

Los cuatro negocios llevan un color propio solo como marca pequeña (punto, sello y barra de sección), nunca como relleno.

## Estados

Todos los controles tienen `:hover`, `:active` (respuesta al pulsar), `:focus-visible`, deshabilitado con cursor y contraste
propios, y carga con esqueleto. Están tematizados selección de texto, cursor de escritura, barra de desplazamiento y anillo de
foco. Las tablas llevan una sola regla bajo la cabecera, cifras tabulares alineadas a la derecha y cabecera fija.

## Lo que se retiró a propósito

Cuadrícula decorativa de fondo, esquinas técnicas en cada panel, títulos en mayúsculas espaciadas, cabecera translúcida con
desenfoque, sombras en modales y avisos, bordes laterales de color y brillos fuera del núcleo.

## Comprobación

```bash
node "<skill>/scripts/check.mjs" frontend/src frontend/index.html   # 0 errores, 0 avisos; 4 notas consultivas que son falsos positivos (valores «100%» de CSS)
node frontend/e2e/smoke.cjs                                        # recorrido en navegador, incluye móvil y movimiento reducido
```
No comprobado: la onda con micrófono real (el navegador de pruebas no tiene micrófono) y el aspecto en Windows con sus
fuentes de sistema de respaldo.
