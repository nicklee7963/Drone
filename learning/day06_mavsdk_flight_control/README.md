# Day 06 — MAVSDK Flight Control

## Goal

Control PX4 programmatically using MAVSDK.

## What I Learned

### MAVSDK Action API

High-level commands handled by PX4.

- `arm()` — arm the vehicle
- `takeoff()` — autonomous takeoff
- `land()` — autonomous landing
- `set_takeoff_altitude()` — configure takeoff altitude

Example:

```python
await drone.action.arm()
await drone.action.takeoff()
await drone.action.land()
