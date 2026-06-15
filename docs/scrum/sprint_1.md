# Sprint 1 - Base funcional de Hermes

## Duracion

1 semana

## Sprint Goal

Construir la base funcional de Hermes para cargar archivos de inventario y requerimientos, seleccionar columnas relevantes y validar que el equipo cuenta con una configuracion minima para iniciar el procesamiento en el Sprint 2.

## Historias comprometidas

| ID | Historia de usuario | Criterios de aceptacion | Story points |
|---|---|---|---:|
| HU-01 | Como usuario, quiero cargar un archivo de inventario para que Hermes pueda leer los materiales disponibles. | El sistema permite seleccionar un archivo `.xlsx`, lo carga en memoria y muestra una vista previa. | 3 |
| HU-02 | Como usuario, quiero cargar un archivo de requerimientos para que Hermes pueda identificar que materiales se necesitan. | El sistema permite seleccionar un archivo `.xlsx`, lo carga en memoria y muestra una vista previa. | 3 |
| HU-03 | Como usuario, quiero seleccionar las columnas relevantes de cada archivo para adaptar Hermes a diferentes formatos. | El sistema muestra listas desplegables con columnas disponibles para descripcion, codigo, cantidad, UDC y fecha. | 5 |
| HU-04 | Como usuario, quiero una interfaz sencilla para operar Hermes sin modificar codigo. | La interfaz separa inventario y requerimientos, incluye botones de carga, combos de seleccion, vista previa y estado del proceso. | 5 |

## Incremento esperado

Al cierre del Sprint 1, Hermes debe permitir:

- Abrir la aplicacion de escritorio.
- Cargar archivo de inventario en Excel.
- Cargar archivo de requerimientos en Excel.
- Mostrar una vista previa de los datos cargados.
- Alternar la vista previa entre inventario y requerimientos.
- Seleccionar columnas relevantes de ambos archivos.
- Validar que la configuracion minima esta completa.
- Alternar entre tema claro y oscuro.

## Fuera de alcance del Sprint 1

- Extraccion de diametro y longitud.
- Normalizacion de medidas.
- Matching entre requerimientos e inventario.
- Asignacion de cantidades.
- Calculo de porcentaje de cobertura.
- Exportacion de resultados finales.

## Tareas tecnicas

| Historia | Tareas |
|---|---|
| HU-01 | Crear boton de carga de inventario, leer Excel con pandas, guardar DataFrame en memoria, mostrar preview. |
| HU-02 | Crear boton de carga de requerimientos, leer Excel con pandas, guardar DataFrame en memoria, mostrar preview. |
| HU-03 | Poblar combos con columnas de cada archivo, guardar seleccion de usuario, validar campos obligatorios. |
| HU-04 | Crear la interfaz con PySide6, agregar paneles separados, estado de proceso, selector de archivo visible y tabla de vista previa. |

## Decisiones tecnicas implementadas

- La interfaz se desarrollo con PySide6 y se separo de los modelos de dominio y
  los servicios de aplicacion.
- La lectura de archivos admite exclusivamente `.xlsx` y normaliza los
  encabezados eliminando espacios exteriores.
- La vista previa conserva como maximo 100 filas visibles, mientras el dataset
  completo permanece disponible en memoria.
- La validacion acumula todos los errores de configuracion para mostrarlos en un
  solo mensaje.
- El tema oscuro es una preferencia visual y no modifica los datos cargados.

## Sprint Review

Demostracion esperada:

1. Ejecutar `python main.py`.
2. Cargar archivo de inventario.
3. Cargar archivo de requerimientos.
4. Alternar entre ambas fuentes desde el selector de vista previa.
5. Seleccionar columnas relevantes.
6. Validar configuracion del Sprint 1.
7. Activar y desactivar el modo oscuro desde `Configuracion`.

Pregunta de validacion con stakeholders:

> Hermes ya puede recibir y preparar los datos necesarios para construir el motor de conciliacion en el Sprint 2?

## Sprint Retrospective

Preguntas sugeridas:

- Que funciono bien en la coordinacion del equipo?
- Que problemas tuvimos con estructura de archivos o columnas?
- Que riesgos vemos para interpretar descripciones de materiales en el Sprint 2?
- Que debemos mejorar para mantener el backlog claro?
