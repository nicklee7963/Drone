import asyncio
import math

from mavsdk import System
from mavsdk.mission import MissionItem, MissionPlan


def offset_latlon(lat_deg, lon_deg, north_m, east_m):
    earth_radius = 6378137.0

    d_lat = north_m / earth_radius
    d_lon = east_m / (earth_radius * math.cos(math.radians(lat_deg)))

    new_lat = lat_deg + math.degrees(d_lat)
    new_lon = lon_deg + math.degrees(d_lon)

    return new_lat, new_lon


def make_waypoint(lat, lon, altitude):
    return MissionItem(
        lat,
        lon,
        altitude,                         # relative altitude
        3.0,                              # speed m/s
        False,                            # stop at waypoint
        float("nan"),                     # gimbal pitch
        float("nan"),                     # gimbal yaw
        MissionItem.CameraAction.NONE,
        float("nan"),                     # loiter time
        float("nan"),                     # photo interval
        1.0,                              # acceptance radius
        float("nan"),                     # yaw
        float("nan"),                     # photo distance
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

    # Read current position
    async for position in drone.telemetry.position():
        home_lat = position.latitude_deg
        home_lon = position.longitude_deg
        break

    print(f"HOME: {home_lat}, {home_lon}")

    # Create waypoints
    wp1_lat, wp1_lon = offset_latlon(
        home_lat, home_lon,
        north_m=10,
        east_m=0,
    )

    wp2_lat, wp2_lon = offset_latlon(
        home_lat, home_lon,
        north_m=10,
        east_m=10,
    )

    wp3_lat, wp3_lon = offset_latlon(
        home_lat, home_lon,
        north_m=0,
        east_m=10,
    )

    mission_items = [
        make_waypoint(wp1_lat, wp1_lon, 5.0),
        make_waypoint(wp2_lat, wp2_lon, 5.0),
        make_waypoint(wp3_lat, wp3_lon, 5.0),
    ]

    mission_plan = MissionPlan(mission_items)

    print("Uploading mission...")
    await drone.mission.upload_mission(mission_plan)

    print("Mission uploaded")

    await drone.mission.set_return_to_launch_after_mission(True)

    print("Arming...")
    await drone.action.arm()

    print("Starting mission...")
    await drone.mission.start_mission()

    async for progress in drone.mission.mission_progress():
        print(
            f"Mission progress: "
            f"{progress.current}/{progress.total}"
        )

        if progress.current == progress.total:
            print("Mission finished")
            break


asyncio.run(main())
