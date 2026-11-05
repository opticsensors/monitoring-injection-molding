# Arquitectura e integración propuestas

Este documento describe diseño pendiente, no funcionalidades disponibles.

## Responsabilidades

| Área | Responsabilidad |
| --- | --- |
| Adaptador de báscula | Conexión, lectura, unidades, estabilidad, tara y errores |
| Adaptador de cámara | Configuración identificada, disparo, imagen original y tiempo |
| Coordinador de inspección | Estados de presencia, estabilidad, captura y retirada |
| Procesamiento de imagen | Calibración, segmentación, trayectoria y ancho del hilo |
| Validación de resultado | Detectar oclusión, desenfoque, recorte y casos no medibles |
| Persistencia | Identidad de inspección, imagen, resultados, estado y reintentos |
| Asociación de piezas | Relacionar inspección con pieza/cavidad y ciclo de captura |
| Integración | Publicar resultados y consultar su recepción sin duplicados |
| Interfaz de operación | Estado, medida, incidencias y resolución de asignación pendiente |

Los adaptadores deberán poder sustituirse por simuladores para desarrollar sin hardware. La elección de bibliotecas de visión y SDK queda pendiente de equipos y ensayos.

## Relación con el sistema existente

La aplicación actual registra capturas con identidad `(machine_id, session_id, cycle_id)`. [cycle_metadata.py](../../cycle_metadata.py) define mensajes v1 de medidas con `weight_g`, `length_mm`, revisión e identificador de actualización; `length_mm` se presenta como longitud de espiral.

Ese contrato espera un par completo peso/longitud; un valor nulo puede borrar una medida. No debe conectarse una nueva fuente automática enviando nulos en campos que no ha medido ni suponiendo que las revisiones locales de dos productores se coordinan solas.

La ampliación deberá definir conflicto con edición manual, revisiones, identificadores idempotentes y actualizaciones parciales o completas. La identidad asociada debe ser la de la captura, sin reconstruirla a partir de valores de máquina corregidos solo para visualización.

El contrato actual no representa por completo diámetro, imágenes, calibración ni historial de reinspecciones. Habrá que diseñar esa extensión y adaptar validación, Node-RED, almacenamiento, History y exportaciones. Un registro de inspecciones separado, vinculado a ciclos, es una propuesta a estudiar; todavía no existe esa tabla o mensaje.

## Datos mínimos de una inspección

Lista conceptual, no esquema implementado:

- Identificador único de inspección, estación y tiempos de lectura/captura.
- Identidad de pieza/cavidad cuando sea necesaria y vínculo a ciclo, o estado pendiente de asignación.
- Peso y unidad; estado de estabilidad y condición de tara.
- Longitud, definición de la magnitud y unidad.
- Perfil/estadísticos de ancho o diámetro con posiciones y definición.
- Resultado de validez y motivo de incidencia, separado del estado de envío.
- Ruta/identificador de imagen original y comprobación de integridad.
- Receta, configuración, calibración y versión de software/método.
- Relación con una inspección anterior si es una repetición o revisión.

No enviar imágenes grandes dentro del mensaje actual de muestras DAQ. Definir almacenamiento de imágenes y comunicar su referencia mediante el contrato acordado. Conservar original y resultado procesado por separado cuando este último sea necesario.

## Comportamiento ante incidencias

Persistir inspecciones antes de considerar terminada su adquisición. Mantener reintentos con la misma identidad y confirmar recepción. Si se pierde la asociación, conservar la medida pendiente; si se pierde un equipo, impedir un resultado aparentemente completo. La garantía de recuperación dependerá de la implementación y de los ensayos, no solo de usar MQTT.

El flujo de operación está en [docs/workflow.md](../docs/workflow.md). Los casos de aceptación están en [validation/protocols/integration.md](../validation/protocols/integration.md).
