# ¿Hace falta un checkerboard?

2026-11-04. **El ajedrez no es obligatorio; una referencia dimensional defendible sí lo es para expresar medidas absolutas en mm.**

| Alternativa | Ventaja | Límite para esta celda |
| --- | --- | --- |
| Checkerboard rígido caracterizado | Métodos maduros y esquinas subpíxel | Planitud, escala y posición real de esquinas deben conocerse; imprimir al 100 % no lo certifica |
| ChArUco rígido caracterizado | Identifica esquinas y permite vistas parciales | Sigue siendo un patrón físico que hay que caracterizar; los códigos no mejoran su exactitud de fabricación |
| Retícula de círculos/puntos | Compatible con placas de vidrio y contraluz | En vistas oblicuas, el centro de una elipse observada no es en general la proyección del centro del círculo; usar detector/modelo adecuado |
| Retícula densa en el plano definitivo | Calibración directa imagen→mm, sin recuperar toda la cámara | Solo sirve en ese plano y dentro del área validada; comprobar puntos intermedios y alturas |
| Regla o dos marcas conocidas | Comprobación rápida de escala a bajo coste | No mide toda la distorsión ni ambas direcciones; medición manual de bordes y planitud pueden dominar |
| Punto/referencia movido con una mesa XY calibrada | Permite construir un mapa sin una placa de ajedrez | Traslada la exigencia metrológica a la mesa, sus movimientos y la altura; probablemente innecesario para el primer prototipo |
| Líneas rectas / «calibration harp» | Comprobar o estimar distorsión sin placa plana | Rectitud no fija por sí sola escala métrica ni pose; haría falta otra referencia |
| Autocalibración con escena natural | Evita un patrón diseñado | Exige textura, múltiples vistas y geometría informativa; poco atractiva para una espiral caliente, lisa y una cámara fija |

Fuentes: [Zhang](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/tr98-71.pdf), [OpenCV ChArUco](https://docs.opencv.org/4.13.0/da/d13/tutorial_aruco_calibration.html), [Heikkilä, círculos](https://ieeexplore.ieee.org/document/879788/), [Tang et al., harp](https://arxiv.org/abs/1212.5656), [Barazzetti et al., targetless](https://isprs-archives.copernicus.org/articles/XXXVIII-5-W16/335/2011/). Alcance de acceso en [literatura](literature_review.md).

## Qué compraría o pediría prestado para la fase metrológica

**Primera opción:** placa rígida con retícula y coordenadas caracterizadas, compatible con el detector elegido y con una superficie suficientemente plana. Elegir vidrio con patrón en cara de observación o cerámica según iluminación, manipulación y certificado disponibles. No comprar solo por la palabra «calibration» ni por tener una cuadrícula bonita.

Para el campo útil 150–200 mm, pediría información sobre:

1. Separaciones reales X/Y y, si es posible, coordenadas individuales con incertidumbre; distinguir tolerancia de fabricación, certificado de conformidad e informe de medición.
2. Planitud en el área utilizada y condiciones de apoyo. El soporte y la temperatura pueden modificar la placa.
3. Posición de la capa del patrón, espesor y expansión térmica. Poner las marcas a la altura definida, no asumir que apoyar cualquier placa reproduce el plano de la pieza.
4. Compatibilidad con luz transmitida/reflejada y contraste a la apertura real. Si el patrón queda detrás de vidrio o metacrilato en el camino de observación, ese camino óptico necesita tratamiento explícito.
5. Área útil que cubra las posiciones de medida, con margen; una placa pequeña centrada deja sin comprobar las zonas exteriores.

Consultar la [comparación previa de tolerancias de Calib.io](../deep_dive_2026-11-04/calibration_references.md). No se han actualizado precios ni solicitado ofertas en este estudio. Una placa de aluminio de bajo coste no es automáticamente suficiente para ±0,1 mm de longitud total.

## Ruta económica antes de comprometer una compra

Una impresión bien adherida a una base rígida permite comprobar adquisición, detección y calibración inicial. Para reducir sus errores geométricos existe `calibrateCameraRO`: el método de [Strobl y Hirzinger](https://elib.dlr.de/71888/1/strobl_2011iccv.pdf) optimiza también los puntos del patrón. Requiere que la geometría del patrón permanezca estable entre vistas; no corrige un papel que se dobla de manera diferente en cada foto.

La escala absoluta permanece indeterminada hasta introducir una longitud conocida. El [tutorial OpenCV](https://docs.opencv.org/4.13.0/d4/d94/tutorial_camera_calibration.html) usa una distancia medida entre esquinas extremas. Para Machina, el pie de rey disponible serviría para una primera comprobación, pero no daría por caracterizada una cuadrícula completa ni por demostrada la incertidumbre de 0,1 mm en 510 mm.

Ejemplo propio: introducir 100,00 mm cuando la separación real es 100,02 mm produce un factor 100/100,02; una longitud real de 510,508806 mm se subestima aproximadamente 0,1021 mm. El ajuste puede seguir reproduciendo las esquinas prácticamente igual de bien. Promediar más fotografías no corrige esa referencia equivocada.

Una referencia larga bien caracterizada ayuda a fijar escala; patrones pequeños de ancho 3–4 mm son complementarios para validar los bordes. Ninguno sustituye al otro. Si el laboratorio dispone de una CMM, proyector de perfiles o equipo óptico calibrado, caracterizar una placa/artefacto prestado puede ser más sensato que comprar el patrón más caro sin haber ensayado la pieza.

Para concretar una futura consulta, un **ejemplo de presupuesto propio, no requisito acordado**: si asignáramos a la referencia de escala una contribución de incertidumbre expandida de 0,03 mm sobre 510,508806 mm, eso equivaldría a unas 59 ppm. Sobre una separación de 200 mm, la incertidumbre expandida de esa separación debería ser aproximadamente ≤0,0118 mm, usando el mismo factor de cobertura y considerando solo escala uniforme. Quedarían por evaluar todas las demás contribuciones, incluidas planitud y altura. Esta cuenta muestra por qué una impresión sin caracterizar o un calibre de resolución aparentemente suficiente no son automáticamente adecuados; tampoco prescribe comprar una placa concreta.

## Mi elección para Machina

No evitaría el patrón para ahorrarme una calibración ocasional: es una tarea conocida y reutilizable. Sí evitaría convertir «hacer 20 fotos de un ajedrez» en un requisito ciego. El mínimo útil es un **mapa validado del plano de trabajo**; una calibración completa de intrínsecos es una herramienta adicional para describir la óptica y comprobar alturas conocidas. Elegir entre ambos se resuelve con el [protocolo de comparación](recommended_protocol.md), no con el RMS más bajo.
