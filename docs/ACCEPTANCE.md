# Criterios de aceptación y pruebas

## Cómo ejecutar

```bash
cd backend && ../.venv/bin/python -m pip install -r requirements-dev.txt && ../.venv/bin/python -m pytest tests -q
node frontend/e2e/smoke.cjs http://127.0.0.1:8765 <carpeta_capturas>   # contra una instancia limpia en marcha
```

Los proveedores simulados existen únicamente en `backend/tests/conftest.py` (`httpx.MockTransport`). Ninguna prueba
hace llamadas externas ni gasta dinero.

## Resultado de la última ejecución (2026-11-10, Linux, Python 3.13, Node 22, FFmpeg 6.1)

- `pytest`: **100 superadas, 0 fallidas** (≈ 25 s).
- Recorrido en navegador: **completado sin problemas** (sin errores de consola, sin respuestas 5xx, sin desbordamiento en móvil).
- Instalación desde un clon limpio con `scripts/setup.sh` y arranque con `scripts/start.sh`: **correcta** (API responde y sirve la interfaz; Ctrl+C detiene API y worker).
- Lanzadores de Windows: **no ejecutados**.

## Criterio → prueba

| Criterio | Prueba |
|---|---|
| Persistencia y migraciones | `test_core::test_migrations_are_idempotent_and_data_persists` |
| Validación de proveedores; timeout, cuota, credenciales inválidas | `test_core::test_provider_errors_map_to_clear_states`, `test_timeout_and_missing_credential`, `test_quota_pauses_and_does_not_loop`, `test_timeouts_retry_with_limit` |
| Gasto pagado desactivado | `test_core::test_paid_spend_disabled_by_default`, `test_paid_budget_exhausted_blocks` |
| Caché y separación por espacio | `test_core::test_cache_by_content_and_space_with_ttl`, `test_records_validation_and_space_isolation`, `test_space_policies` |
| Recuperación y cancelación de trabajos | `test_core::test_recovery_after_crash_and_limited_retries`, `test_cancel_pending_and_running`, `test_heartbeat_detects_cancel_request`, `test_run_proc_no_shell_and_cancel`, `test_worker_as_separate_process_runs_registered_handlers` |
| Deduplicación | `test_core::test_idempotent_enqueue_and_completion`, `test_flows::test_lead_search_dedup_exclusions_and_proposal`, `test_csv_import_mapping_duplicates_and_economy_summary` |
| Fuentes y fechas | `test_flows::test_opportunity_to_dossier_with_sources_and_dates`, `test_unverifiable_quote_is_demoted_and_unknown_source_rejected` |
| Rechazo de salidas malformadas | `test_flows::test_malformed_model_output_is_rejected`, `test_jarvis_model_can_only_pick_validated_tools` |
| Prompt injection en fuentes | `test_flows::test_prompt_injection_in_source_cannot_act` |
| Rutas y archivos | `test_security_review::test_path_traversal_and_file_types`, `test_upload_size_limit`, `test_ssrf_*`, `test_fetch_respects_blocks_and_robots` |
| Aprobación ligada a versión | `test_security_review::test_approval_bound_to_version_destination_and_expiry`, `test_external_send_requires_specific_approval` |
| Backup y restauración | `test_security_review::test_backup_restore_roundtrip_without_secrets`, `test_backup_rejects_tampered_or_unsafe` |
| Oportunidad → entregable | `test_flows::test_opportunity_to_dossier_with_sources_and_dates`, `test_research_without_model_gives_evidence_only_and_without_search_waits` |
| Lead → propuesta revisable | `test_flows::test_lead_search_dedup_exclusions_and_proposal`, `test_lead_with_unverified_quote_stays_unconfirmed` |
| Brief → lote | `test_flows::test_brief_to_content_batch_keeps_brands_separate` |
| Video de prueba → exportación real | `test_flows::test_video_probe_render_formats_subtitles_and_manifest`, `test_video_join_and_failed_clip_does_not_break_batch`, `test_video_validation_suggestions_and_transcription_needs_provider`; en navegador: paso «video» |
| Producto → paquete Shopify | `test_flows::test_product_to_shopify_package`, `test_shopify_without_model_uses_only_given_fields_and_inspects_theme`; en navegador: paso «shopify» |
| Separación de estados de clipping | `test_flows::test_clipping_states_are_not_mixed`, `test_clipping_import_url_verifies_extracted_numbers` |
| Comandos Jarvis → herramientas | `test_flows::test_jarvis_commands_run_registered_tools`; en navegador: paso «comando» |
| Fallback de voz a texto | `test_flows::test_voice_falls_back_to_text` |
| Secretos | `test_core::test_secrets_never_returned_nor_stored_in_db`, respaldo sin secretos |
| Escritura externa solo con aprobación exacta | `test_apps` (conector: lectura directa, escritura rechazada sin aprobación, aprobación de un solo uso ligada a la petición); en navegador: paso «apps» |
| Roles y aislamiento por usuario | `test_apps` (equipo y cliente: rutas y espacios permitidos); en navegador: paso «usuarios con rol» |
| Monitores sin repetir hallazgos | `test_apps`; en navegador: paso «monitores» |
| Importadores sin duplicados | `test_apps` (Apple Health, OFX); en navegador: paso «personal: extracto bancario…» |
| Sin modelo permitido no se envían notas | En navegador: «preguntas a las notas sin IA» |
| Memoria por espacio y en prompts | `test_extra::test_long_term_memory_is_per_space_and_reaches_prompts`; en navegador: paso «memoria…» |
| Horarios: una vez, con pausa | `test_extra::test_schedules_run_orders_on_time_once_and_respect_pause` |
| Medios: archivos, espera sin proveedor, descargas seguras | `test_extra::test_image_and_video_generation_save_files_and_need_a_provider`, `test_fal_queue_downloads_only_from_public_https` |
| Aprobación remota exacta y de un solo uso | `test_extra::test_approve_and_reject_from_telegram_only_exact_and_once` |
| Manos libres solo tras «Jarvis» | En navegador: paso «manos libres» |
| CRUD personal | `test_core::test_personal_modules_crud_archive_export`; en navegador: paso «personal» |

## Comprobación visual (navegador real)

Escritorio 1440×900 y móvil 390×844; estados vacíos de las 12 pantallas de trabajo; trabajo en espera con su motivo;
trabajo de video ejecutándose y completado; error comprensible de conexión; foco por teclado; `prefers-reduced-motion`
(el núcleo deja de animarse). Fallos detectados y corregidos durante la revisión: etiquetas anidadas en grupos de casillas,
insignias deformadas, desplazamiento de página causado por el chat, partición de palabras en tablas, espacio inicial
incorrecto tras el primer inicio y registro de manejadores del worker al ejecutarse como proceso.

## Pendiente de comprobar (requiere tu entorno)

1. `SETUP_JARVIS.cmd` y `START_JARVIS.cmd` en Windows 10/11 con y sin requisitos instalados; acceso directo «Jarvis OS» y ventana de aplicación.
2. Cada proveedor con tu clave: «Guardar y probar conexión» y un trabajo real pequeño.
3. Voz con micrófono en Chrome o Edge.
4. Instalar el paquete Shopify en un duplicado de tu tema y probar móvil, variantes y carrito.
5. Cada app conectada con tu cuenta: «Probar» y una acción de lectura; OAuth de Google.
6. `docker compose up -d --build` en tu servidor.
7. Servidor MCP desde tu cliente (Claude Desktop u otro).
8. Generar una imagen y un video con tu proveedor; manos libres con tu micrófono; aprobar desde tu Telegram.
