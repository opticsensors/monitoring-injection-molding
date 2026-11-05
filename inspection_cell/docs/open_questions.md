# Preguntas abiertas e investigaciones

Actualizado tras las respuestas del 2026-11-04. El usuario ha confirmado **avance de llenado y contracción de piezas completas**, y básculas existentes sin USB ni RS-232. No esperar sus modelos para investigar. Las preferencias ya resueltas están en [research_status.md](research_status.md); no volver a pedir presupuesto, si se pueden cambiar equipos o si la pieza llega caliente.

## Prioridad 1: definir qué se mide

| ID | Pregunta | Cómo resolverla |
| --- | --- | --- |
| Q-01 | ¿La longitud requerida es la espacial de la pieza libre, su proyección cenital o la longitud bajo un apoyo definido? | Acordar definición y método de referencia antes de validar 2D |
| Q-02 | Con colada conservada en la foto, ¿qué región próxima a su unión es medible y dónde empieza el eje? | Mantenerla en pesaje como hipótesis; resolver oclusión y región de medida |
| Q-03 | ¿Qué variaciones reales entre piezas deben distinguirse del ruido? | 0,1 mm ya es orientación, no límite obligatorio. Medir dispersión de recolocación y comparar piezas |
| Q-04 | ¿Qué diámetro interesa: puntos concretos, distribución, mínimo, media, máximo? ¿La sección es circular? | Medir piezas reales y definir estadísticos; una vista no identifica toda la ovalidad |
| Q-05 | ¿Cuál es la masa real con colada y la carga de soporte/panel? | Comprobar estimaciones ≤100 g y unos 2 kg; preferencia ya fijada en 0,01 g, mínimo 0,1 g |
| Q-06 | ¿Qué temperatura tiene la pieza recién desmoldeada y cuánto calienta el apoyo en uso repetido? | Medir condiciones reales para elegir material y comprobar deriva; no cambiar por defecto a inspección fría |

## Prioridad 2: resolver hardware y metrología

- Medir deformación real, referencia de esos 10 mm y altura de la colada.
- Probar si un soporte controla altura sin alargar la espiral, deformar el hilo ni ocultar bordes.
- Verificar FOV con margen, distancia frontal, enfoque y estabilidad con **35 mm** como primera alternativa; 50 mm si basta el campo menor. Los 75 mm no encajan bien con la altura preferida.
- Evaluar contraste de los materiales/colores disponibles con backlight, exposición, transmisión, sombras y uniformidad en todo el campo.
- Elegir qué elementos apoyan en la báscula: pieza, soporte, placa transparente y/o panel. Medir su masa y las fuerzas de los cables.
- Dimensionar rigidez del brazo, anclaje, ajuste y aislamiento respecto a la plataforma de pesaje.
- Completar repetibilidad/linealidad y pinout/trama de SBS-LW-1030; confirmar revisión y discrepancias de U.S. Solid USS-DBS28-50. Comparar PCE-BSK 1100 si la carga puede bajar de 1,1 kg. Los modos automáticos están documentados; falta ensayo sobre precarga real.
- Confirmar precio entregado y accesorios exactos dentro de 300 € con IVA; las páginas PCE discrepan en transporte y el envío U.S. Solid a España no está cerrado.
- Vision Datum BTL-.055X-465-H1LM coincide aproximadamente en peso/longitud con la telecéntrica relatada, pero no está confirmada como modelo STEMMER. No es una prioridad de compra ni bloquea el prototipo convencional.
- Renovar la oferta IN26-1893 y completar costes de iluminación, estructura, calibración y montaje cuando proceda comprar.

## Prioridad 3: resolver operación e integración

- Definir asociación inequívoca de cada pieza a máquina, sesión y ciclo, incluidas piezas atrasadas.
- Confirmar si hay una o varias piezas por ciclo, llenados parciales y posiciones del selector de paso.
- Definir cadencia requerida, umbral de presencia, ventana de estabilidad y retirada.
- Acordar conservación de imágenes, ubicación de almacenamiento y política de reinspecciones.
- Definir convivencia entre resultado automático y edición manual de peso/longitud.
- Ampliar mensajes, almacenamiento, History y exportaciones para diámetro, imagen y trazabilidad de calibración.

Los trabajos de esta lista son pendientes; los documentos de validación describen ensayos propuestos, no resultados existentes.
