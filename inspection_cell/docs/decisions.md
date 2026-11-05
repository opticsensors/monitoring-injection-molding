# Registro de decisiones

Fecha inicial: 2026-11-04. Los estados indican intención de diseño, no validación ni adquisición de equipos.

| ID | Estado | Decisión o propuesta | Motivo / consecuencia |
| --- | --- | --- | --- |
| D-01 | Acordado con el usuario | Mantener `inspection_cell/` en este repositorio | Compartir contexto e integración con ciclos de inyección |
| D-02 | Acordado | Separar contexto, hardware y software, con validación propia | El hardware aún está por resolver |
| D-03 | Línea de estudio inicial | Cámara 2D cenital y báscula conectada al PC | Buscar una solución de menor coste y complejidad que el escaneo 3D |
| D-04 | Descartado en esta fase | Óptica telecéntrica de la propuesta relatada | Coste, peso y volumen. Referencia exacta y ficha pendientes; no generalizar sus dimensiones a todas las telecéntricas |
| D-05 | Propuesta | Backlight difuso y soporte transparente | Obtener silueta con menos dependencia de luz lateral; validar contraste por material/condición y efecto del soporte |
| D-06 | Propuesta | Columna y brazo de perfiles de aluminio | Posicionar cámara centrada; perfil y altura dependen de óptica y rigidez |
| D-07 | Candidatos, sin selección final | FLIR BFS-U3-200S6M-C y Computar V7531-MPZ | Presentación y oferta IN26-1893; falta probar conjunto y confirmar condiciones comerciales |
| D-08 | Solicitado | Detectar colocación con la báscula y automatizar foto/peso | Evitar introducción manual de cada medida |
| D-09 | Aclarado por usuario, 2026-11-04 | 0,1 mm orientativo; no obligatorio para ambas magnitudes | Priorizar variación detectable sobre ruido; sustituye interpretación inicial de límite común |
| D-10 | Arquitectura propuesta | Proceso y dependencias propios para inspección | Permitir ejecución independiente de la adquisición DAQ |
| D-11 | Propuesta de trazabilidad | Mantener inspecciones originales y asignación explícita al ciclo | Gestionar retrasos, reinspecciones y correcciones sin perder evidencia |
| D-12 | Acordado con usuario, 2026-11-04 | Báscula ≤300 € con IVA y conexión; 0,01 g deseado, 0,1 g justo | Buscar alternativas económicas y comprobar repetibilidad real |
| D-13 | Acordado con usuario, 2026-11-04 | Inspeccionar recién desmoldeada y conservar idealmente la colada en fotos | Diseñar apoyo, luz y pesaje para ese estado; temperatura real pendiente |
| D-14 | Acordado con usuario, 2026-11-04 | 2 m inaceptable; 1 m alto pero estudiable; equipos abiertos a alternativas | Revisar focal y estructura |
| D-15 | Recomendación de investigación, sin aprobar compra | Estudiar Computar V3522-MPZ de 35 mm como primera opción | Cubrir 150–200 mm con distancia óptica estimada de 0,63–0,83 m |
| D-16 | Candidatas actualizadas tras ampliación | Comparar U.S. Solid USS-DBS28-50 de 5 kg y SBS-LW-1030 de 3 kg; PCE-BSK 1100 para soporte ligero | Manual U.S. Solid confirma RS-232 continuo y repetibilidad ±0,03 g; entrega a España pendiente. Ninguna validada |
| D-17 | Propuesta pendiente de prueba | Comparar apilado del PPT y backlight fijo fuera de carga | Reducir precarga/cables, a cambio de un puente de carga más complejo |
| D-18 | Propuesta pendiente de prueba | Empezar con apoyo plano y localización holgada antes de ranura ceñida | Evitar imponer forma nominal u ocultar bordes; sujeción de material caliente por validar |
| D-19 | Aclarado por usuario, 2026-11-04 | PP inicial y otros materiales futuros | Apoyo intercambiable y validación por material/condición; no fijar parámetros universales |
| D-20 | Confirmado por usuario, 2026-11-04 | Interesan avance de llenado **y** cambios pequeños en piezas completas | Mantener medidas separadas; no absorber contracción ajustando a un nominal |
| D-21 | Confirmado por usuario, 2026-11-04 | Básculas existentes sin USB ni RS-232; continuar búsqueda sin esperar modelos | Usarlas para comprobaciones manuales; estudiar equipo nuevo dentro de 300 € |
| D-22 | Recomendación, no préstamo solicitado | Probar cámara/lente/backlight antes de cerrar compra | Programas públicos TPL/VA y protocolo preparado; condiciones pendientes |
| D-23 | Recomendación de investigación, 2026-11-04 | Calibrar un mapa del plano con referencia caracterizada y estudiar intrínsecos como complemento | Checkerboard opcional; la escala y el plano reales no proceden de focal/FOV nominales. [Estudio](../hardware/research/calibration_2026-11-04/README.md) |
| D-24 | Protocolo propuesto, no ejecutado, 2026-11-04 | Validar dimensiones con referencia independiente, alturas, recolocación y deriva | Un RMS pequeño o una ráfaga estable no demuestran exactitud. No usar la propia espiral nominal para ajustar escala. [Protocolo](../hardware/research/calibration_2026-11-04/recommended_protocol.md) |

Evidencia: respuestas del usuario, [primera revisión](../hardware/research/2026-11-04_hardware_review.md) y [estudio ampliado](../hardware/research/deep_dive_2026-11-04/README.md). No se ha contactado a proveedores, comprado ni ensayado equipos.

## Regla para futuras actualizaciones

Añadir fecha, fuente y evidencia al resolver una decisión. Si cambia un acuerdo, registrar la sustitución y actualizar requisitos, candidatos y protocolos afectados. Las cuestiones sin respuesta se mantienen en [open_questions.md](open_questions.md).
