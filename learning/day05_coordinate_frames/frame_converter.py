import math


def ned_to_enu(north, east, down):
    """
    NED -> ENU

    NED:
        x = North
        y = East
        z = Down

    ENU:
        x = East
        y = North
        z = Up
    """
    return east, north, -down


def enu_to_ned(east, north, up):
    """
    ENU -> NED
    """
    return north, east, -up


def body_to_ned(forward, right, down, yaw_deg):
    """
    Convert a vector from PX4 Body FRD frame to NED.

    Body:
        x = Forward
        y = Right
        z = Down

    yaw:
        0 deg   = North
        90 deg  = East
        180 deg = South
    """

    yaw = math.radians(yaw_deg)

    north = (
        math.cos(yaw) * forward
        - math.sin(yaw) * right
    )

    east = (
        math.sin(yaw) * forward
        + math.cos(yaw) * right
    )

    return north, east, down
