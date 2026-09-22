"""ES3 safeguards traced to Assembly-CSharp sources in F:/GameUnpack."""
import json
import math
import os
import shutil
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


def number(value, *, integer=False, label='数值', minimum=None, maximum=None):
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f'{label}：请输入有效数字') from None
    if not parsed.is_finite():
        raise ValueError(f'{label}：不能是 NaN 或无穷大')
    if integer and parsed != parsed.to_integral_value():
        raise ValueError(f'{label}：必须为整数，不能丢弃小数部分')
    result = int(parsed) if integer else float(parsed)
    if not integer and (not math.isfinite(result) or abs(result) > 3.402823466e38):
        raise ValueError(f'{label}：超出游戏浮点数范围')
    if integer and not -2147483648 <= result <= 2147483647:
        raise ValueError(f'{label}：超出游戏整数范围')
    if minimum is not None and result < minimum:
        raise ValueError(f'{label}：不能小于 {minimum}')
    if maximum is not None and result > maximum:
        raise ValueError(f'{label}：不能大于 {maximum}')
    return result


def integer_list(text, label='整数列表'):
    if not str(text).strip():
        return []
    return [number(part, integer=True, label=f'{label}第 {i + 1} 项')
            for i, part in enumerate(str(text).replace('，', ',').split(','))]


def validate_document(data):
    if not isinstance(data, dict) or not data:
        raise ValueError('存档必须是非空的 ES3 JSON 对象')
    if not any(isinstance(node, dict) and 'value' in node for node in data.values()):
        raise ValueError('未找到 ES3 的 value 字段，请选择游戏存档')
    json.dumps(data, ensure_ascii=False, allow_nan=False)


def validate_changes(data, original):
    """Only validate changed known keys, retaining unknown/version-specific data."""
    validate_document(data)
    for key, node in data.items():
        if not isinstance(node, dict) or 'value' not in node or node == original.get(key):
            continue
        value = node['value']
        if key == 'Difficulty':
            number(value, integer=True, label='游戏难度', minimum=0, maximum=3)
        elif key == 'Cat' and isinstance(value, dict):
            indices, streaks = value.get('catIndices', []), value.get('feedStreaks', [])
            if len(indices) != len(streaks):
                raise ValueError('宠物猫：猫 ID 与喂养天数必须一一对应')
            if len(set(indices)) != len(indices):
                raise ValueError('宠物猫：猫 ID 不能重复')
            for v in indices:
                number(v, integer=True, label='猫 ID', minimum=0)
            for v in streaks:
                number(v, integer=True, label='喂养天数', minimum=0)
            adopted = number(value.get('adoptedCatIndex', -1), integer=True, label='领养猫 ID', minimum=-1)
            if adopted != -1 and adopted not in indices:
                raise ValueError('宠物猫：领养的猫 ID 必须在猫 ID 列表中')
        elif key == 'BodyGuard' and isinstance(value, dict):
            seen = set()
            for guard in value.get('guards', []):
                slot = number(guard['slotIndex'], integer=True, label='保镖槽位', minimum=0)
                if slot in seen:
                    raise ValueError(f'保镖槽位 {slot} 重复')
                seen.add(slot)
                number(guard['healthNormalized'], label='保镖生命值', minimum=0, maximum=1)
        elif key == 'AirportNpc':
            if not isinstance(value, list) or any(
                    not isinstance(batch, list) or any(not isinstance(npc, dict) for npc in batch)
                    for batch in value):
                raise ValueError('机场队列必须为完整 NPC 对象的二维数组，不能只保存职业 ID')
        elif key == 'NpcPurchase' and isinstance(value, dict):
            number(value.get('npcCountPerPurchase'), integer=True, label='每次采购人数', minimum=1)
            number(value.get('timeInterval'), label='采购间隔', minimum=1, maximum=360)


def atomic_write(path, data, *, backup=True):
    validate_document(data)
    content = json.dumps(data, ensure_ascii=False, indent='\t', allow_nan=False)
    target = Path(path)
    backup_path = None
    if backup and target.exists():
        folder = target.parent / 'ES3_Backups'
        folder.mkdir(exist_ok=True)
        backup_path = folder / (target.name + '.backup_save_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        shutil.copy2(target, backup_path)
    fd, temp = tempfile.mkstemp(prefix=target.name + '.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return backup_path
