# Soluciones existentes y cercanía al problema

## Un antecedente específico: espirales de inyección y escáner plano

[Jones, Callahan y Bruce, 2011](https://www.iastatedigitalpress.com/jtmae/article/14168/galley/12932/download/) ([PDF local](sources/Jones_2011_spiral_flatbed_scanner.pdf), pp. 3–8) estudian espirales de HDPE. Escanearon **solo el último tramo**, aproximadamente una pulgada, a 4800 dpi, y midieron manualmente en AutoCAD. Compararon con proyector de perfiles y realizaron un estudio con 10 piezas, 3 operadores y 3 repeticiones.

Definen dos finales distintos: desviación del borde exterior respecto al arco e intersección del frente de llenado con una línea central. La definición cambia el resultado y su repetibilidad. Su comprobación con bloque patrón encontró un sesgo de escala de aproximadamente **0,53 %**. La tabla 3 comunica R&R de **0,00153 pulgadas = 0,038862 mm**, una magnitud de variación del estudio, **no un error máximo garantizado ni una desviación estándar identificada aquí**. Señalan problemas de enfoque por encima de unos 2,54 mm sobre el cristal. Adquirir aquel tramo requería alrededor de un minuto y medirlo unos cinco minutos.

**Lectura crítica propia:** su resultado no demuestra la longitud espacial completa de 510 mm, piezas a 10 mm de altura ni inspección automática recién desmoldeada. El porcentaje R&R depende de la amplia variación entre las piezas elegidas; no demuestra sensibilidad suficiente para una campaña con variaciones pequeñas.

## Qué cambia en nuestra definición de medida

Conviene separar tres resultados posibles:

| Resultado | Pregunta que responde | Riesgo de confusión |
| --- | --- | --- |
| Longitud del recorrido observado | ¿Cuánto mide la línea central visible de esta pieza bajo una condición de apoyo? | Incluye efectos de contracción, deformación y apoyo; necesita definir extremos |
| Posición del frente de llenado respecto al molde | ¿Hasta dónde llegó el material en la cavidad? | No es automáticamente la longitud de una pieza contraída; registrar frente con el nominal exige un modelo y referencias |
| Distancia entre extremos o envolvente | ¿Qué espacio ocupa la pieza? | Es más fácil de calcular, pero no sustituye longitud de hilo |

El usuario confirmó durante el estudio que interesan **ambas cosas: avance del llenado y cambios dimensionales en piezas completas**. Se propone conservar longitud proyectada observada y posición del frente como magnitudes separadas; condición de apoyo y extremos siguen pendientes. No ajustar todos los radios al nominal si el objetivo es detectar contracción: ese ajuste puede borrar la variación buscada. Véase [definición de medidas](../../../docs/measurement_definition.md).

## Otros antecedentes que ayudan a separar las dos finalidades

**Microespirales, 2019 — [artículo](https://doi.org/10.3390/mi10050335), [texto completo archivado](sources/Micro_spiral_process_fingerprints_2019.xml).** El apartado 2.2 describe imágenes con microscopio Keyence VHX-6000 y cálculo de avance por cuadrantes y ángulo del último arco. Las piezas son de POM, con secciones rectangulares de 1, 0,5 y 0,25 mm de lado. La geometría conocida permite convertir posición angular en longitud de llenado. **Lectura crítica:** es una referencia útil para `s_frente_nominal`, no una demostración de medir contracción libre en nuestro hilo de 3–4 mm. El estudio correlaciona variables de proceso con avance; esa correlación no sustituye una validación dimensional independiente ni se transfiere de POM a otros materiales.

**Plantilla graduada de espiral, ANTEC 2013 — [Menotti y colaboradores, PDF institucional](https://backend.orbit.dtu.dk/ws/files/56154544/INITIAL_VERIFICATION.pdf), p5 del PDF.** Para estudiar calentamiento del molde con ABS, utilizaron una copia polimérica del inserto con marcas cada milímetro y registraron longitud y peso. **Aplicación posible:** plantilla de observación manual del frente para el primer ensayo, siempre identificada como nominal. No demuestra exactitud de 0,1 mm ni mide el recorrido libre de una pieza contraída. No se ha fabricado la plantilla ni archivado este PDF; se conserva el enlace y el método relevante.

**Medición 3D recién desmoldeada, 2022 — [Saeidi Aminabadi y colaboradores](https://doi.org/10.3390/technologies10040095), [PDF local](sources/Aminabadi_2022_inline_3D_moulded_parts.pdf).** Sistema para una pieza curva negra brillante: sensor confocal, movimiento lineal/rotativo, robot, pesaje e identificación de pieza. La operación registraba 30–32 s entre fabricación y medida; no adoptamos ese tiempo para nuestra celda. Sujeción por vacío y recolocación introdujeron deformación/desplazamiento, pese a usar instrumentación precisa.

La comprobación de repetibilidad de la sección 3.4 utilizó **piezas estabilizadas al menos 48 h a unos 23 °C**, no piezas que siguieran contrayéndose. Los autores reportan repetibilidad del orden de ±5–10 µm según condición, con estudio que separa errores sistemáticos. No es una incertidumbre absoluta transferible a nuestra cámara, ni prueba equivalente de comportamiento caliente. **Lección útil:** ensayar por separado el instrumento con pieza estable, el efecto de la sujeción y la evolución recién desmoldeada. El sistema confocal es una alternativa tecnológica documentada, no una propuesta económica equivalente al montaje actual.

## Comparación de conceptos

| Concepto | Qué aporta | Qué no resuelve | Situación |
| --- | --- | --- | --- |
| Cámara cenital convencional + backlight | Imagen rápida, contorno completo si es visible, integración con peso | Alturas variables, parte oculta por colada, transparencia y plano de calibración | Primera vía de prototipo |
| Escáner plano | Alternativa económica para estudiar muestras frías y planas, si ya existe uno disponible | Colada, altura de 10 mm, pieza caliente y cadencia; dpi nominal no es calibración | Referencia exploratoria, no sustitución propuesta de la celda |
| Proyector de perfiles / equipo óptico de laboratorio | Comparación independiente de segmentos y anchuras | Disponibilidad y coste; medir todo el recorrido sigue requiriendo un método | Útil si el laboratorio dispone de él; no confirmado |
| Óptica telecéntrica | Reduce cambio de escala con altura dentro de sus especificaciones | No recupera longitud 3D ni ve detrás de una colada; FOV grande encarece y aumenta volumen | No prioritaria según restricciones del usuario |
| Cámara cenital + vista lateral de control | Puede detectar apoyo incorrecto o alabeo evidente | Una vista lateral puede solapar varias vueltas y no reconstruye toda la espiral | Opción de diagnóstico, no promesa de corrección 3D |
| Escaneo 3D / varias vistas calibradas | Información de altura si observa toda la superficie | Coste, calibración, oclusiones y material translúcido; 3D barato no implica ±0,1 mm | Solo reconsiderar si la longitud espacial libre resulta imprescindible |

La necesidad actual es demostrar el primer concepto con piezas reales. No se ha encontrado evidencia que permita garantizar por bibliografía todas las prestaciones simultáneamente.
