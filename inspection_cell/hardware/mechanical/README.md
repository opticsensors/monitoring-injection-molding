# Diseño mecánico

Concepto inicial: una base sostiene una columna vertical y un brazo horizontal que coloca cámara y lente en posición cenital sobre la zona de inspección. La base de 300 × 300 mm del PPT sigue por dimensionar. El usuario descarta 2 m y considera 1 m alto pero estudiable; se prioriza 35 mm y distancias ópticas aproximadas de 0,63–0,83 m. Véanse el [estudio de perfiles y envolventes](../research/deep_dive_2026-11-04/mechanical_frame.md) y el [estudio de apoyo y rutas de carga](../research/deep_dive_2026-11-04/fixture_and_materials.md).

## Áreas de trabajo

- [frame/](frame/README.md): columna, brazo, base, ajuste y fijaciones.
- [fixtures/](fixtures/README.md): apoyo transparente, posicionamiento y tratamiento de la colada.
- [geometry/](geometry/README.md): script y figuras de la espiral ideal con sensores del molde.
- [cad/](cad/README.md): fuentes CAD recibidas y futuros diseños de la celda.

## Condicionantes de conjunto

Separar la función de sostener la cámara de la de transmitir carga a la báscula. Documentar cada contacto físico y evitar apoyos que desvíen parte del peso. Determinar el volumen necesario para colocar/retirar la pieza con colada vertical y para limpiar la superficie óptica.

La altura debe partir del ensayo de FOV, foco y error; el voladizo y las uniones deben mantener posición y orientación durante la captura. La selección de perfil necesita cargas y geometría reales, no únicamente el precio por metro.
