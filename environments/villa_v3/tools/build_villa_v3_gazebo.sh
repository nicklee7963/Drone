#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

for floor in B1 1F 2F 3F Roof; do
  "$SCRIPT_DIR/export_floor_to_gazebo.sh" "$floor"
done

mkdir -p "$ROOT/gazebo/worlds"
cat > "$ROOT/gazebo/worlds/villa_v3.sdf" <<'SDF'
<?xml version="1.0"?>
<sdf version="1.10">
  <world name="villa_v3_world">
    <physics name="default_physics" type="gz-physics">
      <max_step_size>0.001</max_step_size>
      <real_time_factor>1.0</real_time_factor>
    </physics>
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics">
      <engine><filename>gz-physics-bullet-featherstone-plugin</filename></engine>
    </plugin>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <scene>
      <ambient>0.45 0.45 0.45 1</ambient>
      <background>0.7 0.7 0.7 1</background>
      <shadows>true</shadows>
    </scene>
    <light type="directional" name="sun">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 25 0 0 0</pose>
      <diffuse>0.85 0.85 0.85 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision"><geometry><plane><normal>0 0 1</normal><size>200 200</size></plane></geometry></collision>
        <visual name="visual"><geometry><plane><normal>0 0 1</normal><size>200 200</size></plane></geometry></visual>
      </link>
    </model>
    <include><uri>model://villa_B1</uri><name>villa_B1</name><pose>0 0 -3.2 0 0 0</pose></include>
    <include><uri>model://villa_1F</uri><name>villa_1F</name><pose>0 0 0 0 0 0</pose></include>
    <include><uri>model://villa_2F</uri><name>villa_2F</name><pose>0 0 3.2 0 0 0</pose></include>
    <include><uri>model://villa_3F</uri><name>villa_3F</name><pose>0 0 6.4 0 0 0</pose></include>
    <include><uri>model://villa_Roof</uri><name>villa_Roof</name><pose>0 0 9.6 0 0 0</pose></include>
  </world>
</sdf>
SDF

export SDF_PATH="$ROOT/gazebo"
export GZ_SIM_RESOURCE_PATH="$ROOT/gazebo"
gz sdf -k "$ROOT/gazebo/worlds/villa_v3.sdf"
python3 "$SCRIPT_DIR/validate_gazebo_outputs.py" --root "$ROOT" --output "$ROOT/gazebo/gazebo_validation.json"
"$SCRIPT_DIR/test_villa_v3_gazebo_headless.sh"
echo "Villa V3 Gazebo build complete: $ROOT/gazebo/worlds/villa_v3.sdf"
