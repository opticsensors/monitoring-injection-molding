# Geometría suministrada

Copias sin modificar de `spiral_sensors.py`, `spiral_sensors.svg` y `spiral_sensors.png`, procedentes de la carpeta de proyecto `quality control`.

La [referencia geométrica](../../../docs/geometry_reference.md) recoge arcos, longitud y posiciones calculadas. Estos ficheros describen geometría ideal y sensores del molde, no una calibración de la cámara ni el resultado de medir piezas reales.

## Reproducir el dibujo

El script necesita Python, NumPy y Matplotlib. Al ejecutarlo imprime coordenadas y guarda PNG/SVG en el directorio de trabajo, además de abrir una figura. Para conservar intactas las copias suministradas, ejecutarlo desde una carpeta de salida distinta:

```powershell
# Desde la raíz del repositorio; entorno con numpy y matplotlib instalados.
New-Item -ItemType Directory -Force data/inspection_cell_geometry_preview | Out-Null
Push-Location data/inspection_cell_geometry_preview
try {
    py -3.11 ../../inspection_cell/hardware/mechanical/geometry/spiral_sensors.py
} finally {
    Pop-Location
}
```

El PNG incluido ya es el render proporcionado junto con el SVG. No es necesario convertir el vector para leer el esquema en Markdown. Las futuras modificaciones del modelo deben conservar la procedencia y distinguirse de esta copia de referencia.
