# Product Backlog - Hermes

## Vision del producto

Hermes es una herramienta para apoyar la conciliacion de materiales entre requerimientos de ingenieria e inventario disponible. El producto busca reducir revisiones manuales, errores de interpretacion y retrabajos en procesos de control de materiales.

## Familias de materiales consideradas

- Esparragos
- Empaques
- Tuberia
- Bridas

## Enfoque del MVP

El MVP debe iniciar con una base funcional estable. En Sprint 1 se construye la carga y configuracion de datos. En Sprint 2 se agrega la interpretacion y conciliacion inicial. En Sprint 3 se integran reportes, validacion y demo.

## Historias de usuario

| ID | Epica | Historia de usuario | Prioridad | Story points | Sprint sugerido |
|---|---|---|---|---:|---|
| HU-01 | Carga y configuracion de datos | Como usuario, quiero cargar un archivo de inventario para que Hermes pueda leer los materiales disponibles. | Alta | 3 | Sprint 1 |
| HU-02 | Carga y configuracion de datos | Como usuario, quiero cargar un archivo de requerimientos para que Hermes pueda identificar que materiales se necesitan. | Alta | 3 | Sprint 1 |
| HU-03 | Carga y configuracion de datos | Como usuario, quiero seleccionar las columnas relevantes de cada archivo para adaptar Hermes a diferentes formatos. | Alta | 5 | Sprint 1 |
| HU-04 | Interfaz de usuario | Como usuario, quiero una interfaz sencilla para operar Hermes sin modificar codigo. | Alta | 5 | Sprint 1 |
| HU-05 | Normalizacion de materiales | Como usuario, quiero que Hermes identifique diametro y longitud en esparragos para evitar revision manual. | Alta | 5 | Sprint 2 |
| HU-06 | Normalizacion de materiales | Como usuario, quiero que Hermes normalice medidas a valores estandar para comparar materiales correctamente. | Alta | 5 | Sprint 2 |
| HU-07 | Motor de conciliacion | Como usuario, quiero que Hermes compare materiales requeridos contra inventario disponible para encontrar coincidencias. | Alta | 5 | Sprint 2 |
| HU-08 | Motor de conciliacion | Como usuario, quiero que Hermes descuente inventario conforme asigna materiales para evitar duplicar existencias. | Alta | 8 | Sprint 2 |
| HU-09 | Reportes de cobertura | Como usuario, quiero ver cuanto se cubre de cada requerimiento para conocer el porcentaje de solvencia. | Media | 3 | Sprint 3 |
| HU-10 | Reportes de cobertura | Como usuario, quiero un resumen por UDC para saber que frentes tienen mayor o menor cobertura. | Media | 5 | Sprint 3 |
| HU-11 | Reportes de cobertura | Como usuario, quiero exportar los resultados a Excel para compartirlos con el equipo. | Media | 3 | Sprint 3 |
| HU-12 | Validacion y pruebas | Como equipo, queremos probar Hermes con casos reales o simulados para validar que los resultados sean correctos. | Alta | 5 | Sprint 3 |
| HU-13 | Presentacion y cierre | Como equipo, queremos preparar una demo y presentacion ejecutiva para explicar el valor de Hermes. | Media | 5 | Sprint 3 |

## Notas de alcance

El Sprint 1 no debe incluir reglas de matching, extraccion dimensional ni asignacion de inventario. El objetivo es reducir riesgo construyendo primero la base de entrada de datos e interfaz.
