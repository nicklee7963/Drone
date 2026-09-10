# Alishan Shizhuo Gazebo Terrain Design

## Goal

Create a terrain-only Gazebo Harmonic world that loads the validated Alishan Shizhuo 20 m GeoTIFF DEM directly, with matching visual and collision heightmaps. This is a geometry-validation stage only; it does not add a vehicle, PX4, ROS 2, vegetation, buildings, roads, imagery, Blender content, weather, or navigation.

## Runtime and source data

The installed runtime is Gazebo Harmonic with `gz-sim8` 8.15.0, `gz-common5-geospatial`, and GDAL 3.4.1. The installed geospatial library links to GDAL, and the Gazebo DEM loader accepts one-band GDAL-readable DEM files. The source raster is the existing unmodified `data/processed/alishan_shizhuo_terrain_20m.tif`: a one-band Float32 GeoTIFF in EPSG:3826 with a 25 by 25 grid, 20 m spacing, 500 m by 500 m physical extent, no NoData values, and TWVD2001 elevations from 1330.340 m through 1560.170 m.

## Asset layout

The Gazebo model is placed at `gazebo/models/alishan_shizhuo_terrain/`, with `model.config` and `model.sdf`. Its `terrain/alishan_shizhuo_terrain_20m.tif` entry is a relative symbolic link to the processed GeoTIFF, so the terrain model has a stable `model://` URI without duplicating or modifying the validated terrain data. The world is `gazebo/worlds/alishan_shizhuo.sdf` and includes the model using that URI.

## Coordinate and elevation convention

The terrain model is static and centered horizontally at local `(0, 0)`. Its SDF heightmap uses an explicit size of `500 500 229.830` metres and a position offset of `0 0 -1330.340` metres. Therefore:

```text
local Gazebo Z = TWVD2001 elevation - 1330.340 m
```

The terrain local minimum is 0.000 m, the maximum is 229.830 m, and the validated center elevation is 111.100 m. This preserves all relative relief without vertical exaggeration and avoids placing the terrain at approximately 1.4 km local Z.

The V0 world has no `spherical_coordinates`. The site latitude and longitude remain documented as horizontal metadata, but SDF does not attach a vertical datum to the world-origin elevation. Storing a TWVD2001 height as an Earth WGS84 reference elevation would assert an unverified datum conversion. Geographic anchoring is deferred until a defensible vertical-datum transformation is selected.

Gazebo Harmonic's DART collision attachment uses the collision element pose when it constructs a heightfield, rather than applying the nested heightmap position by itself. The collision therefore explicitly repeats `0 0 -1330.340 0 0 0`; the visual retains the equivalent nested heightmap position. This aligns their declared local origin while retaining the standard direct-DEM SDF values. DART also internally pads/resamples this 25 by 25 heightfield, so runtime contact sampling remains limited by the original 20 m DTM and should be revisited before vehicle dynamics validation.

## World and validation

The world declares ordinary Earth gravity, a 1 ms physics step, the Physics, UserCommands, and SceneBroadcaster systems, a directional sun, neutral scene lighting, and an initial overview camera. The terrain model contains both collision and visual geometry from the same direct GeoTIFF URI. No marker is added.

A standard-library validation CLI parses the generated SDF, verifies the two heightmaps, checks the explicit horizontal size, vertical relief, position convention, reachable terrain asset, and processed GeoTIFF checksum. Unit tests exercise that validator without launching Gazebo. Runtime checks use `gz sim` server-only mode first, then headless rendering and GUI rendering when display support permits. The original processed GeoTIFF hash must be unchanged before and after every runtime invocation.

## Constraints

- Preserve `data/processed/alishan_shizhuo_terrain_20m.tif` unchanged.
- Load the GeoTIFF directly; do not create a PNG or another terrain raster for Gazebo.
- Do not add a geographic anchor in V0.
- Do not create PX4, ROS 2, QGroundControl, road, building, vegetation, Blender, imagery, weather, or navigation files.
- Do not modify `PX4-Autopilot/`.
