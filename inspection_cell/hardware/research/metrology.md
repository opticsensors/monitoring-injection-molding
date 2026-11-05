# Viabilidad metrológica y error por altura

Ampliación específica: [calibración dimensional píxeles→mm](calibration_2026-11-04/README.md), con literatura, configuración FLIR/Computar y protocolo independiente. No sustituye las definiciones de magnitud ni elimina el problema de altura descrito aquí.

Actualización 2026-11-04: el usuario aclara que **0,1 mm es orientativo y no obligatorio para longitud y diámetro**. Importa detectar variación real entre piezas por encima del ruido. Antes de seleccionar el conjunto se debe definir la magnitud y un método de referencia. La [revisión actual](2026-11-04_hardware_review.md) explica por qué binarizar no produce un error absoluto común para ambas medidas y compara altura a 800 mm.

## Tres magnitudes diferentes

1. **Longitud espacial:** recorrido real del eje del hilo, incluyendo su salida del plano.
2. **Longitud proyectada:** recorrido del eje en el plano de la imagen corregida/calibrada.
3. **Longitud bajo apoyo definido:** resultado con la pieza sujeta en una condición mecánica especificada.

Para un elemento de curva, `ds_3D = sqrt(dx² + dy² + dz²)`, mientras que `ds_XY = sqrt(dx² + dy²)`. Una vista cenital no recupera el término `dz` de una pieza arbitrariamente deformada. La proyección ortogonal ideal es menor o igual a la longitud espacial; la perspectiva añade además cambios locales de escala.

Un soporte podría mejorar repetibilidad y reducir variación de altura, pero puede alterar la forma o generar esfuerzos. Hay que validar tanto su efecto mecánico como el resultado óptico. La calibración de un plano no corrige por sí sola alturas desconocidas en toda la pieza.

## Perspectiva con óptica convencional

Con una lente convencional, una variación de distancia cambia la magnificación incluso si la pieza sigue enfocada. La telecentricidad reduce este efecto; esta es la razón técnica para estudiar la altura con cuidado cuando se descarta esa alternativa. Fuente: [Edmund Optics, The Advantages of Telecentricity](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/advantages-of-telecentricity/), consultada el 2026-11-04.

Ejemplo **propio e ilustrativo**, con modelo de cámara central: cámara a distancia Z de un plano calibrado y un segmento paralelo a ese plano elevado uniformemente h hacia la cámara.

```text
escala aparente / escala calibrada = Z / (Z − h)
error de longitud = L × h / (Z − h)
```

Ejemplo histórico con `Z = 1500 mm` y `h = 10 mm` (no es la altura recomendada; el usuario prefiere menos de 1 m):

| Longitud del segmento | Error de escala ilustrativo |
| --- | ---: |
| 4 mm | +0,0268 mm |
| 510,5088 mm | +3,4262 mm |

Esto no predice el error exacto de una espiral alabeada: la altura varía, la curva se inclina y aparecen otras contribuciones. Sí muestra por qué cumplir en diámetro local no garantiza cumplir en longitud total.

En ese mismo modelo, para limitar únicamente este error a 0,1 mm sobre 510,5088 mm, el desplazamiento uniforme sería aproximadamente `h ≤ 0,1 × 1500 / (510,5088 + 0,1) = 0,294 mm`. No es una tolerancia final del soporte: consumiría todo el margen de error sin reservar nada para las demás fuentes.

## Ancho aparente y diámetro

Una silueta permite medir el ancho transversal proyectado. Convertirlo en diámetro real exige justificar sección y orientación. Una sección ovalada no se caracteriza completamente con una sola vista. También deben definirse extremos, región próxima a la colada, rebabas y estadísticos del resultado.

El recorrido medido debe seguir la línea central física. Contar píxeles de un esqueleto sin controlar el sesgo por discretización, curvas y extremos puede introducir error acumulado. El modelo ideal del script sirve como referencia, no como longitud impuesta a las medidas reales.

## Presupuesto de error a construir

| Contribución | Cómo estudiarla |
| --- | --- |
| Escala y distorsión | Patrón de referencia distribuido por el FOV; comparar puntos no usados en ajuste |
| Altura y orientación | Patrones elevados de forma conocida y piezas con su deformación real |
| Soporte | Repetir libre/apoyada/sujeta y con distintas recolocaciones |
| Bordes e iluminación | Barrer exposición, intensidad y umbral; PP, soporte y sombras reales |
| Muestreo, enfoque y algoritmo | Referencias de radios/anchos conocidos, posiciones y orientaciones distintas |
| Temperatura y tiempo tras inyección | Registrar condición térmica y evolución temporal |
| Método de referencia | Documentar su calibración e incertidumbre |

La repetibilidad sola no demuestra exactitud: una medida estable puede estar sesgada. Tampoco debe interpretarse el 0,0 % de distorsión tabulado en la ficha de lente como garantía de error nulo del sistema.

## Telecéntrica descartada en esta fase

El usuario refiere una propuesta de STEMMER con FOV de 226 × 179 mm, masa de 46,7 kg y longitud de 650 mm. Se conserva como motivo de descarte por coste/peso/volumen. Falta modelo y ficha para confirmar esos datos. Ese campo tampoco contiene por completo un cuadrado de 200 × 200 mm. No se extrapolan sus dimensiones a toda óptica telecéntrica.

La siguiente evidencia necesaria es el [ensayo dimensional](../../validation/protocols/dimensional_accuracy.md), no una afirmación de cumplimiento basada únicamente en megapíxeles.
