# -*- coding: utf-8 -*-
# =====================================================================
# Copyright (C) 2026 com-in
# 项目仓库: https://github.com/com-in/SCS-Saves-Editor
# 本程序依照 GNU 通用公共许可证 v3（或更高版本）发布。
# 严禁删除或遮蔽本版权声明；任何二次发布/修改/再分发必须遵守 GPLv3
# 并保留原作者署名。任何未经授权移除署名、抄袭、窜改归属的行为均属侵权。
# 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9（仅为版权署名追踪标识，无任何功能）
# =====================================================================
# 欢迎页/说明：本模块为 main.py 的「新增解包项」扩展混入类。
# 根据游戏解包源码(F:\GameUnpack)中可改存档即生效的 ES3 键，提供定制化入口：
#   Progress / EasterEgg / NpcPurchase / Mayor / NpcRoleFound / Interior /
#   BodyGuard / Tutorial / ScheduleCall / GameStats / Dirt(高风险)。
# 全部复用 main.py 的 _build_list_editor / es3_get / es3_set 基础设施。
import copy
import json
from PySide6.QtCore import Qt, QSignalBlocker
from _save_support import integer_list
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QWidget, QScrollArea, QFrame, QGridLayout,
    QComboBox, QVBoxLayout, QHBoxLayout, QMessageBox,
)
from _role_data import ROLE_NAME
# 统一 UI 规范常量（与 main.py 保持一致）
PAGE_MARGIN = 16
SECTION_SPACING = 12
TABLE_FIXED_HEIGHT = 220

# 店面装修 upgradeName 英文 -> 中文（依据游戏本地化语义整理；仅用于显示，保存仍写英文原值）
INTERIOR_CN = {
    "Wall Concrete": "混凝土墙", "Wall White": "白色墙面", "Wall Blue": "蓝色墙漆",
    "Wall Stripe": "条纹墙面", "Wall Stripe 2": "条纹墙面2", "Wall Luxury": "奢华墙面",
    "Wall Luxury 2": "奢华墙面2", "Wall Luxury 3": "奢华墙面3",
    "Floor Concrete": "混凝土地面", "Floor Carpet": "地毯", "Floor Carpet 2": "地毯2",
    "Floor Carpet 3": "地毯3", "Floor Marble": "大理石地面", "Floor Marble 2": "大理石地面2",
    "Floor Marble 3": "大理石地面3", "Floor Luxury": "奢华地面", "Floor Luxury 2": "奢华地面2",
    "Room Wall Default": "卧室墙面·默认", "Room Wall White": "卧室墙面·白色",
    "Room Wall Blue": "卧室墙面·蓝色", "Room Wall Stripe": "卧室墙面·条纹",
    "Room Wall Stripe 2": "卧室墙面·条纹2", "Room Wall Luxury": "卧室墙面·奢华",
    "Room Wall Luxury 2": "卧室墙面·奢华2", "Room Wall Luxury 3": "卧室墙面·奢华3",
    "Room Floor Concrete": "卧室地面·混凝土", "Room Floor Carpet": "卧室地面·地毯",
    "Room Floor Carpet 2": "卧室地面·地毯2", "Room Floor Carpet 3": "卧室地面·地毯3",
    "Room Floor Marble": "卧室地面·大理石", "Room Floor Marble 2": "卧室地面·大理石2",
    "Room Floor Marble 3": "卧室地面·大理石3", "Room Floor Luxury": "卧室地面·奢华",
    "Room Floor Luxury 2": "卧室地面·奢华2",
    "Room Table Folding": "折叠桌", "Room Table Metal Table": "金属桌",
    "Room Table Wooden Table": "木制桌", "Room Table Office Table": "办公桌",
    "Room Bed Rag": "破烂的床", "Room Bed Clean": "干净床铺",
    "Room Bed Luxury": "奢华大床", "Room Bed Cash": "金钱之床",
}
# 成就 statID(AchievementID 枚举下标) -> 中文描述；仅用于显示，保存仍写原始枚举下标
GAMESTATS_CN = {0: "总金钱收入", 1: "驯服NPC数", 2: "死亡工人数", 3: "赌博收益"}


def _section(lay, title):
    """在给定布局内追加一个小节标题。"""
    t = QLabel(title)
    t.setObjectName("CardTitle")
    lay.addWidget(t)


