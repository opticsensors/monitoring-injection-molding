# Electricidad y comunicaciones físicas

Estado: arquitectura preliminar, sin esquema eléctrico ni cableado aprobado.

| Equipo | Conexión prevista | Pendiente |
| --- | --- | --- |
| Cámara candidata | USB 3.1 Gen 1 al PC; alimentación según ficha | Puerto/controlador, cableado y adquisición real |
| Báscula | USB, RS-232 o Ethernet según selección | Modelo, protocolo, adaptador y alimentación |
| Backlight | Fuente/controlador según panel | Tensión, corriente, control, disparo y disipación |
| PC | Almacenamiento y conexión a servicios del proyecto | Ubicación, interfaces disponibles y funcionamiento sin red |

El disparo desde PC y las rutas serie están contrastados documentalmente en [viabilidad de adquisición](acquisition_feasibility.md). Una sincronización por I/O sería una decisión posterior; el manual GPIO se ha localizado, pero no se ha diseñado un cableado definitivo.

La [extracción de la ficha de cámara](../components/camera_bfs_u3_200s6.md) recoge alimentación por USB/GPIO, consumo máximo, I/O optoaislada/no aislada y salida auxiliar. La ficha no aporta las asignaciones de pines ni todos los límites eléctricos de esas líneas.

El cableado de elementos apoyados en la báscula debe permitir el movimiento necesario sin transmitir una fuerza apreciable. Registrar también alimentación, conectores, longitudes y alivio de tracción en [wiring/](wiring/README.md).
