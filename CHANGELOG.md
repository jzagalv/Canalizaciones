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


