# Protocolo propuesto para Machina

2026-11-04. **Diseño de experimento, no ensayo ejecutado.** Las cantidades de capturas son puntos de partida propios, no mínimos normativos ni garantías estadísticas. Vinculado a [definición de medidas](../../../docs/measurement_definition.md) y [primeras comprobaciones de laboratorio](../../../validation/protocols/first_lab_checks.md).

## 1. Fijar la condición de medida antes de calibrar

- Separar ancho local, longitud central proyectada y avance del frente. Definir principio/final del recorrido y qué zona de unión con la colada queda excluida o visible.
- Definir la condición de apoyo y el plano efectivo. Confirmar sección, espesor, altura libre y comportamiento con apoyo; no asumir que una espiral de 3–4 mm tiene su contorno en el suelo.
- Mantener la colada cuando sea posible; registrar cualquier zona oculta como no medida. No completar automáticamente esa zona con el nominal.
- Para contracción, registrar estado térmico/tiempo desde desmoldeo. La estabilización de la lectura de peso no significa que la geometría haya dejado de cambiar. No hace falta decidir ahora la latencia final del software.

**Puerta de decisión:** si no se consigue una condición de altura suficientemente repetible sin deformar lo que queremos medir, una buena calibración 2D no resuelve la longitud espacial libre. Habrá que aceptar longitud proyectada/apoyada, reducir la exigencia o añadir información de altura. El ancho puede seguir siendo útil y debe evaluarse por separado.

## 2. Montar una configuración óptica estable

Cámara aproximadamente perpendicular, estructura rígida y ruta de carga de la báscula separada. Ajustar campo, enfoque, apertura, luz y exposición con la pieza y con una referencia. Bloquear ajustes y guardar la [receta FLIR](flir_computar.md). Mantener inmóvil el patrón durante cada exposición; detenerlo también durante lectura rolling shutter.

Comprobar calentamiento desde arranque observando una referencia dimensional fija y `DeviceTemperature`. Usar la misma condición de adquisición en calibración y medida. Una temperatura electrónica estable no prueba por sí sola estabilidad de toda la estructura: comprobar también las medidas de referencia.

## 3. Obtener una calibración del plano y, si conviene, intrínsecos

### Ruta base: referencia métrica en el plano definitivo

1. Colocar una retícula rígida caracterizada a la altura definida; registrar superficie, espesor y apoyo.
2. Cubrir las zonas donde pueden aparecer piezas. Una placa menor puede trasladarse con referencias conocidas o tomarse en varias posiciones para validación; no unir posiciones desconocidas como si fueran coordenadas globales conocidas.
3. Detectar puntos con refinamiento subpíxel y revisar identificaciones erróneas, desenfoque y saturación. Ajustar primero escala/similitud y homografía como referencias de comparación.
4. Examinar residuos por posición y dirección, además del RMS total. Si persiste distorsión no lineal, comparar modelo de cámara con distorsión o mapa empírico 2D. No aumentar parámetros hasta absorber errores del patrón.
5. Reservar observaciones y, preferiblemente, un artefacto independiente para validar en mm. Los mismos puntos usados para ajustar no bastan.

### Ruta complementaria: `K,D` y pose, mediante patrón inclinado

Para el prototipo haría también una campaña inicial de intrínsecos si el patrón puede fotografiarse con nitidez en distintas orientaciones. Es útil para diagnosticar distorsión y estudiar planos de altura conocida; su aceptación sigue dependiendo de la comprobación dimensional.

- Partir de unas **20–30 vistas útiles** con inclinaciones alrededor de ambos ejes, distintas posiciones y cobertura de centro/bordes/esquinas. Añadir datos si el mapa no se estabiliza. Una ráfaga de 30 imágenes casi idénticas no aporta esa diversidad.
- No reenfocar para conseguir que cada pose se vea bien. Si el patrón completo inclinado sale de la profundidad de campo, ajustar su tamaño/poses y cobertura o volver a la ruta de plano; no mezclar ópticas distintas dentro de una única calibración.
- Como arranque, un modelo pinhole con distorsión radial/tangencial moderada; comparar complejidad usando datos reservados. No activar todos los coeficientes por defecto.
- Capturar al final el patrón en el plano de trabajo, para establecer escala, origen y orientación de medida. Tener solo `K,D` no entrega aún coordenadas del plano en mm.
- Repetir una campaña independiente. Comparar el **mapa y las dimensiones resultantes**, no solo diferencias entre coeficientes correlacionados.

Con 35/75 mm se debe vigilar especialmente la correlación focal–distancia. El patrón movido solo dentro del mismo plano no sustituye a las inclinaciones para estimar intrínsecos. Sin embargo, sí puede ayudar a comprobar o calibrar ese plano.

## 4. Validación independiente que exigiría

