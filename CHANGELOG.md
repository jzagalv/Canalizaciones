## 0.9.7-alpha - 2026-01-28
- Fixed: QMessageBox en CanvasScene usa parent QWidget válido al validar conexión de tramo.

## 0.9.6-alpha - 2026-01-28
- Fixed: Se impide crear tramos que comiencen y terminen en el mismo nodo.

## 0.9.5-alpha - 2026-01-28
- Fixed: Ventana Armario/Tablero ahora lista y dibuja todas las canalizaciones conectadas al nodo (expande T1-A, T1-B, etc.), incluyendo múltiples tramos entrantes.

## 0.9.4-alpha - 2026-01-28
- Fixed: Ventana Armario/Tablero ahora considera todas las canalizaciones de todos los tramos conectados al nodo.

## 0.9.3-alpha - 2026-01-28
- Added: Cotado de dimensiones (mm) en vistas frontal, lateral e inferior de Armario/Tablero.

## 0.9.2-alpha - 2026-01-28
- Changed: Ajuste de layout y escalado real de vistas en ventana de armario/tablero.

## 0.9.1-alpha - 2026-01-28
- Fixed: Unificación del tipo de equipos a {Tablero, Armario} en todas las UIs y librerías.
- Changed: "Equipo" queda deprecado y se migra a "Tablero" por compatibilidad.
- Added: Ventana Armario/Tablero accesible desde menú contextual del nodo para visualizar tramos conectados y cables, con vista inferior dibujando cables según asignación existente.

## 0.9.0-alpha - 2026-01-28
- Added: Editor masivo de equipos/armarios desde menú contextual en “Equipos”.
- Added: Campos cable_access y dimensions_mm en equipment_library items.

## 0.8.0-alpha - 2026-01-28
- Added: Presets de reglas de llenado (CRUD) + preset activo por proyecto.
- Changed: Motor usa reglas desde preset (no desde materiales).
- Fixed: Editores de materiales ya no exigen max_fill_percent/max_layers.

## 0.7.9-alpha - 2026-01-27
- Changed: Mejorado resaltado de troncales (mas visible, mas grueso ~ radio GAP, colores por troncal con palette dinamica).

## 0.7.8-alpha - 2026-01-27
- Fixed: Troncales: acci?n ahora soporta selecci?n m?ltiple y selecci?n de nodos (GAP/c?mara) sin error.
- Improved: UX para agrupar tramos manualmente incluso con cortes intermedios.

## 0.7.7-alpha - 2026-01-27
- Fixed: ejecuci?n/entrypoint estable con `python -m app`, VS Code launch config, compatibilidad con rutas antiguas.

## 0.7.6-alpha - 2026-01-27
- Fixed: BFS troncales no invalida edges por cortes; cortes por GAP/C?mara/Equipo aplicados correctamente; persistencia y refresh visual.

## 0.7.5-alpha - 2026-01-27
- Fixed: creaci?n de troncales, cortes por GAP/C?mara y refresh visual de overlays.

## 0.7.4-alpha - 2026-01-27
- Added: cortes de troncal por GAP/C?mara; men? contextual en canvas para troncales y edici?n tags; resaltado visual de troncales; renombrar/eliminar equipos en librer?a con bloqueo si est?n usados.

## 0.7.3-alpha - 2026-01-27
- Added: Troncales por selecci?n conectada (BFS/DFS), asignar/agregar/quitar tramos.

## 0.7.2-alpha - 2026-01-27
- Fix: Persistencia de equipos creados por usuario en equipment_library y recarga en Biblioteca.

## 0.7.1-alpha - 2026-01-27
- Added: per-conduit cable assignment and drawing in segment section view
- Added: circuit table shows assigned conduit (T1-A/B/...)
- Added: per-conduit used/available percentages and service preference

## 0.7.0-alpha - 2026-01-26
- Added: material uid/code and per-project snapshots for reproducibility
- Changed: proyectos guardan duct_uid + duct_snapshot (legacy projects migrate automatically)
- Fixed: warnings por ductos duplicados (Schedule 40/80) ya no colisionan

## 0.6.6 - 2026-01-25

- Fixed: detalle de tramo mantiene lista de circuitos tras recalcular

- Changed: Recalcular opera en modo manual-only (sin recomendaciones)

- Changed: cache de c?lculo no se invalida por preview/UI



