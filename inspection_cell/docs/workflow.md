# Flujo de inspección propuesto

Este flujo describe el comportamiento deseado. Los umbrales, temporizaciones e interfaces todavía no están implementados.

1. **Preparación:** cargar receta, identificación de máquina/sesión y calibración. Comprobar cámara, báscula y almacenamiento. Verificar el estado de tara con el soporte vacío.
2. **Disponibilidad:** esperar a que la báscula indique plataforma vacía dentro de una banda definida.
3. **Colocación:** el operario introduce la espiral. Un aumento de peso por encima del umbral detecta presencia; por sí solo no identifica qué pieza se ha colocado.
4. **Estabilización:** esperar lectura estable, retirada de la mano y ausencia de movimiento durante una ventana configurable. Confirmar pieza única y encuadre mediante la imagen cuando sea viable.
5. **Captura:** generar una identidad de inspección, registrar lectura estable y tiempo, disparar la cámara y asociar el archivo original a esa misma inspección. Registrar por separado los instantes de lectura y fotografía.
6. **Cálculo:** comprobar exposición, enfoque y oclusiones; aplicar calibración; separar la espiral de colada/soporte y calcular las magnitudes definidas por la receta.
7. **Asociación:** resolver el identificador de pieza y la identidad de captura del ciclo. Si no es inequívoco, guardar la inspección como pendiente de asignación.
8. **Persistencia y envío:** conservar localmente imagen, peso, resultados y estado antes de enviarlos. Registrar confirmación de recepción y tratar reintentos sin duplicar inspecciones.
9. **Retirada:** mantener la inspección terminada mientras la pieza permanezca presente. Rearmar tras detectar retirada estable.

## Estados iniciales

`no_listo → vacío → presencia → estabilizando → capturando → procesando → terminado → esperando_retirada`

Estados adicionales previstos: `error_equipo`, `medida_no_válida`, `pendiente_asignación` y `pendiente_envío`. La implementación decidirá cómo combinar estados de adquisición, validez y sincronización sin perder información.

## Asociación con la inyección

El repositorio utiliza `(machine_id, session_id, cycle_id)` para la identidad de captura. El número visible dentro de una sesión no basta por sí solo.

La estrategia de identificación queda abierta: pieza/bandeja etiquetada, código, selección explícita o una cola estricta validada. Asignar siempre al último ciclo sería incorrecto si hay enfriamiento, piezas retiradas, retrasos o reinspecciones. La detección por peso únicamente indica presencia.

Si hay varias piezas por ciclo, se necesitará además `part_id` o `cavity_id`. Una nueva inspección de la misma pieza debe conservar su trazabilidad en lugar de crear otra pieza ficticia.

## Casos a resolver

- Pieza retirada o movida durante la estabilización o exposición.
- Dos piezas simultáneas, resto de colada, manos y objetos ajenos.
- Longitud parcial por llenado incompleto, extremos ambiguos o colada superpuesta.
- Falta de estabilidad, sobrecarga, lectura inválida o pérdida de conexión.
- Orden de piezas diferente al de inyección y cambios de sesión.
- Reinspección, edición manual concurrente y reenvío de una inspección ya recibida.

Los ensayos de estos casos están en [validación de integración](../validation/protocols/integration.md).
