import math

from frame_converter import (
    ned_to_enu,
    enu_to_ned,
    body_to_ned,
)


def close(a, b, eps=1e-6):
    return abs(a - b) < eps


# Test 1: NED -> ENU
enu = ned_to_enu(8, -2, -4)

assert enu == (-2, 8, 4)

print("PASS: NED -> ENU")


# Test 2: ENU -> NED
ned = enu_to_ned(-2, 8, 4)

assert ned == (8, -2, -4)

print("PASS: ENU -> NED")


# Test 3: Body forward 5 m, yaw = 90 deg
# Drone faces East, so forward should become East +5 in NED.

north, east, down = body_to_ned(
    forward=5,
    right=0,
    down=0,
    yaw_deg=90,
)

assert close(north, 0)
assert close(east, 5)
assert close(down, 0)

print("PASS: Body -> NED, yaw 90 deg")


# Test 4: Body forward 4 m, yaw = 180 deg
# Drone faces South, so forward should become North -4.

north, east, down = body_to_ned(
    forward=4,
    right=0,
    down=0,
    yaw_deg=180,
)

assert close(north, -4)
assert close(east, 0)
assert close(down, 0)

print("PASS: Body -> NED, yaw 180 deg")


print("\nALL FRAME TESTS PASSED")
