"""Read item prefab collision shapes in the prefab root's saved coordinate frame."""
import hashlib
import json
import math
import os
import struct

from _map_items import box_corners, quaternion
from unity_scene_loader import _v3, _q4, _rotate


def transform_corners(corners, chain):
    """Apply child-to-root TRS in order; root world position/rotation are saved separately."""
    result = []
    for point in corners:
        for position, rotation, scale in reversed(chain):
            point = _rotate(rotation, tuple(a*b for a, b in zip(point, scale)))
            point = tuple(a+b for a, b in zip(point, position))
        result.append(point)
    if math.prod(math.prod(scale) for _, _, scale in chain) < 0:
        result = [result[i] for i in (0, 3, 2, 1, 4, 7, 6, 5)]
    return result


def _string(raw, offset):
    length = struct.unpack_from('<i', raw, offset)[0]
    if length < 0 or offset+4+length > len(raw):
        raise ValueError("Invalid serialized string")
    return raw[offset+4:offset+4+length].decode('utf-8'), offset+4+((length+3)&~3)


def _item_header(raw):
    name, offset = _string(raw, 28)
    item_id = struct.unpack_from('<i', raw, offset)[0]
    _, offset = _string(raw, offset+4)  # itemName
    _, offset = _string(raw, offset)  # LocalizedString table reference
    _, offset = _string(raw, offset+8)  # table entry ID followed by entry key
    # FallbackState, WaitForCompletion (aligned), local variable count.
    # Nonempty local variables require a different schema; fail rather than guess.
    if struct.unpack_from('<i', raw, offset+8)[0] != 0:
        raise ValueError("Unsupported localized variables")
    return item_id, name, struct.unpack_from('<iq', raw, offset+12)


def _placement_definition(raw):
    """ItemData's serialized facility fields (Unity bools are 4-byte aligned)."""
    _, offset = _string(raw, 28)
    _, offset = _string(raw, offset+4)
    _, offset = _string(raw, offset)
    _, offset = _string(raw, offset+8)
    offset += 24+8+12  # localized tail, prefab, level/debt, icon
    _, offset = _string(raw, offset)  # description
    _, offset = _string(raw, offset)  # description localized table
    _, offset = _string(raw, offset+8)
    if struct.unpack_from('<i', raw, offset+8)[0] != 0:
        raise ValueError('Unsupported localized variables')
    tier = struct.unpack_from('<i', raw, offset+12)[0]
    offset += 16  # localized tail and tier
    flags = struct.unpack_from('<14i', raw, offset)
    if any(value not in (0, 1) for value in flags):
        raise ValueError('Unsupported ItemData facility schema')
    stock_index, interval = struct.unpack_from('<if', raw, offset+56)
    shelf_type = struct.unpack_from('<i', raw, offset+76)[0]
    if shelf_type not in range(6) or not math.isfinite(interval):
        raise ValueError('Invalid facility defaults')
    return {'tier': tier, 'is_placable': bool(flags[0]), 'is_shelf': bool(flags[3]),
            'is_wall': bool(flags[4]), 'is_cage': bool(flags[12]),
            'is_stock_station': bool(flags[13]), 'shelf_type': shelf_type,
            'stock_index': stock_index, 'stock_interval': interval}


def _read_item_refs(raw, offset, item_file, item_ids):
    """Read a bounded serialized List<ItemData>; reject unknown references."""
    count = struct.unpack_from('<i', raw, offset)[0]
    if count < 0 or count > 10000 or offset + 4 + count * 12 > len(raw):
        raise ValueError('Invalid scene item list')
    result = []
    for index in range(count):
        file_id, path_id = struct.unpack_from('<iq', raw, offset + 4 + index * 12)
        if file_id != item_file or path_id not in item_ids:
            raise ValueError('Unknown scene ItemData reference')
        result.append(item_ids[path_id])
    return result


