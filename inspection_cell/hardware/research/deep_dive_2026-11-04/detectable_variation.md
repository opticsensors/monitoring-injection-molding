# Detectar variación no es lo mismo que garantizar exactitud absoluta

Este punto responde a la preocupación del usuario: que las diferencias entre piezas no queden enterradas en ruido. **Un sesgo constante no impide necesariamente comparar piezas; un sesgo que cambia con cada colocación sí puede hacerlo.** Los ejemplos siguientes son modelos, no ensayos ni tolerancias propuestas.

## Qué se cancela al comparar y qué permanece

Supongamos una lectura `y = (1+a)·x + b + ε`, con escala `a`, offset `b` y ruido `ε`. Si `a` y `b` se mantienen constantes entre dos medidas, el offset desaparece en la diferencia y queda `Δy = (1+a)·Δx + Δε`. Si cambian altura, borde, foco, material o temperatura, la cancelación deja de estar garantizada.

Por tanto, una longitud con un sesgo fijo de 1 mm podría servir para distinguir una variación de 0,2 mm **si** la repetición, escala y condición son suficientemente estables. No se concluye que nuestro conjunto tenga esa estabilidad. Tampoco un buen ensayo de repetibilidad demuestra que la longitud absoluta sea correcta.

Los [cálculos de altura](calculation_notes.md) muestran sensibilidad geométrica respecto a un plano fijo. Una elevación constante de toda la pieza se puede incluir en una calibración adecuada. El problema de comparación es **cuánto cambia esa condición entre piezas o al recolocarlas**, además de cuánto desconocemos la forma espacial. No convertir el ejemplo de 0,157 mm de altura en una tolerancia obligatoria de fabricación del soporte.

## Una ambigüedad especialmente relevante para contracción

En el modelo pinhole, para una pieza plana a altura `h` y un factor dimensional de pieza `s`, el tamaño observado respecto al plano de referencia es proporcional a:

`s · Z/(Z-h)`.

Una sola imagen no separa ambos factores sin información adicional. A Z=800 mm, una reducción dimensional uniforme del 0,1 % (`s=0,999`) y una elevación de 0,8 mm se compensan exactamente en este modelo: `0,999·800/(800-0,8)=1`. **Es un contraejemplo de observabilidad**, no una predicción de cómo se deforma la espiral.

Una regla fija sobre el plano de apoyo puede detectar deriva de la cámara, pero no sube con las zonas alabeadas. Medir a la vez longitud y ancho tampoco elimina automáticamente esta ambigüedad: ambos pueden cambiar por el mismo factor de escala. Un cociente como longitud/ancho elimina esa escala, pero también elimina una contracción isotrópica ideal.

El peso aporta otra característica de calidad, pero una pieza puede contraerse al enfriarse prácticamente sin cambiar su masa real. La comparación de masa y geometría ayuda a investigar llenado, sección o material; no convierte la masa en un sensor de altura. Los ejemplos de masa de [calculation_notes.md](calculation_notes.md) mantienen densidad constante y no son un modelo de contracción de una misma pieza.

## Cómo decidir con los primeros ensayos

| Ensayo separado | Qué estima | Qué no demuestra |
| --- | --- | --- |
| Misma referencia estable, sin tocar | Ruido de adquisición/localización | Error por recolocación ni exactitud absoluta |
| Misma pieza fría, retirar y recolocar | Variación de apoyo, posición y manipulación | Evolución caliente ni variación real entre piezas |
| Referencia conocida independiente en centro/esquinas/alturas | Sesgo y dependencia geométrica bajo condiciones ensayadas | Todas las formas/materiales futuros |
| Varias piezas de ciclos/condiciones distintos | Variación observada entre piezas | Qué parte procede del proceso si el ruido anterior no está cuantificado |
| Serie recién desmoldeada + referencia estable intercalada | Evolución de pieza y parte de la deriva del sistema | Una corrección térmica universal |

Esta separación también aparece en el [estudio confocal de 2022](existing_solutions.md): comprobó repetibilidad con piezas estabilizadas para no confundirla con cambio dimensional. No adoptamos su instrumentación ni sus cifras como prestaciones propias.

Como cribado, comparar la diferencia que interesa con la dispersión de **recolocación** y con cambios por altura/luz, no solo con el ruido de veinte fotos idénticas. El [protocolo inicial](../../../validation/protocols/first_lab_checks.md) conserva datos individuales y distingue sesgo, desviación típica y deriva. Definir un límite de aceptación después de ver el tamaño real de las variaciones; 0,1 mm sigue siendo orientación.

## Consecuencia para el prototipo

La cámara 2D no queda descartada. El apoyo y la condición de medida deben hacer observable la variación elegida. Para llenados claramente incompletos, el frente puede aportar una señal grande. Para contracción pequeña, la estabilidad de altura/forma y el método de referencia merecen más esfuerzo. Si solo una magnitud falla, conservar las otras y declarar la limitación; no ocultarla con un ajuste al nominal.
