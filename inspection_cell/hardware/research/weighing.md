# Pesaje y detección de pieza

## Datos disponibles

El peso real sigue sin medirse; el usuario estima **unos 100 g o menos con colada**, más quizá **2 kg de soporte y panel**. Quiere **0,01 g**, acepta 0,1 g como mínimo justo y fija **300 € con IVA y conexión al PC**. Estos incrementos no equivalen automáticamente a exactitud, repetibilidad o incertidumbre. Inspección recién desmoldeada.

La [comparativa actual](../components/scales_shortlist.md) reúne U.S. Solid de 5/3,2 kg, SBS-LW-1030 y PCE-BSK 1100/5100, precios y manuales. El [estudio ampliado](deep_dive_2026-11-04/weighing.md) registra discrepancias web/manual, precarga, calor, estática y una ruta secundaria de 300 g con soporte muy ligero. Los modelos de las [diapositivas 9 y 10](../../docs/presentation_summary.md) son referencias históricas. El [estudio de soporte](deep_dive_2026-11-04/fixture_and_materials.md) compara cargar el panel sobre la báscula con mantenerlo fijo fuera de la carga.

## Selección pendiente

- Rango de masa de la pieza, incluyendo o excluyendo colada según receta.
- Masa de soporte, placa y panel que realmente cargan sobre la plataforma.
- Capacidad, resolución, repetibilidad, linealidad y efecto de carga excéntrica.
- Acceso a lectura estable, unidades, tara, sobrecarga y códigos de error.
- Interfaz y protocolo: RS-232, USB o Ethernet no describen por sí solos el formato de datos.
- Frecuencia de actualización y tiempo de estabilización con la pieza real.
- Tamaño útil de plataforma y transmisión de fuerzas por cables o contactos laterales.

La tara descuenta la indicación del soporte, pero la báscula sigue soportando su masa. No fijar una capacidad de 3, 6 u 8 kg sin conocer la carga total.

## Automatización prevista

Detectar presencia mediante diferencia respecto a la tara, esperar estabilidad y disparar la fotografía desde el PC. Usar bandas distintas de entrada/salida y una ventana temporal configurable para evitar oscilaciones del estado. Obtener valores de configuración de ensayos, no del diámetro nominal ni del ruido de una única muestra.

El evento estable debe vincular peso, imagen e identidad de inspección. Registrar retirada antes de rearmar para que la misma pieza no genere capturas repetidas. La báscula no identifica el ciclo de inyección; esa asociación requiere otro mecanismo.

## Evidencia necesaria

Lecturas repetidas de referencias y de piezas, variación de tara, recolocaciones, carga excéntrica, interferencia del cableado, cambios térmicos y reconexión del equipo. Véase [protocolo de pesaje y disparo](../../validation/protocols/weighing_and_trigger.md).
