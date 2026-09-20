import asyncio

from mavsdk import System
from mavsdk.offboard import OffboardError, PositionNedYaw


async def main():
    drone = System()

    print("Connecting...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected!")
            break

    print("Waiting for PX4...")
    async for health in drone.telemetry.health():
        if health.is_local_position_ok and health.is_home_position_ok:
            print("PX4 ready!")
            break

    # Set takeoff altitude
    await drone.action.set_takeoff_altitude(3.0)

    print("Arming...")
    await drone.action.arm()

    print("Taking off...")
    await drone.action.takeoff()

    print("Waiting 8 seconds for takeoff...")
    await asyncio.sleep(8)

    # Offboard needs an initial setpoint before start()
    print("Setting initial Offboard setpoint...")
    await drone.offboard.set_position_ned(
        PositionNedYaw(
            0.0,   # North
            0.0,   # East
            -3.0,  # Down
            0.0    # Yaw
        )
    )

    print("Starting Offboard mode...")
    try:
        await drone.offboard.start()
    except OffboardError as error:
        print(f"Offboard start failed: {error._result.result}")
        return

    # Position control target
    print("Flying to N=5, E=0, D=-3...")
    await drone.offboard.set_position_ned(
        PositionNedYaw(
            5.0,   # North
            0.0,   # East
            -3.0,  # Down
            0.0    # Yaw
        )
    )

    print("Monitoring position... Press Ctrl+C to stop.")

    async for pv in drone.telemetry.position_velocity_ned():
        print(
            f"N: {pv.position.north_m:6.2f} m | "
            f"E: {pv.position.east_m:6.2f} m | "
            f"D: {pv.position.down_m:6.2f} m"
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