class ExtraPagesMixin:
    """新增存档修改项：成长/采购/市政/装修/其他数据。"""

    # ==================== 各新增页布局 ====================
    def _scroll_lay(self, tab):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        '''给页面套一层 QScrollArea，返回内容布局供调用方填充；超高时可上下滚动。'''
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFocusPolicy(Qt.NoFocus)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        scroll.setWidget(inner)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        outer.addWidget(scroll)
        return lay

    def build_extra_tabs(self):
        # 仅填充已在 build_ui 里注册进 self.stack 的页面布局
        self._build_extra_growth()
        self._build_extra_purchase()
        self._build_extra_municipal()
        self._build_extra_interior()
        # 其他数据已拆分为 7 个独立页面
        self._build_extra_bodyguard()
        self._build_extra_tutorial()
        self._build_extra_schedule()
        self._build_extra_gamestats()
        self._build_extra_cat()
        self._build_extra_delivery()
        self._build_extra_airport()

    def _build_extra_growth(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_growth)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "📈 成长进度", "剧情进度解锁、彩蛋激活 等成长类统计")

        _section(lay, "📖 剧情进度解锁 (Progress)")
        bar = QHBoxLayout(); bar.setSpacing(8)
        b1 = QPushButton("🎁 全部达成"); b1.clicked.connect(self._progress_all_done)
        b2 = QPushButton("♻️ 重置进度"); b2.setObjectName("Ghost")
        b2.clicked.connect(self._progress_reset)
        bar.addWidget(b1); bar.addWidget(b2); bar.addStretch(1); lay.addLayout(bar)
        self.progress_table = self._build_list_editor(lay)
        lay.addWidget(self.progress_table, 1)
        self.progress_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        self.progress_table._header_map = {
            "progressIndex": "进度索引", "curProgressToUnlock": "当前解锁进度"}
        self.progress_table._readonly_cols = ("progressIndex",)
        self._table_keys["Progress"] = self.progress_table
        h = QLabel("💡 把【当前解锁进度】拉高即可提前完成对应剧情解锁；进度索引列只读。")
        h.setObjectName("Hint"); lay.addWidget(h)

        _section(lay, "🥚 彩蛋激活 (EasterEgg)")
        bar = QHBoxLayout(); bar.setSpacing(8)
        b1 = QPushButton("🎁 全部激活"); b1.clicked.connect(self._easteregg_all)
        bar.addWidget(b1); bar.addStretch(1); lay.addLayout(bar)
        self.easteregg_table = self._build_list_editor(lay)
        lay.addWidget(self.easteregg_table, 1)
        self.easteregg_table.setMaximumHeight(230)
        self.easteregg_table._header_map = {
            "progressIndex": "彩蛋索引", "activated": "是否激活"}
        self.easteregg_table._readonly_cols = ("progressIndex",)
        self._table_keys["EasterEgg"] = self.easteregg_table
        h = QLabel("💡 勾选【是否激活】开启对应彩蛋；彩蛋索引列只读。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_purchase(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_purchase)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🛒 人口采购", "设置每次购买人数、采购间隔与自动采购开关")
        card = QFrame(); card.setObjectName("CardBox")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(14, 12, 14, 12); cv.setSpacing(10)
        tt = QLabel("🛒 人口采购 (NpcPurchase)")
        tt.setObjectName("CardTitle"); cv.addWidget(tt)
        form = QGridLayout(); form.setHorizontalSpacing(12); form.setVerticalSpacing(10)
        form.addWidget(QLabel("每次购买人数 (npcCountPerPurchase)"), 0, 0)
        e_count = QLineEdit("1"); e_count.setFixedHeight(32)
        form.addWidget(e_count, 0, 1)
        form.addWidget(QLabel("采购间隔/秒 (timeInterval)"), 1, 0)
        e_interval = QLineEdit("1"); e_interval.setFixedHeight(32)
        form.addWidget(e_interval, 1, 1)
        cb_auto = QCheckBox("✅ 自动采购 (autoPurchaseEnabled)")
        form.addWidget(cb_auto, 2, 0, 1, 2)
        cv.addLayout(form)
        self.npcp_entries = {"count": e_count, "interval": e_interval, "auto": cb_auto}
        lay.addWidget(card)
        h = QLabel("💡 提高每次购买人数可一次补充更多人口；游戏默认人数上限为 10，间隔范围为 1～360 秒。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_municipal(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_municipal)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🏛️ 市政管理", "市长驯服队列、已发现职业 等市政数据")

        _section(lay, "🏛️ 市长驯服队列 (Mayor)")
        self.mayor_table = self._build_list_editor(lay)
        lay.addWidget(self.mayor_table, 1)
        self.mayor_table.setMaximumHeight(230)
        self.mayor_table._header_map = {
            "npcId": "NPC编号", "isSpawned": "是否生成", "isTamed": "是否驯服",
            "isDead": "是否死亡", "sickValue": "疾病值", "starveValue": "饥饿值",
            "thirstValue": "口渴值", "sanityValue": "理智值", "tameProgress": "驯服进度",
            "position.x": "位置X", "position.y": "位置Y", "position.z": "位置Z",
        }
        self.mayor_table._readonly_cols = ("id", "npcData", "npcRole")
        self.mayor_table._hide_cols = ("tameProgress",)   # 暂时隐藏驯服进度列（数据仍保留）
        self._table_keys["Mayor"] = self.mayor_table
        lay.addWidget(self._build_row_ops_bar(self.mayor_table))
        h = QLabel("💡 与工人同结构(WorkNpc)。浅色/JSON 文本列可按需编辑。")
        h.setObjectName("Hint"); lay.addWidget(h)

        _section(lay, "🔍 已发现职业 (NpcRoleFound)")
        self.rolefound_table = QTableWidget(0, 1)
        self.rolefound_table.setObjectName("ListTable")
        self.rolefound_table.setHorizontalHeaderLabels(["已发现职业（灰色只读，不可改）"])
        hdr = self.rolefound_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        self.rolefound_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rolefound_table.verticalHeader().setVisible(False)
        lay.addWidget(self.rolefound_table)
        lay.addWidget(self._build_role_ops())
        h = QLabel("💡 已发现职业为灰色只读（对应关系展示，不可修改）；新增时从右侧下拉选择职业后点【➕ 新增】。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_role_ops(self):
        bar = QWidget(); h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0); h.setSpacing(8)
        lab = QLabel("新增职业："); lab.setObjectName("Muted")
        h.addWidget(lab)
        self.rolefound_new_combo = QComboBox()
        self.rolefound_new_combo.setFixedHeight(32)
        self.rolefound_new_combo.setMinimumWidth(150)
        for rid in sorted(ROLE_NAME.keys()):
            self.rolefound_new_combo.addItem(ROLE_NAME[rid], rid)
        h.addWidget(self.rolefound_new_combo)
        badd = QPushButton("➕ 新增"); badd.clicked.connect(self._rolefound_add)
        bdel = QPushButton("➖ 删除选中"); bdel.setObjectName("Ghost")
        bdel.clicked.connect(lambda: self._list_del_row(self.rolefound_table))
        h.addWidget(badd); h.addWidget(bdel); h.addStretch(1)
        return bar

    def _rolefound_add(self):
        t = self.rolefound_table
        rid = int(self.rolefound_new_combo.currentData())
        # 已存在则提示，不重复添加
        for rr in range(t.rowCount()):
            cell = t.item(rr, 0)
            if cell is not None and cell.data(Qt.UserRole) == rid:
                self.set_status("该职业已发现，无需重复添加")
                return
        r = t.rowCount(); t.insertRow(r)
        self._set_rolefound_cell(r, rid)

    def _set_rolefound_cell(self, row, role_id):
        cell = QTableWidgetItem(f"{ROLE_NAME.get(role_id, '未知职业')}  ·  ID {role_id}")
        cell.setData(Qt.UserRole, role_id)
        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
        self.rolefound_table.setItem(row, 0, cell)

    def _build_extra_interior(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_interior)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🛋️ 店面装修", "店内装修解锁与地面污垢坐标管理")

        _section(lay, "🛋️ 店内装修 (Interior)")
        self.interior_table = self._build_interior_table(lay)
        lay.addWidget(self.interior_table, 1)
        self.interior_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        # 记录每行所属类型索引，供互斥与保存使用
        self._interior_row_types = []
        self.interior_table.itemChanged.connect(self._interior_mutual)
        h = QLabel("💡 勾选【是否解锁】开通装修；启用按类型分列，同类型只能同时启用一个。")
        h.setObjectName("Hint"); lay.addWidget(h)

        _section(lay, "🟤 地面污垢坐标 (Dirt)  ⚠️ 高风险")
        bar = QHBoxLayout(); bar.setSpacing(8)
        b1 = QPushButton("🧹 一键清空污垢"); b1.clicked.connect(self._dirt_clear)
        bar.addWidget(b1); bar.addStretch(1); lay.addLayout(bar)
        self.dirt_table = self._build_list_editor(lay)
        lay.addWidget(self.dirt_table, 1)
        self.dirt_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        self.dirt_table._header_map = {
            "position.x": "位置X", "position.y": "位置Y", "position.z": "位置Z",
            "rotation.x": "旋转X", "rotation.y": "旋转Y",
            "rotation.z": "旋转Z", "rotation.w": "旋转W",
        }
        self._dirt_modified = False
        self.dirt_table.model().rowsInserted.connect(lambda *a: self._mark_dirt_modified())
        self.dirt_table.model().rowsRemoved.connect(lambda *a: self._mark_dirt_modified())
        self.dirt_table.itemChanged.connect(self._mark_dirt_modified)
        lay.addWidget(self._build_row_ops_bar(self.dirt_table))
        h = QLabel("污垢为游戏生成的坐标列表。清空操作会移除这些记录；点击保存后写入文件。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _mark_dirt_modified(self):
        self._dirt_modified = True

    def _dirt_clear(self):
        self._list_load(self.dirt_table, [])
        self._dirt_modified = True
        self.set_status("已清空污垢，点击保存后写入存档")

    def _build_extra_data(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        # 已拆分：BodyGuard/Tutorial/ScheduleCall/GameStats/Cat/DeliveryLocation/AirportNpc
        # 各自独立页面（见下方 7 个 _build_extra_* 方法）
        pass

    def _build_extra_bodyguard(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_bodyguard)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🛡️ 保镖状态", "保镖站位槽位与生命值管理")
        _section(lay, "🛡️ 保镖状态 (BodyGuard)")
        self.bodyguard_table = QTableWidget(0, 2)
        self.bodyguard_table.setObjectName("ListTable")
        self.bodyguard_table.setHorizontalHeaderLabels(
            ["槽位 slotIndex", "生命值 healthNormalized"])
        hdr = self.bodyguard_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        self.bodyguard_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.bodyguard_table.verticalHeader().setVisible(False)
        self.bodyguard_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        bar = QWidget(); bh = QHBoxLayout(bar)
        bh.setContentsMargins(0, 0, 0, 0); bh.setSpacing(8)
        badd = QPushButton("➕ 新增槽位"); badd.clicked.connect(self._bodyguard_add)
        bdel = QPushButton("➖ 删除选中"); bdel.setObjectName("Ghost")
        bdel.clicked.connect(lambda: self._list_del_row(self.bodyguard_table))
        bh.addWidget(badd); bh.addWidget(bdel); bh.addStretch(1)
        lay.addWidget(self.bodyguard_table)
        lay.addWidget(bar)
        h = QLabel("💡 槽位=保镖站位索引；生命值取值 0~1。可增删保镖槽位。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_tutorial(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_tutorial)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🎓 教程标记", "各教程是否已触发解锁（分行勾选）")
        _section(lay, "🎓 教程标记 (Tutorial)")
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); box = QGridLayout(inner)
        box.setContentsMargins(6, 6, 6, 6); box.setSpacing(12)
        scroll.setWidget(inner); scroll.setMinimumHeight(160)
        lay.addWidget(scroll, 1)
        self._h_tutorial = {"widgets": [], "is_bool": True, "prefix": "教程", "box": box}
        h = QLabel("💡 每个教程是否已触发（勾选=已解锁），自动分行排列。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_schedule(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_schedule)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "📞 来电队列", "待呼来电的 NPC 编号队列")
        _section(lay, "📞 待呼来电网表 (ScheduleCall)")
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); box = QGridLayout(inner)
        box.setContentsMargins(6, 6, 6, 6); box.setSpacing(12)
        scroll.setWidget(inner); scroll.setMinimumHeight(160)
        lay.addWidget(scroll, 1)
        self._h_schedule = {"widgets": [], "is_bool": False, "prefix": "来电", "box": box}
        h = QLabel("💡 即将打来的电话队列，自动分行排列，每个元素一个 NPC 编号。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_gamestats(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_gamestats)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🏆 成就统计", "各成就/统计项累计数值")
        _section(lay, "🏆 成就统计 (GameStats)")
        self.gamestats_table = self._build_list_editor(lay)
        lay.addWidget(self.gamestats_table, 1)
        self.gamestats_table.setMaximumHeight(230)
        self.gamestats_table._header_map = {
            "statID": "统计ID", "value": "累计数值"}
        self.gamestats_table._readonly_cols = ("statID",)
        self.gamestats_table._display_cn = {"statID": GAMESTATS_CN}
        self._table_keys["GameStats"] = self.gamestats_table
        h = QLabel("💡 各成就/统计的累计值，可直接修改数值；统计ID只读。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_cat(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_cat)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🐱 宠物猫", "已领养猫、猫ID列表与喂养天数")
        _section(lay, "🐱 宠物猫 (Cat)")
        row1 = QWidget(); rl1 = QHBoxLayout(row1)
        rl1.setContentsMargins(0, 0, 0, 0); rl1.setSpacing(8)
        rl1.addWidget(QLabel("已领养猫索引 (adoptedCatIndex, -1=未领养)"))
        e_adopt = QLineEdit("-1"); e_adopt.setFixedHeight(32)
        rl1.addWidget(e_adopt); rl1.addStretch(1)
        lay.addWidget(row1)
        row2 = QWidget(); rl2 = QHBoxLayout(row2)
        rl2.setContentsMargins(0, 0, 0, 0); rl2.setSpacing(8)
        rl2.addWidget(QLabel("已有猫ID (catIndices)"))
        e_indices = QLineEdit(""); e_indices.setFixedHeight(32)
        rl2.addWidget(e_indices, 1)
        lay.addWidget(row2)
        row3 = QWidget(); rl3 = QHBoxLayout(row3)
        rl3.setContentsMargins(0, 0, 0, 0); rl3.setSpacing(8)
        rl3.addWidget(QLabel("喂养连续天数 (feedStreaks)"))
        e_feed = QLineEdit(""); e_feed.setFixedHeight(32)
        rl3.addWidget(e_feed, 1)
        lay.addWidget(row3)
        self.cat_adopted = e_adopt
        self.cat_indices_input = e_indices
        self.cat_feed_input = e_feed
        h = QLabel("💡 猫ID与喂养天数均为逗号分隔的整数列表，两者按顺序一一对应；留空将写回空列表 []。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_delivery(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_delivery)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🚚 配送点", "物资配送落点设置")
        _section(lay, "🚚 配送点 (DeliveryLocation)")
        bar = QWidget(); bh2 = QHBoxLayout(bar)
        bh2.setContentsMargins(0, 0, 0, 0); bh2.setSpacing(8)
        bh2.addWidget(QLabel("配送落点 (0=前门 Frontdoor，1=后院 Backyard)"))
        combo = QComboBox()
        combo.addItem("0 - 前门 (Frontdoor)")
        combo.addItem("1 - 后院 (Backyard)")
        combo.setFixedHeight(32)
        bh2.addWidget(combo); bh2.addStretch(1)
        lay.addWidget(bar)
        self.delivery_combo = combo
        h = QLabel("💡 选择配送点落位置；保存时写回整数 0/1。")
        h.setObjectName("Hint"); lay.addWidget(h)
        lay.addStretch(1)

    def _build_extra_airport(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        lay = self._scroll_lay(self.tab_airport)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "✈️ 机场队列", "机场等待航班批次与成员职业")
        _section(lay, "✈️ 机场等待队列 (AirportNpc)")
        self.airport_table = QTableWidget(0, 2)
        self.airport_table.setObjectName("ListTable")
        self.airport_table.setHorizontalHeaderLabels(["批次", "完整 NPC 数据（JSON 数组）"])
        ah = self.airport_table.horizontalHeader()
        ah.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        ah.setSectionResizeMode(1, QHeaderView.Stretch)
        self.airport_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.airport_table.verticalHeader().setVisible(False)
        self.airport_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        abar = QWidget(); abh = QHBoxLayout(abar)
        abh.setContentsMargins(0, 0, 0, 0); abh.setSpacing(8)
        aadd = QPushButton("➕ 新增一批"); aadd.clicked.connect(self._airport_add_batch)
        adel = QPushButton("➖ 删除选中批"); adel.setObjectName("Ghost")
        adel.clicked.connect(self._airport_del_batch)
        aclear = QPushButton("✈️ 一键清空队列"); aclear.setObjectName("Ghost")
        aclear.clicked.connect(self._airport_clear)
        abh.addWidget(aadd); abh.addWidget(adel); abh.addWidget(aclear); abh.addStretch(1)
        lay.addWidget(self.airport_table)
        lay.addWidget(abar)
        self.airport_widgets = {"add": aadd, "del": adel, "clear": aclear}
        ahint = QLabel("一行代表一个航班批次。游戏保存完整 NPC 对象（含职业、能力等），"
                       "请保留对象字段；清空一批请填 []。职业名称可在单元格提示中查看。")
        ahint.setWordWrap(True)
        ahint.setObjectName("Hint"); lay.addWidget(ahint)
        lay.addStretch(1)

    def _bodyguard_add(self):
        t = self.bodyguard_table
        used = {self._to_int(t.item(r, 0).text()) for r in range(t.rowCount()) if t.item(r, 0)}
        slot = next(i for i in range(len(used) + 1) if i not in used)
        t.insertRow(t.rowCount())
        n = t.rowCount() - 1
        t.setItem(n, 0, QTableWidgetItem(str(slot)))
        t.setItem(n, 1, QTableWidgetItem("1"))

    # ==================== 机场等待队列 (AirportNpc) ====================
    def _airport_add_batch(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.airport_table
        r = t.rowCount(); t.insertRow(r)
        it = QTableWidgetItem(str(r))
        it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        t.setItem(r, 0, it)
        t.setItem(r, 1, QTableWidgetItem("[]"))

    def _airport_del_batch(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.airport_table
        r = t.currentRow()
        if r < 0:
            self.set_status("请先选中一个批次再删除")
            return
        t.removeRow(r)
        for i in range(t.rowCount()):
            it0 = t.item(i, 0)
            if it0 is not None:
                it0.setText(str(i))

    def _airport_clear(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        self.airport_table.setRowCount(0)
        self.set_status("机场等待队列已清空，保存时写回 []")

    def _load_airport(self, val):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.airport_table
        t.setRowCount(0)
        if not isinstance(val, list):
            return
        for batch in val:
            r = t.rowCount(); t.insertRow(r)
            it = QTableWidgetItem(str(r))
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            t.setItem(r, 0, it)
            cell = QTableWidgetItem(json.dumps(batch, ensure_ascii=False))
            roles = [ROLE_NAME.get(m.get('npcRoleId'), str(m.get('npcRoleId')))
                     for m in batch if isinstance(m, dict)] if isinstance(batch, list) else []
            cell.setToolTip(f"{len(roles)} 位 NPC：" + '、'.join(roles))
            t.setItem(r, 1, cell)

    def _airport_save(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.airport_table
        out = []
        for r in range(t.rowCount()):
            it = t.item(r, 1)
            txt = it.text() if it is not None else ""
            try:
                batch = json.loads(txt)
            except ValueError as exc:
                raise ValueError(f"机场队列第 {r + 1} 批 JSON 无效：{exc}") from exc
            out.append(batch)
        return out

    # ==================== 加载到界面 ====================
    # ==================== 店内装修专用表 ====================
    INTERIOR_TYPE_COLS = ("外墙", "地板", "卧室墙", "卧室地板", "卧室桌", "床")

    def _interior_type_index(self, name):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        n = str(name or "")
        if n.startswith("Room Wall"):
            return 2
        if n.startswith("Room Floor"):
            return 3
        if n.startswith("Room Table"):
            return 4
        if n.startswith("Room Bed"):
            return 5
        if n.startswith("Wall"):
            return 0
        return 1  # Floor

    def _build_interior_table(self, lay):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        table = QTableWidget(0, 2 + len(self.INTERIOR_TYPE_COLS))
        table.setObjectName("InteriorTable")
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        table.setHorizontalHeaderLabels(
            ["装修名称", "是否解锁"] + list(self.INTERIOR_TYPE_COLS))
        hdr.resizeSection(0, 140)
        for _c in range(1, table.columnCount()):
            hdr.resizeSection(_c, 72)
        if hasattr(lay, "addWidget"):
            lay.addWidget(table, 1)
        return table

    def _interior_load(self, items):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.interior_table
        blocker = QSignalBlocker(t)
        t.setRowCount(0)
        self._interior_row_types = []
        if not isinstance(items, list):
            return
        for it in items:
            if not isinstance(it, dict):
                continue
            name = it.get("upgradeName") or ""
            unlocked = bool(it.get("unlocked", False))
            selected = bool(it.get("selected", False))
            typ = self._interior_type_index(name)
            r = t.rowCount(); t.insertRow(r)
            self._interior_row_types.append(typ)
            # 名称(只读，显示中文，保留原文)
            it0 = QTableWidgetItem(INTERIOR_CN.get(str(name), str(name)))
            it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            it0.setData(Qt.UserRole, name)
            it0.setData(Qt.UserRole + 1, json.dumps(it, ensure_ascii=False, allow_nan=False))
            t.setItem(r, 0, it0)
            # 是否解锁(可编辑勾选)
            it1 = self._new_bool_cell(unlocked)
            t.setItem(r, 1, it1)
            # 类型分列：选中项落在所属类型列，其余类型列禁用留空
            for c in range(2, 2 + len(self.INTERIOR_TYPE_COLS)):
                col_typ = c - 2
                if col_typ == typ:
                    t.setItem(r, c, self._new_bool_cell(selected))
                else:
                    empty = QTableWidgetItem("")
                    empty.setFlags(empty.flags() & ~Qt.ItemIsEnabled)
                    t.setItem(r, c, empty)
        t.resizeRowsToContents()

    def _interior_mutual(self, item):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        # 同类型互斥：勾选某行启用列时，自动取消同类其它行的该列
        if item is None or item.column() < 2:
            return
        if item.checkState() != Qt.Checked:
            return
        r = item.row()
        if not (0 <= r < len(self._interior_row_types)):
            return
        c = item.column()
        typ = self._interior_row_types[r]
        col_typ = c - 2
        if col_typ != typ:
            return
        t = self.interior_table
        t.blockSignals(True)
        try:
            t.item(r, 1).setCheckState(Qt.Checked)
            for rr, rt in enumerate(self._interior_row_types):
                if rt == typ and rr != r:
                    cell = t.item(rr, c)
                    if cell is not None and cell.checkState() == Qt.Checked:
                        cell.setCheckState(Qt.Unchecked)
        finally:
            t.blockSignals(False)

    def _interior_save(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.interior_table
        out = []
        for r in range(t.rowCount()):
            it0 = t.item(r, 0)
            if it0 is None:
                continue
            raw = it0.data(Qt.UserRole)
            name = raw if raw is not None else it0.text()
            unlocked = False
            it1 = t.item(r, 1)
            if it1 is not None:
                unlocked = (it1.checkState() == Qt.Checked)
            typ = self._interior_row_types[r] if r < len(self._interior_row_types) else self._interior_type_index(name)
            selected = False
            sc = t.item(r, 2 + typ)
            if sc is not None:
                selected = (sc.checkState() == Qt.Checked)
            original = json.loads(it0.data(Qt.UserRole + 1) or '{}')
            original.update({"upgradeName": str(name),
                             "unlocked": bool(unlocked), "selected": bool(selected)})
            out.append(original)
        return out

    def load_extra_ui(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        self._list_load(self.progress_table, self.es3_get("Progress"))
        self._list_load(self.easteregg_table, self.es3_get("EasterEgg"))
        self._list_load(self.mayor_table, self.es3_get("Mayor"))
        self._load_rolefound(self.es3_get("NpcRoleFound"))
        self._interior_load(self.es3_get("Interior"))
        self._list_load(self.dirt_table, self.es3_get("Dirt"))
        self._load_bodyguard(self.es3_get("BodyGuard"))
        self._load_hlist(self._h_tutorial, self.es3_get("Tutorial"))
        self._load_hlist(self._h_schedule, self.es3_get("ScheduleCall"))
        self._list_load(self.gamestats_table, self.es3_get("GameStats"))
        npcp = self.es3_get("NpcPurchase")
        self.npcp_entries["count"].setText("1")
        self.npcp_entries["interval"].setText("1")
        self.npcp_entries["auto"].setChecked(False)
        for widget in self.npcp_entries.values():
            widget.setEnabled(isinstance(npcp, dict))
        if isinstance(npcp, dict):
            self.npcp_entries["count"].setText(str(npcp.get("npcCountPerPurchase", 1)))
            self.npcp_entries["interval"].setText(str(npcp.get("timeInterval", 1)))
            self.npcp_entries["auto"].setChecked(
                bool(npcp.get("autoPurchaseEnabled", False)))
        cat = self.es3_get("Cat")
        self.cat_adopted.setText("-1")
        self.cat_indices_input.clear()
        self.cat_feed_input.clear()
        for widget in (self.cat_adopted, self.cat_indices_input, self.cat_feed_input):
            widget.setEnabled(isinstance(cat, dict))
        if isinstance(cat, dict):
            self.cat_adopted.setText(str(cat.get("adoptedCatIndex", -1)))
            ci = cat.get("catIndices")
            if isinstance(ci, list):
                self.cat_indices_input.setText(",".join(str(x) for x in ci))
            fs = cat.get("feedStreaks")
            if isinstance(fs, list):
                self.cat_feed_input.setText(",".join(str(x) for x in fs))
        dl = self.es3_get("DeliveryLocation")
        try:
            dlv = int(dl)
        except Exception:
            dlv = 0
        self.delivery_combo.setCurrentIndex(1 if dlv == 1 else 0)
        self._load_airport(self.es3_get("AirportNpc"))
        self._dirt_modified = False

    def _rolefound_combo(self, extra_ids=()):
        cb = QComboBox()
        for rid in sorted(ROLE_NAME.keys()):
            cb.addItem(ROLE_NAME[rid], rid)
        # 存档中 ROLE_NAME 未覆盖的 id 也保留（显示为未知职业），避免保存时静默丢失
        for rid in sorted(set(int(x) for x in extra_ids) - set(ROLE_NAME.keys())):
            cb.addItem(f"未知职业({rid})", rid)
        return cb

    def _load_rolefound(self, ids):
        t = self.rolefound_table
        t.setRowCount(0)
        if not isinstance(ids, list):
            return
        for i in ids:
            try:
                rid = int(i)
            except Exception:
                rid = -1
            r = t.rowCount(); t.insertRow(r)
            self._set_rolefound_cell(r, rid)

    def _load_bodyguard(self, d):
        t = self.bodyguard_table
        t.setRowCount(0)
        if not isinstance(d, dict):
            return
        guards = d.get("guards")
        if not isinstance(guards, list):
            return
        for g in guards:
            if not isinstance(g, dict):
                continue
            r = t.rowCount(); t.insertRow(r)
            cell = QTableWidgetItem(str(g.get("slotIndex", 0)))
            cell.setData(Qt.UserRole, json.dumps(g, ensure_ascii=False, allow_nan=False))
            t.setItem(r, 0, cell)
            t.setItem(r, 1, QTableWidgetItem(str(g.get("healthNormalized", 1))))

    # ==================== 保存到存档 ====================
    def save_extra_to_data(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        # 定制表单/高风险项：NpcPurchase / BodyGuard / NpcRoleFound / Dirt
        # （其余新键：Progress/EasterEgg/Mayor/Interior/Tutorial/ScheduleCall/GameStats
        #   已通过 _table_keys 在 merge_json_tabs 中统一保存）
        d = self.es3_get("NpcPurchase")
        if isinstance(d, dict):
            d["npcCountPerPurchase"] = self._to_int(self.npcp_entries["count"].text())
            d["timeInterval"] = self._to_float(self.npcp_entries["interval"].text())
            d["autoPurchaseEnabled"] = self.npcp_entries["auto"].isChecked()
            self.es3_set("NpcPurchase", d)
        self._save_bodyguard()
        self._save_rolefound()
        self._save_dirt()
        self.es3_set("Interior", self._interior_save())
        self.es3_set("Tutorial", self._save_hlist(self._h_tutorial))
        self.es3_set("ScheduleCall", self._save_hlist(self._h_schedule))
        # 宠物猫 (Cat)：取回原 dict 就近修改，保持其它字段不变
        cat = self.es3_get("Cat")
        if isinstance(cat, dict):
            cat["adoptedCatIndex"] = self._to_int(self.cat_adopted.text())
            cat["catIndices"] = self._csv_int_list(self.cat_indices_input.text())
            cat["feedStreaks"] = self._csv_int_list(self.cat_feed_input.text())
            self.es3_set("Cat", cat)
        # 配送点 (DeliveryLocation)：直接回写整数 0/1
        self.es3_set("DeliveryLocation", self.delivery_combo.currentIndex())
        # 机场等待队列 (AirportNpc)：仅当存档原有关键时才回写，避免凭空新增键污染
        if self.es3_get("AirportNpc") is not None:
            self.es3_set("AirportNpc", self._airport_save())

    def _save_bodyguard(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.bodyguard_table
        guards = []
        for r in range(t.rowCount()):
            it0 = t.item(r, 0); it1 = t.item(r, 1)
            guard = json.loads(it0.data(Qt.UserRole) or '{}') if it0 else {}
            guard.update({
                "slotIndex": self._to_int(it0.text() if it0 is not None else 0),
                "healthNormalized": self._to_float(it1.text() if it1 is not None else 1),
            })
            guards.append(guard)
        d = self.es3_get("BodyGuard")
        if isinstance(d, dict):
            d["guards"] = guards
            self.es3_set("BodyGuard", d)

    def _save_rolefound(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        t = self.rolefound_table
        out = []
        for r in range(t.rowCount()):
            cell = t.item(r, 0)
            if cell is None:
                continue
            out.append(cell.data(Qt.UserRole))
        self.es3_set("NpcRoleFound", out)

    def _save_dirt(self):
        if self.es3_get("Dirt") is not None:
            self.es3_set("Dirt", self._list_save(self.dirt_table))


    @staticmethod
    def _csv_int_list(txt):
        return integer_list(txt)


    # ==================== 横向标量列表 ====================
    def _load_hlist(self, cfg, items):
        box = cfg["box"]
        def clear_layout(layout):
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    clear_layout(item.layout())
        clear_layout(box)
        cfg["widgets"] = []
        if not isinstance(items, list):
            items = []
        for i, value in enumerate(items):
            if cfg["is_bool"]:
                widget = QCheckBox(f"{cfg['prefix']} {i + 1}")
                widget.setChecked(bool(value))
            else:
                widget = QLineEdit(str(value))
                widget.setToolTip(f"{cfg['prefix']} {i + 1}")
                widget.setFixedWidth(100)
            box.addWidget(widget, i // 5, i % 5)
            cfg["widgets"].append(widget)


    def _save_hlist(self, cfg):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        out = []
        if cfg.get("is_bool"):
            for w in cfg["widgets"]:
                out.append(w.isChecked())
        else:
            for w in cfg["widgets"]:
                out.append(self._to_int(w.text()))
        return out

    # ==================== 一键操作 ====================
    def _progress_all_done(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        its = self.es3_get("Progress")
        if not isinstance(its, list):
            return
        for d in its:
            if isinstance(d, dict):
                d["curProgressToUnlock"] = max(int(d.get("curProgressToUnlock", 0)), 999999)
        self._list_load(self.progress_table, its)
        self.set_status("已一键达成全部剧情进度")

    def _progress_reset(self):
        its = self.es3_get("Progress")
        if not isinstance(its, list):
            return
        for d in its:
            if isinstance(d, dict):
                d["curProgressToUnlock"] = 0
        self._list_load(self.progress_table, its)
        self.set_status("已重置剧情进度")

    def _easteregg_all(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        its = self.es3_get("EasterEgg")
        if not isinstance(its, list):
            return
        for d in its:
            if isinstance(d, dict):
                d["activated"] = True
        self._list_load(self.easteregg_table, its)
        self.set_status("已全部激活彩蛋")
