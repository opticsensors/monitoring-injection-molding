# Requisitos de la celda

Actualizado el 2026-11-04 con las respuestas del usuario. **Aportado** significa descrito por el usuario o documentado en las fuentes; no equivale a validación experimental. **Estimación** no es una medición. **Objetivo** expresa lo que se busca conseguir. **TBD** indica una decisión o dato pendiente. Véase [contexto para retomar](research_status.md).

## Pieza y magnitudes

| ID | Parámetro | Valor o requisito | Estado / fuente |
| --- | --- | --- | --- |
| P-01 | Material | PP inyectado inicialmente; otros materiales en futuras campañas | Aclaración del usuario: no diseñar ni validar exclusivamente para PP; grados y condiciones TBD |
| P-02 | Forma | Espiral idealmente plana con colada vertical | Aportado por el usuario |
| P-03 | Diámetro del hilo | Aproximadamente 3–4 mm; el script ideal usa ancho de 3 mm | Usuario / [geometría](geometry_reference.md) |
| P-04 | Longitud real del hilo | X mm / TBD por pieza | No medida; no rellenar con la longitud teórica |
| P-05 | Longitud geométrica de referencia | 510,508806 mm por la línea central | Cálculo del script; excluye la colada vertical |
| P-06 | Peso real | TBD medido; estimación del usuario del orden de 100 g o menos con colada | No es un máximo verificado |
| P-07 | Envolvente de la pieza | Aproximadamente 150 × 150 mm; reservar 200 × 200 mm como hipótesis conservadora | Usuario; confirmar márgenes de colocación |
| P-08 | Deformación fuera del plano | Algunas zonas apoyadas; otras hasta aproximadamente 10 mm sobre el apoyo | Usuario; definir referencia exacta de altura |
| P-09 | Colada | Conservarla idealmente en las fotografías; altura, diámetro y unión TBD | Prever alojamiento y oclusión. Mantenerla también en pesaje como hipótesis de trabajo |
| P-10 | Estado al medir | Recién desmoldeada; temperatura real todavía sin medir | Confirmado por usuario. Evaluar calor sobre soporte y pesaje sin imponer una espera larga |

## Prestaciones buscadas

| ID | Requisito | Estado / criterio pendiente |
| --- | --- | --- |
| M-01 | 0,1 mm como orientación para el estudio dimensional; distinguir variación real del ruido | El usuario aclara que no es un límite obligatorio para ambas magnitudes. Definir variación mínima detectable y evaluar longitud/diámetro por separado |
| M-02 | Medir el recorrido para **avance de llenado y contracción de piezas completas** | Ambas finalidades confirmadas. Separar magnitudes: [definición](measurement_definition.md). Condición espacial/proyectada/apoyada por cerrar |
| M-03 | Medir diámetro del hilo | Definir posiciones, diámetro mínimo/medio/máximo y cómo tratar ovalidad, rebabas y extremos |
| M-04 | Medir peso: 0,01 g deseado; 0,1 g mínimo y justo | Preferencia del usuario; comprobar repetibilidad y sensibilidad real, no solo división de pantalla |
| M-05 | Conservar imagen y peso asociados a una misma inspección | Objetivo de trazabilidad |
| M-06 | Identificar calibración y versión del método de medida | Propuesta para poder reproducir resultados |
| M-07 | Mostrar inspecciones no válidas o pendientes | Evitar presentar una oclusión o una asociación desconocida como una medida válida |

El objetivo metrológico no es una tolerancia de fabricación de la pieza. Los límites de aceptación/rechazo del producto están por definir. La resolución de la cámara o de la báscula tampoco demuestra por sí sola el error de medida.

## Operación e integración

| ID | Requisito | Estado |
| --- | --- | --- |
| O-01 | Introducción manual de la pieza | Concepto inicial |
| O-02 | Detección automática a partir de la báscula | Solicitado; umbral, estabilidad y tiempos TBD |
| O-03 | Esperar una lectura estable y adquirir foto automáticamente | Solicitado; concretar criterio y disparo |
| O-04 | Transferencia automática de imagen y peso al PC | Solicitado |
| O-05 | Asociar la inspección al ciclo pertinente | Solicitado; resolver identificación explícita, piezas retrasadas y repeticiones |
| O-06 | No repetir capturas indefinidamente con la pieza apoyada | Propuesta: rearmar tras retirada confirmada |
| O-07 | Conservar inspecciones pendientes ante caída de red | Propuesta de arquitectura, todavía sin implementar |
| O-08 | Mantener independiente el proceso de inspección de la adquisición DAQ | Arquitectura prevista en el mismo repositorio |
| O-09 | Colocar y medir automáticamente con poca espera | Prioridad actual hardware; no bloquear el estudio pidiendo un tiempo numérico de software |

## Condicionantes de hardware

- Priorizar el estudio de cámara 2D, óptica convencional y backlight.
- Ópticas telecéntricas descartadas en esta fase por coste y volumen/peso de la propuesta recibida. Se ha localizado una referencia comercial de peso/longitud coincidentes con el relato del usuario, sin confirmar que sea la ofertada: [investigación óptica](../hardware/research/deep_dive_2026-11-04/optics_and_lighting.md).
- Estructura conceptual con perfiles de aluminio. El usuario descarta 2 m; 1 m ya resulta alto, aunque se puede considerar. Priorizar menos de 1 m de distancia cámara-pieza. La base de 300 × 300 mm del PowerPoint sigue siendo una hipótesis por dimensionar.
- Cámara y óptica recomendadas por STEMMER, no seleccionadas de forma definitiva; comparar alternativas. El estudio actual prioriza focal de 35 mm frente a 75 mm.
- Soporte transparente, posiblemente de metacrilato con ranura/alojamiento de colada, permitido como línea de estudio. Verificar que no imponga dimensiones ni oculte contornos; no es un diseño aprobado.
- La cámara y el soporte deben respetar el FOV, el enfoque, la accesibilidad y la estabilidad mecánica.
- La báscula debe soportar la masa de la pieza más todos los elementos realmente apoyados en ella. La tara no elimina la carga física.
- Soporte más backlight: el usuario estima unos 2 kg; hay que pesarlos. Estudiar tanto apilado como panel fijo fuera de la carga de pesaje.
- Báscula: máximo **300 € con IVA y conexión al PC**. Presupuesto total de construcción no cerrado. Los 2.000–3.000 € del PowerPoint siguen siendo una estimación histórica.

## Condiciones para cerrar la especificación

**Medios disponibles confirmados:** pie de rey y básculas de laboratorio **sin USB ni RS-232**. El usuario no conoce los modelos y pide continuar buscando sin depender de ellos. Se consideran medios para pruebas manuales; no volver a pedir conectividad/modelo como condición para avanzar. Anotar capacidad/división visibles al hacer cada prueba, sin asumir exactitud de referencia. El usuario puede aportar el grado de PP, pero no debe convertirse en una restricción permanente del diseño.

Medir masa, temperatura, altura y carga total; resolver definición de longitud/diámetro y efecto del soporte. Confirmar variación detectable con el [plan de validación](../validation/README.md). La identificación pieza/ciclo permanece como trabajo de integración posterior; las preferencias de precisión, presupuesto y estado recién desmoldeado ya están respondidas.