## 0.6.5 - 2026-01-25

- Added: color coding for utilization (green/amber/red) across canvas/dialog/panel

- Fixed: enforce max 2 decimals for calculated values shown in UI



## 0.6.4 - 2026-01-24

- FIX: porcentaje de ocupacion consistente entre canvas y dialogo (mismo origen de datos)

- UI: labels de tramos estandarizados con fondo blanco y actualizacion en tiempo real



## 0.6.3 - 2026-01-24

- FIX: persistencia de edicion de tramo desde dialogo (props/kind/runs)

- UI: eliminado panel lateral duplicado de propiedades de tramo (se usa dialogo)



## 0.6.2 - 2026-01-24

- Fixed: Circuit cable selection now uses combobox populated from active materials library

- Added: Circuits table shows calculated route ("Recorrido") per circuit



## 0.6.1 - 2026-01-24

- Added: Cable combobox selector in Circuits

- Added: Duct selection by standard (norma) in tramo dialog



## 0.6.0 - 2026-01-23

- Added: Administrador de materiales_bd.lib (ventana flotante).

- Added: Editor CRUD por categoría (conductors/ducts/epc/bpc) con diálogos específicos.

- Changed: Menú "Librerías" con acciones para materiales_bd.lib.



## 0.5.0 - 2026-01-23

- Added: Ventana "Gestión de Librerías y Plantillas".

- Added: Editor CRUD de materiales por categoría con diálogos específicos.

- Changed: Menú "Herramientas" con acceso a la nueva ventana.



## 0.4.0 - 2026-01-23

- Added: Biblioteca con Drag&Drop para Equipos/GAP/Cámaras.

- Changed: Eliminados botones de inserción manual en Canvas.

- Fixed: compatibilidad de Drag&Drop con MIME antiguo.



## 0.3.0 - 2026-01-20

- Canvas: soporte Drag&Drop desde Biblioteca de Equipos (.lib kind equipment_library)

- Canvas: nodo de conexión (junction)

- Tramos: modo auto/manual + tamaño (catálogo) + cantidad (corrida simple)

- Nueva pestaña: Biblioteca Equipos

- Nueva pestaña: Equipos Primarios

- Project schema: primary_equipment



# Changelog



## 0.2.0 - 2026-01-19

- Canvas (QGraphicsScene/QGraphicsView): equipos, cámaras y tramos conectables.

- Edición rápida de tipo de tramo (duct/epc/bpc) y eliminación de elementos.

- Capa de cálculo inicial (routing + propuesta por tramo):

  - Ruteo por camino más corto en el canvas (por longitud si existe, o distancia geométrica).

  - Propuesta por tramo según catálogo (ducto o EPC) usando fill% por servicio.

  - Separación de servicios según reglas (best-effort).

- Resultados por tramo con estado (ok/warn/error) y badge en el canvas.



## 0.1.0 - 2026-01-19

- Estructura base del rediseño (arquitectura mantenible).

- Soporte inicial para Librerías .lib (material_library y template_library) extraídas desde BD.xlsx.

- Proyecto .proj.json con selección de librerías y perfil (convencional/digital).

- UI mínima con gestor de librerías (cargar/activar/prioridad) y selector de perfil.



## [0.3.1]

- Fix IndentationError in Canvas recalc method



## [0.3.2]

- Fix boot imports: ensure project root is on sys.path so `from ui...` works when running `python app/main.py`



## [0.3.3]

- Fix IndentationError in CanvasScene method definitions



## [0.3.4]

- Fix indentation and rewrite CanvasScene implementation (nodes/edges/connect mode/DnD)

- Fix EdgeItem methods indentation

- Fix CanvasTab _on_add_junction indentation



## [0.3.5] - 2026-01-21

- Canvas: soporte de plano de fondo (imagen) para posicionar equipos/canalizaciones de forma realista.

  - Cargar plano, ajustar a vista, bloquear/desbloquear, y control de opacidad.

  - Persistencia en Project.canvas.background (path/opacity/locked).

  - Exportación del canvas a PNG y PDF para adjuntar a informes.

- Fix: CanvasTab completado (métodos faltantes y conexiones) y toolbar consolidada.

- Fix: CanvasView (DnD) y CanvasItems (imports/compatibilidad NodeData) para evitar crashes.





















