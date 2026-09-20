import asyncio
from mavsdk import System


async def print_position_velocity(drone):
    async for pv in drone.telemetry.position_velocity_ned():
        p = pv.position
        v = pv.velocity

        print(
            f"NED Position [m]   "
            f"N={p.north_m:7.2f}  "
            f"E={p.east_m:7.2f}  "
            f"D={p.down_m:7.2f}"
        )

        print(
            f"NED Velocity [m/s] "
            f"N={v.north_m_s:7.2f}  "
            f"E={v.east_m_s:7.2f}  "
            f"D={v.down_m_s:7.2f}"
        )

        await asyncio.sleep(0.5)


async def print_attitude(drone):
    async for attitude in drone.telemetry.attitude_euler():
        print(
            f"Attitude [deg]     "
            f"Roll={attitude.roll_deg:7.2f}  "
            f"Pitch={attitude.pitch_deg:7.2f}  "
            f"Yaw={attitude.yaw_deg:7.2f}"
        )

        await asyncio.sleep(0.5)


async def main():
    drone = System()

    print("Connecting to PX4...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("Connected.")
            break

    await asyncio.gather(
        print_position_velocity(drone),
        print_attitude(drone),
    )


if __name__ == "__main__":
    asyncio.run(main())
