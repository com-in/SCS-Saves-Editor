"""Shared item rotation and collision-box geometry for painting and picking."""
import math

from unity_scene_loader import _rotate, _mul_quaternion


def quaternion(value):
    try:
        q = tuple(float(value.get(k, d)) for k, d in zip("xyzw", (0, 0, 0, 1))) if isinstance(value, dict) else tuple(value)
        length = math.hypot(*q)
        if len(q) != 4 or not math.isfinite(length) or length < 1e-12:
            raise ValueError("Invalid quaternion")
        return tuple(v / length for v in q)
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0, 1.0)


def yaw_rotation(degrees):
    angle = math.radians(degrees) / 2
    return (0.0, math.sin(angle), 0.0, math.cos(angle))


def heading(rotation):
    forward = _rotate(quaternion(rotation), (0, 0, 1))
    return math.degrees(math.atan2(forward[0], forward[2])) % 360


def rotate_world_y(rotation, degrees):
    # Match ItemPlacingSystem.Rotate(Vector3.up, angle, Space.World).
    return quaternion(_mul_quaternion(yaw_rotation(degrees), quaternion(rotation)))


def box_corners(center, size):
    x, y, z = center
    w, h, d = (v / 2 for v in size)
    return [(x+dx, y+dy, z+dz) for dy in (-h, h)
            for dx, dz in ((-w, -d), (w, -d), (w, d), (-w, d))]


def world_corners(corners, rotation, position):
    return [tuple(a+b for a, b in zip(_rotate(rotation, v), position)) for v in corners]
