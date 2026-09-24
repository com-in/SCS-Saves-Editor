"""Extract a placement map from Unity scene colliders without modifying game files."""
from __future__ import annotations

import os
import pickle
import hashlib
import math
from functools import lru_cache


def _v3(value):
    if isinstance(value, (tuple, list)):
        return (float(value[0]), float(value[1]), float(value[2]))
    return (float(value.x), float(value.y), float(value.z))


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _rotate(q, v):
    """Rotate a vector using a Unity quaternion (x, y, z, w)."""
    x, y, z, w = q
    ux, uy, uz = x, y, z
    tx, ty, tz = (2 * (uy * v[2] - uz * v[1]),
                  2 * (uz * v[0] - ux * v[2]),
                  2 * (ux * v[1] - uy * v[0]))
    return (v[0] + w * tx + uy * tz - uz * ty,
            v[1] + w * ty + uz * tx - ux * tz,
            v[2] + w * tz + ux * ty - uy * tx)


def _mul_quaternion(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw,
            aw*bw - ax*bx - ay*by - az*bz)


def _q4(value):
    return (float(value.x), float(value.y), float(value.z), float(value.w))


def load_map_layout(path):
    """Extract the actual walkable floors and walls from level colliders.

    Unlike the old mesh preview this traverses the entire scene and applies
    parent position, rotation, and scale to each floor/wall footprint.
    """
    import UnityPy

    env = UnityPy.load(path)
    names = {}
    transforms = {}
    colliders = []
    for obj in env.objects:
        typ = obj.type.name
        if typ == "GameObject":
            go = obj.read()
            names[obj.path_id] = go.m_Name
        elif typ == "Transform":
            transforms[obj.path_id] = obj.read()
        elif typ == "BoxCollider":
            colliders.append(obj.read())

    owner = {tr.m_GameObject.path_id: path_id for path_id, tr in transforms.items()}

    @lru_cache(maxsize=None)
    def world_transform(path_id):
        tr = transforms[path_id]
        position, rotation, scale = _v3(tr.m_LocalPosition), _q4(tr.m_LocalRotation), _v3(tr.m_LocalScale)
        parent_id = tr.m_Father.m_PathID
        if parent_id in transforms:
            pp, pr, ps = world_transform(parent_id)
            scaled = tuple(position[i] * ps[i] for i in range(3))
            position = _add(pp, _rotate(pr, scaled))
            rotation = _mul_quaternion(pr, rotation)
            scale = tuple(scale[i] * ps[i] for i in range(3))
        return position, rotation, scale

    def to_world(point, transform):
        position, rotation, scale = transform
        return _add(position, _rotate(rotation, tuple(point[i] * scale[i] for i in range(3))))

    objects = []
    bounds = []
    for collider in colliders:
        game_object_id = collider.m_GameObject.m_PathID
        name = names.get(game_object_id, "")
        low = name.lower()
        size = _v3(collider.m_Size)
        if "floor" in low or low == "ground" or low == "officeground":
            kind = "floor"
        elif low.startswith(("wall", "officewall", "workerroomwall", "lowergroundwall", "fence")):
            kind = "wall"
        else:
            continue
        transform_id = owner.get(game_object_id)
        if transform_id is None or min(abs(size[0]), abs(size[2])) < 0.01:
            continue
        transform = world_transform(transform_id)
        center = _v3(collider.m_Center)
        half = tuple(component / 2 for component in size)
        if kind == "floor":
            y = center[1] + half[1]
            local = [(center[0]-half[0], y, center[2]-half[2]),
                     (center[0]+half[0], y, center[2]-half[2]),
                     (center[0]+half[0], y, center[2]+half[2]),
                     (center[0]-half[0], y, center[2]+half[2])]
        else:
            # Walls are shown as a narrow top strip in the map, not full-height panels.
            y = center[1] + half[1]
            local = [(center[0]-half[0], y, center[2]-half[2]),
                     (center[0]+half[0], y, center[2]-half[2]),
                     (center[0]+half[0], y, center[2]+half[2]),
                     (center[0]-half[0], y, center[2]+half[2])]
        corners = [to_world(point, transform) for point in local]
        base_y = min(to_world((center[0], center[1]-half[1], center[2]), transform)[1],
                     to_world((center[0], center[1]+half[1], center[2]), transform)[1])
        if any(not math.isfinite(component) for corner in corners for component in corner):
            continue
        # Ignore decorative colliders with huge extents.
        if max(math.dist(corners[0], corners[1]), math.dist(corners[1], corners[2])) > 120:
            continue
        objects.append({"name": name, "kind": kind, "quad": corners, "base_y": base_y,
                        "triangles": [
            (corners[0], corners[1], corners[2]), (corners[0], corners[2], corners[3])]})
        bounds.extend(corners)

    floor_heights = [obj["quad"][0][1] for obj in objects if obj["kind"] == "floor"]
    # Large horizontal planes identify storeys; stairs and short ramps do not.
    candidates = []
    for y in sorted(floor_heights):
        if any(abs(y - existing) < 0.35 for existing in candidates):
            continue
        count = sum(abs(y - other) < 0.35 for other in floor_heights)
        if count >= 20:
            candidates.append(y)
    floor_levels = []
    for y in sorted(candidates, key=lambda value: -sum(abs(value - other) < 0.35 for other in floor_heights)):
        if all(abs(y - existing) >= 2.3 for existing in floor_levels):
            floor_levels.append(y)
    floor_levels.sort()
    return {"source": os.path.abspath(path), "objects": objects,
            "triangle_count": len(objects) * 2, "object_count": len(objects),
            "floor_levels": floor_levels,
            "layout_bounds": (min(v[0] for v in bounds), max(v[0] for v in bounds),
                              min(v[2] for v in bounds), max(v[2] for v in bounds)) if bounds else None}


def load_scene_cached(path, cache_dir=None):
    """Load a scene from a small local cache keyed by source metadata."""
    source = os.path.abspath(path)
    cache_dir = cache_dir or os.path.join(os.path.dirname(source), "..", "..", "..", "SCS-Saves-Editor-Cache")
    os.makedirs(cache_dir, exist_ok=True)
    stat = os.stat(source)
    key = f"layout-v5|{source}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8")
    cache_path = os.path.join(cache_dir, hashlib.sha256(key).hexdigest() + ".pkl")
    try:
        with open(cache_path, "rb") as fh:
            cached = pickle.load(fh)
        if isinstance(cached, dict) and cached.get("source") == source:
            cached["cached"] = True
            return cached
    except (OSError, ValueError, EOFError, pickle.PickleError):
        pass
    scene = load_map_layout(source)
    temp = cache_path + ".tmp"
    with open(temp, "wb") as fh:
        pickle.dump(scene, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(temp, cache_path)
    scene["cached"] = False
    return scene
