import asyncio
from mavsdk import System


async def main():
    drone = System()

    print("Connecting...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected!")
            break

    async for position in drone.telemetry.position_velocity_ned():
        print(
            f"N: {position.position.north_m:.2f} m | "
            f"E: {position.position.east_m:.2f} m | "
            f"D: {position.position.down_m:.2f} m"
        )


if __name__ == "__main__":
    asyncio.run(main())
