# Definition of Done - Hermes

Una historia de usuario de Hermes se considera terminada cuando cumple con los siguientes criterios.

## Criterios generales

- La funcionalidad fue implementada en el repositorio.
- La funcionalidad puede ejecutarse sin modificar el codigo fuente.
- El comportamiento cumple los criterios de aceptacion definidos.
- El equipo puede demostrar la funcionalidad en Sprint Review.
- Los errores principales fueron manejados con mensajes claros para el usuario.
- La funcionalidad esta documentada de forma minima.

## Criterios especificos del Sprint 1

- El sistema permite cargar archivos `.xlsx`.
- El sistema rechaza archivos vacios mediante un mensaje de error.
- El sistema muestra una vista previa de los datos cargados.
- El sistema muestra las columnas disponibles en listas desplegables.
- El sistema valida que las columnas obligatorias fueron seleccionadas.
- El sistema no ejecuta conciliacion ni asignacion automatica en Sprint 1.

## Criterios de calidad tecnica

- El codigo esta separado en un punto de entrada `main.py` y una aplicacion principal en `src/hermes_app.py`.
- Las dependencias estan declaradas en `requirements.txt`.
- Los archivos temporales, ambientes virtuales y salidas locales estan excluidos mediante `.gitignore`.
- El proyecto puede instalarse y ejecutarse siguiendo las instrucciones del README.

## Criterios de producto

- La interfaz puede ser entendida por un usuario no tecnico.
- El flujo de carga y seleccion de columnas es claro.
- El incremento habilita el desarrollo del Sprint 2.
