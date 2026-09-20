import asyncio
from mavsdk import System


async def main():
    drone = System()
    await drone.connect(system_address="udpin://0.0.0.0:14540")
    print("Waiting for drone...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected")
            break

    async for position in drone.telemetry.position():
        print(f"Lat: {position.latitude_deg}")
        print(f"Lon: {position.longitude_deg}")
        print(f"Relative altitude: {position.relative_altitude_m:.2f} m")
        break


asyncio.run(main())