def _read_mayor_refs(raw, offset, item_file, item_ids):
    """MayorExchange: ItemData PPtr, two amounts, then a variable NpcRole list."""
    count = struct.unpack_from('<i', raw, offset)[0]
    offset += 4
    if count < 0 or count > 10000:
        raise ValueError('Invalid mayor exchange count')
    result = []
    for _ in range(count):
        if offset + 24 > len(raw):
            raise ValueError('Truncated mayor exchange')
        file_id, path_id, required, current, roles = struct.unpack_from('<iqiii', raw, offset)
        if file_id != item_file or path_id not in item_ids:
            raise ValueError('Unknown mayor ItemData reference')
        if required < 0 or current < 0 or roles < 0 or roles > 10000:
            raise ValueError('Invalid mayor exchange fields')
        offset += 24 + roles * 12
        if offset > len(raw):
            raise ValueError('Truncated mayor role list')
        result.append(item_ids[path_id])
    return result


def _scene_item_catalog(env, data_dir, script_classes, item_ids):
    """Current main scene's serialized shop and save-load registry, not assets alone."""
    scene = env.load_file(os.path.join(data_dir, 'level1'))
    refs = {os.path.basename(ref.path.replace('\\', '/')): i + 1
            for i, ref in enumerate(scene.externals)}
    script_file, item_file = refs['globalgamemanagers.assets'], refs['sharedassets1.assets']
    shops, registries, mayors = [], [], []
    for obj in scene.objects.values():
        if obj.type.name != 'MonoBehaviour':
            continue
        raw = obj.get_raw_data()
        if len(raw) < 32:
            continue
        file_id, script_id = struct.unpack_from('<iq', raw, 16)
        if file_id != script_file:
            continue
        kind = script_classes.get(script_id)
        if kind not in ('ShopSystem', 'HouseManager', 'MayoMenuManager'):
            continue
        _, start = _string(raw, 28)
        if kind == 'ShopSystem':
            # debtManager, itemPrefab, content (PPtr); currency, meat, level.
            shops.append(_read_item_refs(raw, start + 48, item_file, item_ids))
        elif kind == 'MayoMenuManager':
            mayors.append(_read_mayor_refs(raw, start, item_file, item_ids))
        else:
            # shelfItems is empty in the shipped scene; never guess its layout.
            if struct.unpack_from('<i', raw, start)[0] != 0:
                raise ValueError('Unsupported scene shelfItems data')
            registry = _read_item_refs(raw, start + 4, item_file, item_ids)
            # HouseManager.GetItemDataFromId indexes directly into this list.
            if registry != list(range(len(registry))):
                raise ValueError('Item registry indices do not match ItemData IDs')
            registries.append(registry)
    if len(shops) != 1 or len(registries) != 1 or len(mayors) != 1 or not shops[0]:
        raise ValueError('Cannot verify unique shop, mayor exchange and item registry')
    return set(shops[0]), set(registries[0]), set(mayors[0])


