import asyncio
from mavsdk import System


async def main():
    drone = System()

    # STATE 1 — CONNECT
    print("[STATE] CONNECTING")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[STATE] CONNECTED")
            break

    # STATE 2 — WAIT UNTIL PX4 IS READY
    print("[STATE] WAITING_FOR_HEALTH")

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("[STATE] READY")
            break

    # Set desired takeoff altitude
    await drone.action.set_takeoff_altitude(3.0)

    # STATE 3 — ARM
    print("[STATE] ARMING")
    await drone.action.arm()

    # Confirm actual armed state
    async for armed in drone.telemetry.armed():
        if armed:
            print("[STATE] ARMED")
            break

    # STATE 4 — TAKEOFF
    print("[STATE] TAKING_OFF")
    await drone.action.takeoff()

    # Confirm altitude using telemetry
    async for pv in drone.telemetry.position_velocity_ned():
        altitude = -pv.position.down_m

        print(f"[TAKEOFF] altitude = {altitude:.2f} m")

        if altitude >= 2.7:
            print("[STATE] TARGET_ALTITUDE_REACHED")
            break

    # STATE 5 — HOVER
    print("[STATE] HOVERING")
    await asyncio.sleep(5)

    # STATE 6 — LAND
    print("[STATE] LANDING")
    await drone.action.land()

    # Confirm actual landing
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            print("[STATE] LANDED")
            break

    print("[STATE] COMPLETE")


if __name__ == "__main__":
    asyncio.run(main())
