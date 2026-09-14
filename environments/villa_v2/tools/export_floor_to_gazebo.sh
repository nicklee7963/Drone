#!/usr/bin/env bash

set -e

ROOT="$HOME/Phenix_Project/Drone/environments/villa_v2"

FLOOR="$1"

if [ -z "$FLOOR" ]; then
    echo "Usage:"
    echo "  $0 1F"
    echo "  $0 2F"
    echo "  $0 3F"
    echo "  $0 B1"
    exit 1
fi

SRC="$ROOT/01_shell/$FLOOR/${FLOOR}_shell.blend"
MODEL_NAME="villa_${FLOOR}"

DEST="$ROOT/gazebo/$MODEL_NAME"
MESH_DIR="$DEST/meshes"
OBJ="$MESH_DIR/${MODEL_NAME}.obj"

echo "======================================"
echo " Exporting Villa Floor: $FLOOR"
echo "======================================"
echo
echo "Source:"
echo "  $SRC"
echo
echo "Destination:"
echo "  $DEST"
echo

if [ ! -f "$SRC" ]; then
    echo "ERROR: Blender file not found:"
    echo "$SRC"
    exit 1
fi

mkdir -p "$MESH_DIR"

echo "[1/4] Exporting OBJ..."

blender -b "$SRC" --python-expr "
import bpy

out='$OBJ'

bpy.ops.object.select_all(action='SELECT')

bpy.ops.wm.obj_export(
    filepath=out,
    export_selected_objects=True,
    apply_modifiers=True,
    export_materials=True,
    forward_axis='Y',
    up_axis='Z'
)

print('Export complete:', out)
"

echo
echo "[2/4] Creating model.config..."

cat > "$DEST/model.config" <<CONFIG
<?xml version="1.0"?>
<model>
  <name>Villa $FLOOR</name>
  <version>1.0</version>

  <sdf version="1.9">model.sdf</sdf>

  <author>
    <name>nicklee</name>
  </author>

  <description>
    Villa V2 $FLOOR shell.
  </description>
</model>
CONFIG

echo
echo "[3/4] Creating model.sdf..."

cat > "$DEST/model.sdf" <<SDF
<?xml version="1.0" ?>
<sdf version="1.9">

  <model name="$MODEL_NAME">

    <static>true</static>

    <link name="${MODEL_NAME}_link">

      <visual name="${MODEL_NAME}_visual">
        <geometry>
          <mesh>
            <uri>meshes/${MODEL_NAME}.obj</uri>
          </mesh>
        </geometry>
      </visual>

      <collision name="${MODEL_NAME}_collision">
        <geometry>
          <mesh>
            <uri>meshes/${MODEL_NAME}.obj</uri>
          </mesh>
        </geometry>
      </collision>

    </link>

  </model>

</sdf>
SDF

echo
echo "[4/4] Validating SDF..."

gz sdf -k "$DEST/model.sdf"

echo
echo "======================================"
echo " SUCCESS"
echo "======================================"
echo
echo "Gazebo model:"
echo "$DEST"
echo
echo "Mesh:"
echo "$OBJ"
