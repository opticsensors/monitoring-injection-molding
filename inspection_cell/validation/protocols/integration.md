# Protocolo propuesto: trazabilidad e integración

Estado: pendiente de implementar y ejecutar. Requisitos relacionados: M-05, M-07 y O-04 a O-08.

## Casos de referencia

| Caso | Resultado esperado propuesto |
| --- | --- |
| Una pieza conocida de un ciclo | Imagen, peso y medidas vinculados a la misma inspección y captura |
| Pieza de un ciclo anterior | Se conserva su identidad, aunque exista un ciclo más reciente |
| Identidad desconocida | Inspección guardada pendiente de asignación |
| Cambio de sesión/máquina visible | No se reconstruye la identidad de captura desde etiquetas ambiguas |
| Dos piezas/cavidades por ciclo | Distinción por identidad de pieza/cavidad si aplica |
| Reinspección | Se conserva la relación con la pieza y con la inspección anterior |
| Reintento del mismo mensaje | Sin duplicado ni sustitución de una revisión posterior |
| Edición manual concurrente | Regla de conflicto explícita, sin borrar campos no medidos |
| Pérdida de red | Evidencia local recuperable y estado de envío pendiente |
| Reinicio durante envío | Recuperación comprobada sin atribuir datos a otra pieza |
| Cámara o báscula fallan | Inspección incompleta/no válida visible, sin valores inventados |
| History y exportación | Diámetro, longitud, peso y procedencia se leen con las unidades acordadas |

## Evidencia

Usar identidades conocidas, verificar almacenamiento y lectura posterior, y contrastar el archivo de imagen mediante su identificador/huella. Registrar versiones de contratos y componentes utilizados. Ejecutar primero con simuladores y después con hardware real; informar ambos resultados por separado.