def extract_item_profiles(data_dir):
    import UnityPy
    env = UnityPy.Environment()
    env.path = os.path.abspath(data_dir)
    scripts = env.load_file(os.path.join(data_dir, 'globalgamemanagers.assets'))
    script_ids = set()
    script_classes = {}
    for obj in scripts.objects.values():
        if obj.type.name == 'MonoScript':
            script_classes[obj.path_id] = obj.read().m_ClassName
            if script_classes[obj.path_id] == 'ItemData':
                script_ids.add(obj.path_id)
    assets = env.load_file(os.path.join(data_dir, 'sharedassets1.assets'))
    script_files = {i+1 for i, ref in enumerate(assets.externals)
                    if os.path.basename(ref.path.replace('\\', '/')) == 'globalgamemanagers.assets'}
    profiles, definitions, missing, item_ids = {}, {}, [], {}
    for obj in list(assets.objects.values()):
        if obj.type.name != 'MonoBehaviour':
            continue
        raw = obj.get_raw_data()
        if len(raw) < 28:
            continue
        script_file, script_id = struct.unpack_from('<iq', raw, 16)
        if script_file not in script_files or script_id not in script_ids:
            continue
        try:
            item_id, name, (file_id, path_id) = _item_header(raw)
            item_ids[obj.path_id] = item_id
            definition = _placement_definition(raw)
            definition['has_placable_component'] = False
            definitions[item_id] = definition
            # Current game's ItemData and itemPrefab live in sharedassets1.
            # Reject an unsupported external reference instead of using a wrong ID.
            if file_id != 0 or path_id not in assets.objects:
                raise ValueError('Unavailable prefab')
            prefab = assets.objects[path_id]
            if prefab.type.name != 'GameObject':
                raise ValueError('Invalid prefab reference')
            for component in prefab.read().m_Component:
                reader = component.component.deref()
                if reader.type.name != 'MonoBehaviour':
                    continue
                component_raw = reader.get_raw_data()
                file_ref, script_ref = struct.unpack_from('<iq', component_raw, 16)
                if file_ref in script_files and script_classes.get(script_ref) == 'PlacableObject':
                    definition['has_placable_component'] = True
            boxes = []

            def walk(go, chain, root=False):
                if not go.m_IsActive and not root:
                    return
                components = [c.component.deref() for c in go.m_Component]
                transform = next((c.read() for c in components if c.type.name == 'Transform'), None)
                if transform is None:
                    return  # Ignore UI/RectTransform subtrees.
                trs = ((0, 0, 0), (0, 0, 0, 1), _v3(transform.m_LocalScale)) if root else (
                    _v3(transform.m_LocalPosition), quaternion(_q4(transform.m_LocalRotation)), _v3(transform.m_LocalScale))
                chain = chain+[trs]
                for component in components:
                    if component.type.name != 'BoxCollider':
                        continue
                    collider = component.read()
                    if collider.m_IsTrigger or not collider.m_Enabled:
                        continue
                    corners = transform_corners(box_corners(_v3(collider.m_Center), _v3(collider.m_Size)), chain)
                    if all(math.isfinite(x) and abs(x) < 1000 for v in corners for x in v):
                        boxes.append(corners)
                for child in transform.m_Children:
                    walk(child.read().m_GameObject.read(), chain)

            walk(prefab.read(), [], root=True)
            if not boxes:
                raise ValueError('No physical box colliders')
            vertices = [v for box in boxes for v in box]
            bounds = [[min(v[i] for v in vertices), max(v[i] for v in vertices)] for i in range(3)]
            profiles[item_id] = {'name': name, 'boxes': boxes, 'bounds': bounds, 'source': 'BoxCollider'}
        except (ValueError, KeyError, struct.error) as exc:
            missing.append({'asset': obj.path_id, 'reason': str(exc)})
    if not profiles:
        raise ValueError('无法读取当前游戏版本的物品碰撞体尺寸')
    catalog_error = None
    try:
        shop_ids, registered_ids, mayor_ids = _scene_item_catalog(env, data_dir, script_classes, item_ids)
        for item_id, definition in definitions.items():
            definition['in_shop'] = item_id in shop_ids
            definition['registered'] = item_id in registered_ids
            definition['in_mayor_exchange'] = item_id in mayor_ids
    except (OSError, ValueError, KeyError, struct.error) as exc:
        # Geometry still works; unverified items must not become addable.
        catalog_error = str(exc)
    return {'profiles': profiles, 'definitions': definitions, 'missing': missing,
            'catalog_error': catalog_error}


def load_item_profiles(data_dir, cache_dir):
    sources = [os.path.join(data_dir, name) for name in ('globalgamemanagers.assets', 'sharedassets1.assets', 'level1')]
    identity = '|'.join(f'{os.path.abspath(p)}:{os.stat(p).st_size}:{os.stat(p).st_mtime_ns}' for p in sources)
    key = hashlib.sha256(('item-boxes-v5|'+identity).encode('utf-8')).hexdigest()
    path = os.path.join(cache_dir, 'items-'+key+'.json')
    try:
        with open(path, encoding='utf-8') as fh:
            result = json.load(fh)
        result['profiles'] = {int(k): v for k, v in result['profiles'].items()}
        result['definitions'] = {int(k): v for k, v in result['definitions'].items()}
        return result
    except (OSError, ValueError, KeyError):
        pass
    result = extract_item_profiles(data_dir)
    os.makedirs(cache_dir, exist_ok=True)
    with open(path+'.tmp', 'w', encoding='utf-8') as fh:
        json.dump(result, fh, ensure_ascii=False)
    os.replace(path+'.tmp', path)
    return result
