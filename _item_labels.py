"""Item labels using ItemData.tier, not the player's unlock level."""
from _item_data import USER_ITEM_NAME

# Extracted from the game's serialized ItemData; omitted catalog IDs have tier 1.
# Keep labels available even when no game scene has been loaded.
ITEM_TIERS = dict.fromkeys(USER_ITEM_NAME, 1)
ITEM_TIERS.update({29: 2, 37: 2, 83: 2, 84: 3, 94: 2, 95: 2, 96: 3,
    97: 4, 98: 2, 99: 3, 100: 4, 104: 2, 105: 2, 106: 3, 107: 2,
    109: 2, 110: 3, 111: 999, 115: 2, 116: 3, 122: 2, 123: 3,
    124: 4, 126: 3, 127: 2, 128: 2, 131: 3, 132: 2, 133: 3,
    135: 4, 137: 3, 138: 4, 140: 2, 141: 2, 149: 2, 151: 2, 163: 3})

# Purpose first, then item family, then numeric tier. IDs only break ties;
# neither the saved item order nor the displayed name depends on this index.
_ITEM_GROUPS = (
    ('床', '双层床', '床垫'),
    ('网络钓鱼工作站', '恋爱诈骗站', '黑客终端', '挖矿站', '工作台', '小型工作台'),
    ('餐桌', '饮水机', '自动贩卖机', '马桶', '淋浴设备', '风扇', '空调',
     '药品架', '垃圾桶', '垃圾箱', '扫地机器人'),
    ('手摇发电机', '脚踏发电机', '人力仓鼠轮', '风力发电机', '太阳能板'),
    ('存储架', '小型食品储藏柜', '食品储藏柜', '进货终端'),
    ('小型笼子', '大型笼子', '电椅', '绞肉机', '器官移植椅', '器官摘取椅', '献祭'),
    ('沙发', '电视', '钢琴', '篮球框', '二十一点', '老虎机'),
    ('桌子', '桌间隔板', '灯', '壁挂灯', '地毯', '盆栽', '雕像', '墙面横幅',
     '舞台', '蓝色迪斯科灯', '绿色迪斯科灯', '黄色迪斯科灯', '骷髅灯', '悬挂骷髅'),
)
_ITEM_ORDER = {name: (group, family) for group, names in enumerate(_ITEM_GROUPS)
               for family, name in enumerate(names)}


def item_sort_key(item_id, definition=None):
    name = USER_ITEM_NAME.get(item_id, '')
    group, family = _ITEM_ORDER.get(name, (len(_ITEM_GROUPS), 0))
    tier = (definition or {}).get('tier', ITEM_TIERS.get(item_id, 1))
    if not isinstance(tier, int) or isinstance(tier, bool):
        tier = 1
    return group, family, name, tier, item_id


def item_label(item_id, definition=None, fallback=None):
    name = USER_ITEM_NAME.get(item_id, fallback or f"未知物品({item_id})")
    tier = (definition or {}).get('tier', ITEM_TIERS.get(item_id))
    # Match ItemData.GetItemName: tier 1 has no suffix.
    if isinstance(tier, int) and not isinstance(tier, bool) and tier > 1:
        return f"{name} Lv {tier}"
    return name
