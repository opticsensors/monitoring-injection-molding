# Espacio de la futura aplicación

Directorio de código reservado para el paquete de inspección. No contiene todavía una implementación ni un punto de entrada.

La primera implementación podrá separar adaptadores de cámara/báscula, coordinador, procesamiento, persistencia e integración según [architecture.md](../../architecture.md). Fijar la estructura interna cuando se elijan los equipos y el primer flujo ejecutable.

No importar ventanas o módulos de adquisición DAQ para reutilizar accidentalmente estado de la aplicación principal. La integración deberá utilizar contratos explícitos y bibliotecas compartidas solo cuando exista una necesidad concreta.
