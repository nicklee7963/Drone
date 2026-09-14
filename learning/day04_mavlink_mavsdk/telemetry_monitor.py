import asyncio
from mavsdk import System


async def print_armed(drone):
    async for armed in drone.telemetry.armed():
        print(f"[ARMED] {armed}")


async def print_flight_mode(drone):
    async for mode in drone.telemetry.flight_mode():
        print(f"[MODE] {mode}")


async def print_attitude(drone):
    await drone.telemetry.set_rate_attitude_euler(2.0)

    async for attitude in drone.telemetry.attitude_euler():
        print(
            f"[ATTITUDE] "
            f"Roll={attitude.roll_deg:6.2f}°  "
            f"Pitch={attitude.pitch_deg:6.2f}°  "
            f"Yaw={attitude.yaw_deg:6.2f}°"
        )


async def main():
    drone = System()

    print("Connecting to PX4...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected to PX4!\n")
            break

    tasks = [
        asyncio.create_task(print_armed(drone)),
        asyncio.create_task(print_flight_mode(drone)),
        asyncio.create_task(print_attitude(drone)),
        asyncio.create_task(print_position_velocity(drone)),
    ]

    await asyncio.gather(*tasks)

async def print_position_velocity(drone):
    await drone.telemetry.set_rate_position_velocity_ned(2.0)

    async for pv in drone.telemetry.position_velocity_ned():
        print(
            f"[LOCAL] "
            f"N={pv.position.north_m:6.2f} m  "
            f"E={pv.position.east_m:6.2f} m  "
            f"D={pv.position.down_m:6.2f} m  |  "
            f"VN={pv.velocity.north_m_s:5.2f} m/s  "
            f"VE={pv.velocity.east_m_s:5.2f} m/s  "
            f"VD={pv.velocity.down_m_s:5.2f} m/s"
        )


if __name__ == "__main__":
    asyncio.run(main())



