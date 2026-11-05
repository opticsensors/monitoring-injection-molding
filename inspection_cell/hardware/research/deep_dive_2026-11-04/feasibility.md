# Dictamen de viabilidad y siguiente prototipo

Investigación del 2026-11-04. **La arquitectura del PowerPoint es viable como punto de partida; sus prestaciones metrológicas todavía no están demostradas.** Conservar cámara cenital, luz posterior y pesaje automático. Cambiaría la focal y haría el apoyo intercambiable antes de cerrar la estructura. No compraría el conjunto completo basándome solo en megapíxeles y decimales.

## Qué podemos afirmar y qué no

| Función | Dictamen actual | Evidencia que falta para cerrar |
| --- | --- | --- |
| Detectar colocación, leer peso y disparar foto desde PC | Viable en principio con modelos concretos: manuales documentan salida serie automática y disparo software de cámara | Unidad recibida, trama, retirada, estabilidad y captura; [integración física](../../electrical/acquisition_feasibility.md) |
| Ancho del hilo próximo a 3–4 mm | Prometedor con 20 MP y buen contraste; 0,1 mm merece ensayo | Borde real, sección, recolocación, altura y comparación independiente; no equivale a diámetro 3D |
| Avance de llenado de una espiral incompleta | Prometedor si frente e inicio son visibles | Definición del extremo y alineación; distinguir contracción de falta de llenado |
| Cambios pequeños de longitud en espiral completa | Posible bajo una condición de apoyo reproducible; es el punto dimensional más exigente | Control/observación de altura, longitud de referencia y ensayo entre piezas |
| Longitud espacial libre con alabeo desconocido de hasta 10 mm | **No recuperable de forma general con una sola proyección 2D** | Controlar la forma durante medida o añadir información independiente de altura |
| Pesaje con división 0,01 g y hasta varios kg de precarga | Hay candidatas económicas documentadas | Detectar 10 mg sobre la carga real, deriva térmica, cable y excentricidad; no garantizado por la división |
| Mismo ajuste para todos los materiales futuros | No demostrado | Validar apoyo, contraste y temperatura por familia/condición; conservar modularidad |

El usuario ha confirmado **ambas finalidades de longitud: avance de llenado y contracción de piezas completas**. La [definición de medidas](../../../docs/measurement_definition.md) evita mezclarlas. No ajustar cada pieza a un nominal de 510,508806 mm y devolver ese valor como si se hubiera observado.

## Por qué longitud y ancho no comparten un error absoluto

Un cambio de escala del 0,1 % representa 0,004 mm sobre 4 mm, pero 0,511 mm sobre 510,5 mm. En el modelo de cámara a 800 mm, elevar uniformemente 2 mm una curva respecto al plano calibrado produce aproximadamente **+0,010 mm de ancho y +1,279 mm de longitud**. Es un ejemplo calculado sin ruido, no un resultado experimental. El alabeo real también modifica la proyección del recorrido; no basta corregir con la altura máxima. [Modelo reproducible y límites](calculation_notes.md).

Un sesgo constante puede permitir comparar piezas. Sin embargo, a 800 mm una contracción uniforme del 0,1 % y una subida de 0,8 mm se compensan exactamente en un modelo pinhole. Una regla fija en la base no mide la altura de la pieza. Véase [variación detectable](detectable_variation.md); es un contraejemplo calculado, no una predicción del alabeo real.

La longitud de una cadena binaria también depende del estimador: contar pasos ortogonales/diagonales puede introducir un sesgo aun aumentando píxeles. Conviene conservar los niveles de gris y validar bordes y recorrido por separado. Esto no exige programar ahora la aplicación, pero sí evita comprar hardware a partir de una hipótesis incorrecta sobre el algoritmo.

## Montaje que ensayaría primero

