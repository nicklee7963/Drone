import asyncio
from mavsdk import System


async def main():
    drone = System()

    print("Connecting to PX4...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected to PX4!")
            break

    print("Reading armed state...")

    async for armed in drone.telemetry.armed():
        print(f"Armed: {armed}")


if __name__ == "__main__":
    asyncio.run(main())
