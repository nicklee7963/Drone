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

    print("Waiting for PX4 to be ready...")

    async for health in drone.telemetry.health():
        if health.is_local_position_ok and health.is_home_position_ok:
            print("PX4 ready!")
            break

    print("Arming...")
    await drone.action.arm()

    print("ARMED")


if __name__ == "__main__":
    asyncio.run(main())