1. **Cámara mono de unos 20 MP con focal de 35 mm.** Para la FLIR y un cuadrado útil de 150–200 mm, la estimación de distancia óptica es 0,635–0,835 m. La de 75 mm sube a 1,36–1,79 m y encaja mal con la altura aceptada. Confirmar distancia frontal real, margen y calidad en esquinas con el proveedor. [Alternativas de lente](lens_alternatives.md).
2. **Columna rígida, brazo corto y arriostrado**, con ajustes bloqueables. Empezaría dimensionando 40 × 40 para la columna; el perfil concreto y las uniones importan. La base de 300 × 300 mm no está validada: la SBS mide 300 mm de fondo según la imagen comercial y no deja margen por ese lado. [Evaluación mecánica](mechanical_frame.md).
3. **Apoyo transparente reemplazable**, inicialmente plano o con alivio local para la unión de colada si las fotos/cotas lo confirman. La ranura completa sigue siendo una opción a ensayar; puede ocultar bordes o imponer la forma y borrar la contracción que interesa detectar. [Soporte y materiales](fixture_and_materials.md).
4. **Backlight de prueba antes del definitivo.** Comparar difuso y semicollimado con piezas reales. La colimación de luz puede mejorar el borde, pero no hace telecéntrica a la cámara ni recupera longitud 3D. Hay programas públicos de préstamo de TPL y VA, sujetos a condiciones. [Paneles y ensayos](lighting_candidates.md).
5. **Comparar U.S. Solid de 5 kg y Steinberg de 3 kg** si el panel queda sobre la báscula. Si se logra un apoyo ligero, añadir PCE de 1,1 kg. Mantener abierta la alternativa de luz fija y puente soportado únicamente por la báscula; primero comprobar que merece su mayor complejidad mecánica. [Pesaje ampliado](weighing.md).

La referencia de calibración también importa: una cuadrícula comercial económica no garantiza exactitud de 0,1 mm. Priorizar una referencia conocida prestada o caracterizada, con comprobación independiente; [fichas y plan de calibración](calibration_references.md).

La cámara de STEMMER sigue siendo candidata; no se ha demostrado que otra sea superior. Una lente de 35 mm más barata solo interesa si proporciona bordes suficientemente estables a la magnificación de uso. El número comercial de megapíxeles de la lente no sustituye esa prueba.

## Costes que cambian la decisión

- **Steinberg SBS-LW-1030:** 178 € con IVA observado; estimación de 218–238 € añadiendo una reserva de cable/adaptador. Repetibilidad no publicada de forma separada.
- **U.S. Solid USS-DBS28-50:** tienda alemana muestra aproximadamente 105–119 € según lectura; 5 kg / 0,01 g, USB y RS-232 anunciados. Manual específico: repetibilidad y linealidad ±0,03 g. Entrega a España, fiscalidad y USB exacto pendientes. No es una oferta entregada de 105 €.
- **PCE-BSK 1100:** escenario de 233,29 € con IVA, adaptador y transporte; solo admite 1,1 kg de carga bruta. Confirmar presupuesto conjunto.

Fuentes comerciales y supuestos en la [comparativa vigente](../../components/scales_shortlist.md). Las básculas existentes no tienen USB **ni RS-232**; se utilizarían para ensayos manuales, sin frenar la búsqueda de una nueva.

La luz puede costar más que la báscula: el Edmund/EFFILUX 200 × 200 del PPT figura a **765 € sin IVA** y pesa **1,9 kg**. No dar por incluidos fuente, cables o controlador. Un panel doméstico sirve para investigar contraste inicialmente, pero no queda validado para metrología por producir una silueta visible. [Fuente y comparación de paneles](lighting_candidates.md).

## Tres comprobaciones que más reducirían la incertidumbre

1. **Piezas reales:** masa de 3–5 piezas con colada; fotos cenital, lateral a ras del apoyo y parte inferior de la unión; altura de colada y ancho/espesor del hilo. Incluir una incompleta y una alabeada si existen. No hace falta identificar los modelos de las básculas para seguir investigando.
2. **Repetición y apoyo:** misma pieza fría, diez retiradas/recolocaciones en báscula y medidas suaves de ancho en zonas identificadas; comparar apoyo libre y soporte provisional. Después caracterizar por separado la evolución recién desmoldeada. El calibre no proporciona por sí solo la longitud curva de referencia.
3. **Préstamo óptico:** muestras con colada, plano calibrado, alturas conocidas y referencia independiente; pedir imágenes originales y datos de repetición, no solo una imagen que parezca nítida. [Ensayo concreto](../../../validation/protocols/first_lab_checks.md) y [consulta preparada](supplier_questions.md).

Se continuará con 2D si las pruebas separan la variación buscada del ruido y sesgos de apoyo/altura. Si solo falla la longitud de pieza libre, no sustituirla silenciosamente por una longitud nominal: redefinir condición de medida o evaluar una medición de altura complementaria. El rechazo de una condición no invalida automáticamente el ancho o el avance de llenado.

## Estado de las evidencias

Se han leído manuales, artículos experimentales y diez hilos de experiencias; se han ejecutado cálculos sintéticos. **No hay todavía ensayos físicos, selección de compra ni CAD validado.** La revisión nativa del CAD quedó pendiente al detenerse el control del ordenador con Escape. Las [experiencias de usuarios](field_reports.md) sirven para preparar pruebas, no como especificación del equipo propuesto.
