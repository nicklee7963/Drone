import asyncio
import math

from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan


def offset_latlon(lat_deg, lon_deg, north_m, east_m):
    R = 6378137.0

    d_lat = north_m / R
    d_lon = east_m / (R * math.cos(math.radians(lat_deg)))

    return (
        lat_deg + math.degrees(d_lat),
        lon_deg + math.degrees(d_lon),
    )


def generate_survey_points(width_m, height_m, spacing_m):
    points = []

    north = 0.0
    eastward = True

    while north <= height_m:
        if eastward:
            points.append((north, 0.0))
            points.append((north, width_m))
        else:
            points.append((north, width_m))
            points.append((north, 0.0))

        north += spacing_m
        eastward = not eastward

    return points


def make_waypoint(lat, lon, altitude):
    return MissionItem(
        lat,
        lon,
        altitude,
        3.0,                              # speed
        True,                             # fly-through
        float("nan"),
        float("nan"),
        MissionItem.CameraAction.NONE,
        float("nan"),
        float("nan"),
        1.0,                              # acceptance radius
        float("nan"),
        float("nan"),
        MissionItem.VehicleAction.NONE,
    )


async def main():
    drone = System()

    await drone.connect(
        system_address="udpin://0.0.0.0:14540"
    )

    print("Waiting for drone...")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected")
            break

    print("Waiting for global position...")

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("Global position OK")
            break

    async for position in drone.telemetry.position():
        home_lat = position.latitude_deg
        home_lon = position.longitude_deg
        break

    print(f"HOME: {home_lat}, {home_lon}")

    # Generate survey in local North/East coordinates
    survey_points = generate_survey_points(
        width_m=20,
        height_m=20,
        spacing_m=5,
    )

    mission_items = []

    for i, (north, east) in enumerate(survey_points):
        lat, lon = offset_latlon(
            home_lat,
            home_lon,
            north,
            east,
        )

        print(
            f"WP{i}: "
            f"N={north:.1f}, "
            f"E={east:.1f}"
        )

        mission_items.append(
            make_waypoint(
                lat,
                lon,
                altitude=5.0,
            )
        )

    mission_plan = MissionPlan(mission_items)

    await drone.mission.set_return_to_launch_after_mission(True)

    print("Uploading survey mission...")
    await drone.mission.upload_mission(mission_plan)

    print("Arming...")
    await drone.action.arm()

    print("Starting survey...")
    await drone.mission.start_mission()

    async for progress in drone.mission.mission_progress():
        print(
            f"Progress: "
            f"{progress.current}/{progress.total}"
        )

        if progress.current == progress.total:
            print("Survey finished")
            break


asyncio.run(main())
