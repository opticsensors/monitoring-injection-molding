# Cámara, óptica y campo de visión

**Recomendación actual, 2026-11-04:** estudiar primero **Computar V3522-MPZ de 35 mm**, con [ficha archivada](../components/datasheets/V3522-MPZ.pdf). El usuario descarta 2 m y considera 1 m alto. La [primera revisión](2026-11-04_hardware_review.md) compara focales de 25/35/50/75 mm y la [ampliación de lentes](deep_dive_2026-11-04/lens_alternatives.md) añade VA/Basler/Kowa, MTF y condiciones de préstamo; la tabla de 75 mm de abajo describe la propuesta original, no una selección final.

## Conjunto candidato

Datos de las fichas suministradas y la oferta; no son resultados de ensayo.

La extracción ampliada de las fichas está en [cámara BFS-U3-200S6](../components/camera_bfs_u3_200s6.md) y [lente V7531-MPZ](../components/lens_v7531_mpz.md). Incluye rangos de exposición, modos de adquisición, conexiones, condiciones de FPS y cotas de montaje. Los PDF de `C:\edu\projects\Machina` se verificaron el 2026-11-04 contra las copias archivadas.

| Parámetro | Cámara FLIR BFS-U3-200S6M-C |
| --- | --- |
| Imagen | 5472 × 3648 píxeles, monocroma, 20 MP |
| Sensor | Sony IMX183 CMOS, formato comercial 1 pulgada |
| Píxel | 2,4 µm |
| Lectura | Rolling shutter con global reset |
| Frecuencia indicada | 18 FPS bajo condiciones de ficha |
| Montura / interfaz | C / USB 3.1 Gen 1 |
| Dimensiones / masa | 29 × 29 × 30 mm / 36 g |
| Alimentación indicada | 5 V por USB 3 o 8–24 V por GPIO; consumo máximo 3 W |

| Parámetro | Óptica Computar V7531-MPZ |
| --- | --- |
| Focal | 75 mm |
| Iris | f/3,1 a f/16 |
| Enfoque | 0,25 m a infinito, manual |
| Formato indicado | 1 Type / 20 MP, imagen máxima 12,8 × 9,6 mm, círculo Ø16 mm |
| Montura | C |
| Masa / dimensiones | 176,1 g / Ø42 × 79,8 mm nominales |
| Ángulo indicado para 1 Type | 12,2° diagonal, 9,8° horizontal, 7,3° vertical |

Fuentes: [cámara](../components/datasheets/BFS-U3-200S6-Datasheet.pdf), [lente](../components/datasheets/V7531-MPZ.pdf) y [oferta](../components/quotes/IN26-1893.pdf). La etiqueta comercial «1 pulgada» no es una dimensión de sensor de 25,4 mm. El tamaño activo calculado con resolución y píxel es **13,1328 × 8,7552 mm**, diagonal aproximada de 15,784 mm. Comprobar cobertura y rendimiento en esquinas del conjunto real.

## Estimación inicial de encuadre

Cálculo propio con imagen completa, píxeles cuadrados, cámara perpendicular y sin recorte/distorsión. Para encuadrar un cuadrado manda el lado corto de 3648 píxeles.

| Zona cuadrada mínima | FOV completo correspondiente | Muestreo en objeto | Píxeles en 0,10 mm | Distancia óptica aproximada u |
| --- | --- | --- | --- | --- |
| 150 × 150 mm | 225 × 150 mm | 0,04112 mm/píxel | 2,43 | 1.360 mm |
| 200 × 200 mm | 300 × 200 mm | 0,05482 mm/píxel | 1,82 | 1.788 mm |

Fórmulas: `s = FOV_y / 3648`, `m = 8,7552 / FOV_y`, `u ≈ f × (1 + 1/m)` para una lente delgada de focal `f = 75 mm`. La distancia u parte del plano principal del modelo óptico; no es una cota de montaje desde el frontal ni desde el sensor. El diseño real requiere verificarla con el fabricante o medir el campo a distintas distancias. Los márgenes adicionales incrementan FOV y distancia.

No dividir 200 mm entre 5472 píxeles para prometer cobertura de un cuadrado de 200 mm: con ese ajuste solo se abarcarían aproximadamente 133 mm en el lado corto.

El muestreo no demuestra exactitud. La óptica, apertura, enfoque, contraste y calibración también determinan el resultado; véase [Edmund Optics, Sensors and Lenses](https://www.edmundoptics.com/knowledge-center/application-notes/imaging/sensors-and-lenses/), consultado el 2026-11-04.

## Ensayos pendientes

Con el mismo FOV y sensor, cambiar focal cambia la distancia de trabajo, **no los mm/píxel**. Para 150/200 mm de lado, la estimación de distancia óptica con 35 mm es 0,63/0,83 m; con 50 mm, 0,91/1,19 m. Confirmar distancia frontal real y margen. Se guardó también la [ficha de 50 mm](../components/datasheets/V5024-MPZ.pdf); los [cálculos](optics_tradeoffs.py) reproducen la comparación.

- Medir FOV y uniformidad de escala con patrón en toda la zona útil y con la placa transparente final.
- Evaluar foco/apertura para la dispersión de alturas real; una imagen enfocada puede seguir teniendo error de perspectiva.
- Comprobar que la colada vertical cabe y no oculta zonas del hilo.
- Fijar exposición y comprobar movimiento/parpadeo con el modo de lectura de esta cámara.
- Confirmar SDK, disparo, lectura de tiempos y compatibilidad del PC. El conector C y USB no bastan para validar el conjunto metrológico.
- Evaluar la [sensibilidad a altura](metrology.md) antes de fijar la altura definitiva de la estructura.

La cámara ofertada es monocroma. El estudio inicial se centra en silueta, no en clasificación por color.

La evaluación vigente incluye [apertura, bordes y luz](deep_dive_2026-11-04/optics_and_lighting.md), [contracción frente a altura](deep_dive_2026-11-04/detectable_variation.md) y [referencias de calibración](deep_dive_2026-11-04/calibration_references.md).
