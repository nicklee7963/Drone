import asyncio
import math

from mavsdk import System
from mavsdk.offboard import OffboardError, PositionNedYaw


async def wait_until_reached(drone, target_n, target_e, target_d, tolerance=0.3):
    async for pv in drone.telemetry.position_velocity_ned():
        n = pv.position.north_m
        e = pv.position.east_m
        d = pv.position.down_m

        error = math.sqrt(
            (target_n - n) ** 2
            + (target_e - e) ** 2
            + (target_d - d) ** 2
        )

        print(
            f"N: {n:6.2f} | "
            f"E: {e:6.2f} | "
            f"D: {d:6.2f} | "
            f"error: {error:.2f} m"
        )

        if error < tolerance:
            print("Target reached!\n")
            break


async def goto(drone, north, east, down, yaw=0.0):
    print(
        f"Going to N={north}, "
        f"E={east}, D={down}, Yaw={yaw}"
    )

    await drone.offboard.set_position_ned(
        PositionNedYaw(
            north,
            east,
            down,
            yaw
        )
    )

    await wait_until_reached(
        drone,
        north,
        east,
        down
    )


async def main():
    drone = System()

    print("Connecting...")
    await drone.connect(
        system_address="udpin://0.0.0.0:14540"
    )

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected!")
            break

    print("Waiting for PX4...")

    async for health in drone.telemetry.health():
        if (
            health.is_local_position_ok
            and health.is_home_position_ok
        ):
            print("PX4 ready!")
            break

    await drone.action.set_takeoff_altitude(3.0)

    print("Arming...")
    await drone.action.arm()

    print("Taking off...")
    await drone.action.takeoff()

    print("Waiting for takeoff...")
    await asyncio.sleep(8)

    print("Setting initial setpoint...")
    await drone.offboard.set_position_ned(
        PositionNedYaw(
            0.0,
            0.0,
            -3.0,
            0.0
        )
    )

    print("Starting Offboard...")

    try:
        await drone.offboard.start()

    except OffboardError as error:
        print(
            f"Offboard failed: "
            f"{error._result.result}"
        )

        await drone.action.land()
        return

    print("\n--- Starting Square Mission ---\n")

    await goto(
        drone,
        5.0,
        0.0,
        -3.0
    )

    await goto(
        drone,
        5.0,
        5.0,
        -3.0
    )

    await goto(
        drone,
        0.0,
        5.0,
        -3.0
    )

    await goto(
        drone,
        0.0,
        0.0,
        -3.0
    )

    print("--- Square Mission Complete ---")

    print("Stopping Offboard...")

    try:
        await drone.offboard.stop()

    except OffboardError as error:
        print(
            f"Offboard stop error: "
            f"{error._result.result}"
        )

    print("Landing...")
    await drone.action.land()

    async for in_air in drone.telemetry.in_air():
        if not in_air:
            break

    print("Landed!")
    print("Mission complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nProgram interrupted.")
