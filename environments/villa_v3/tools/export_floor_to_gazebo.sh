#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
FLOOR="${1:-}"

case "$FLOOR" in
  B1|1F|2F|3F|Roof) ;;
  *)
    echo "Usage: $0 {B1|1F|2F|3F|Roof}" >&2
    exit 2
    ;;
esac

SRC="$ROOT/01_shell/$FLOOR/${FLOOR}_shell.blend"
MODEL_NAME="villa_${FLOOR}"
DEST="$ROOT/gazebo/$MODEL_NAME"
MESH_DIR="$DEST/meshes"
OBJ="$MESH_DIR/${MODEL_NAME}.obj"

if [[ ! -f "$SRC" ]]; then
  echo "ERROR: Blender file not found: $SRC" >&2
  exit 1
fi

mkdir -p "$MESH_DIR"
echo "Exporting $FLOOR shell geometry from $SRC"

blender -b "$SRC" --python-expr "
import bpy
out = r'''$OBJ'''
bpy.ops.object.select_all(action='DESELECT')
selected = []
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH' and obj.get('shell_geometry'):
        obj.hide_render = False
        obj.hide_set(False)
        obj.select_set(True)
        selected.append(obj)
if not selected:
    raise RuntimeError('no shell_geometry meshes found for export')
bpy.context.view_layer.objects.active = selected[0]
bpy.ops.wm.obj_export(
    filepath=out,
    export_selected_objects=True,
    apply_modifiers=True,
    export_materials=True,
    forward_axis='Y',
    up_axis='Z'
)
print('Exported architectural meshes:', len(selected), out)
"

cat > "$DEST/model.config" <<CONFIG
<?xml version="1.0"?>
<model>
  <name>Villa V3 $FLOOR</name>
  <version>1.0</version>
  <sdf version="1.9">model.sdf</sdf>
  <author><name>nicklee</name></author>
  <description>Cleaned Villa V3 $FLOOR architectural shell.</description>
</model>
CONFIG

cat > "$DEST/model.sdf" <<SDF
<?xml version="1.0"?>
<sdf version="1.9">
  <model name="$MODEL_NAME">
    <static>true</static>
    <link name="${MODEL_NAME}_link">
      <visual name="${MODEL_NAME}_visual">
        <geometry><mesh><uri>meshes/${MODEL_NAME}.obj</uri></mesh></geometry>
      </visual>
      <collision name="${MODEL_NAME}_collision">
        <geometry><mesh><uri>meshes/${MODEL_NAME}.obj</uri></mesh></geometry>
      </collision>
    </link>
  </model>
</sdf>
SDF

gz sdf -k "$DEST/model.sdf"
echo "Exported and validated $MODEL_NAME -> $DEST"