| Ensayo | Diseño inicial propuesto | Qué resuelve |
| --- | --- | --- |
| Campo y orientación | Distancias caracterizadas cortas y largas, en centro y cuatro zonas exteriores; horizontal, vertical y diagonal | Sesgos espaciales/direccionales que una escala central oculta |
| Bordes comparables | Artefactos opacos de ancho próximo a 3–4 mm y espesor conocido; después piezas de materiales reales | Separar calibración de coordenadas y localización de la silueta |
| Curva | Artefacto curvo cuya geometría haya sido caracterizada independientemente | Sesgo de longitud central, extremos y suavizado; rectas solas no validan la espiral |
| Capturas sin mover | 30 imágenes de referencia y pieza fría, con ajustes fijos | Ruido de adquisición/algoritmo, sin mezclar recolocación ni enfriamiento |
| Recolocación | 20 retiradas y nuevas colocaciones de la misma pieza fría | Efecto del apoyo, posición y orientación reales |
| Desplazamientos pequeños | Trasladar/girar ligeramente un artefacto rígido dentro del mismo plano, sin reenfocar | Sesgos de muestreo subpíxel que una ráfaga inmóvil puede ocultar; comprobar invariancia de su dimensión |
| Luz y exposición | Variación controlada alrededor de la receta elegida, con artefacto y materiales reales | Desplazamiento de bordes por respuesta fotométrica, contraste y saturación |
| Alturas conocidas | Referencia a 0, 0,5, 1, 2, 5 y 10 mm respecto al plano; reducir rango si la pieza apoyada lo permite | Sensibilidad real a altura y límites del mapa; sin reenfoque |
| Arranque y sesiones | Repetir referencia durante calentamiento y en al menos tres sesiones | Deriva, reinicio y reproducibilidad entre sesiones |
| Material caliente | Serie separada con piezas recién desmoldeadas, estado térmico/tiempo registrados | Cambio físico de pieza y soporte; no llamarlo «ruido de cámara» |

La independencia debe ser real: desplazar la misma placa permite detectar errores del mapa, pero **no descubre un error uniforme de escala de esa placa**. Para este último hace falta una referencia distinta y mejor conocida. Tampoco basta una segunda impresión de la misma impresora sin caracterizarla.

Para la detección de contracción, añadiría después una comparación con un **artefacto estable caracterizado de geometría semejante**, manteniendo posición, iluminación y receta. Es una adaptación del enfoque de comparación de la [guía NPL](https://www.npl.co.uk/special-pages/gpg39_dimensional), no una reducción de incertidumbre ya demostrada. La calibración métrica permanece independiente: nunca reescalar la pieza a su CAD ni a la referencia. Una pieza de PP caliente o que siga envejeciendo no debe convertirse sin estudio en el patrón estable. Una referencia rígida de otro material ayuda a comprobar geometría, pero no reproduce automáticamente la transmisión de luz y los bordes del polímero.

Los artefactos de altura deben evitar que su espesor desconocido se cuele como un supuesto desplazamiento conocido. La cara/puntos medidos y la longitud de referencia se definen explícitamente.

## 5. Criterio de aceptación

No fijar como aceptación «RMS <0,1 píxel». Informar por magnitud y condición:

- sesgo respecto a referencia y su incertidumbre;
- desviación estándar sin mover y tras recolocación;
- peor desviación observada por zona/altura, separada de incertidumbre estadística;
- deriva entre sesiones y rango de temperatura/configuración válidos;
- diferencia mínima distinguible según un criterio de falsas alarmas y detección acordado.

Si se decide que hay que distinguir cambios de 0,1 mm, usarlo como objetivo de detección y calcular qué repetibilidad requiere; no asumir que es el error absoluto certificado. Ver [ejemplo cuantitativo](repeatability_uncertainty.md). Las tolerancias finales siguen abiertas, tal como indicó el usuario.

## 6. Operación futura

Guardar la calibración aprobada y reutilizarla. Incluir una referencia fija fuera de la pieza, si cabe y no afecta al pesaje/apoyo, como control de desplazamiento/escala. Comprobarla al inicio y después de incidentes, ampliando frecuencia según deriva observada. No autorregular la escala usando la propia espiral ni confundir una referencia al ras de base con la altura real del hilo.

Cada lectura deberá conservar imagen original, receta, calibración, medidas y banderas de calidad. Rechazar como no válida una lectura con oclusión, saturación, movimiento o condición fuera del dominio validado; no rellenar silenciosamente números.

## Lo que falta obtener, sin bloquear la investigación

Hay pie de rey y básculas manuales confirmados. Para pasar de propuesta a prueba hacen falta muestras frías/calientes, sección y alabeo observados, disponibilidad de cámara/lente/luz prestadas y alguna referencia dimensional caracterizada. Para validar longitud central con exigencia alta hará falta un método independiente más adecuado que medir con calibre la envolvente exterior de la espiral.

Si solo se puede conseguir una primera sesión con cámara, priorizar **la misma referencia/pieza a varias posiciones y alturas**, conservando imágenes originales y ajustes, antes de producir cientos de imágenes sin controlar esas variables.
