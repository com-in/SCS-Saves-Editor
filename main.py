#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诈骗园区模拟器 - ES3存档修改器 (PySide6版)
功能: 安全编辑Unity ES3 JSON存档(真实ES3结构)，自动备份，防闪退
适配结构: 顶层 key -> {"__type":..., "value":...}
"""
import os
import time
import shutil
import json
import copy
import uuid
import threading
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QListWidget, QTextEdit, QPlainTextEdit,
    QPushButton, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QFrame, QStatusBar, QToolButton,
    QStackedWidget, QListWidgetItem, QSizePolicy, QComboBox, QDialog, QSpinBox,
)
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap
from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve, QTimer, QSize, QThread, Signal, QSettings

from _memscan import MemScanner, find_game_process

# ==================== 主题配置 ====================
# 默认亮色
BG_COLOR = "#f5f6fa"
CARD_BG = "#f5f6fa"      # 与程序背景一致，层次靠边框体现
ENTRY_BG = "#f5f6fa"      # 与程序背景一致
TEXT_COLOR = "#24273a"
TEXT_SECOND = "#5b6080"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
SUCCESS = "#16a34a"
WARNING = "#b45309"
DANGER = "#dc2626"
BORDER = "#c9cede"   # 边框略加深，统一浅灰下仍清晰可见

# 亮色主题
LIGHT_THEME = {
    "BG_COLOR": BG_COLOR,
    "CARD_BG": CARD_BG,
    "ENTRY_BG": ENTRY_BG,
    "TEXT_COLOR": TEXT_COLOR,
    "TEXT_SECOND": TEXT_SECOND,
    "ACCENT": ACCENT,
    "ACCENT_HOVER": ACCENT_HOVER,
    "SUCCESS": SUCCESS,
    "WARNING": WARNING,
    "DANGER": DANGER,
    "BORDER": BORDER,
}

# 暗色主题（深色下编辑框背景与程序背景保持一致）
DARK_THEME = {
    "BG_COLOR": "#1e1e2e",
    "CARD_BG": "#1e1e2e",
    "ENTRY_BG": "#1e1e2e",
    "TEXT_COLOR": "#cdd6f4",
    "TEXT_SECOND": "#a6adc8",
    "ACCENT": "#89b4fa",
    "ACCENT_HOVER": "#b4befe",
    "SUCCESS": "#a6e3a1",
    "WARNING": "#f9e2af",
    "DANGER": "#f38ba8",
    "BORDER": "#313244",
}

def build_qss(theme):
    """根据主题字典生成完整 QSS，避免各处内联散落样式"""
    BG = theme["BG_COLOR"]; CARD = theme["CARD_BG"]; ENTRY = theme["ENTRY_BG"]
    T = theme["TEXT_COLOR"]; TS = theme["TEXT_SECOND"]
    ACC = theme["ACCENT"]; ACH = theme["ACCENT_HOVER"]
    S = theme["SUCCESS"]; W = theme["WARNING"]; D = theme["DANGER"]; BD = theme["BORDER"]
    return f"""
* {{ font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; }}
QMainWindow {{ background: {BG}; }}
QWidget {{ background: {BG}; color: {T}; font-size: 13px; }}
QLabel {{ background: transparent; }}
QLabel#CardTitle {{ color: {T}; font-weight: bold; font-size: 14px; }}
QLabel#Hint {{ color: {W}; font-size: 12px; }}
QLabel#Muted {{ color: {TS}; font-size: 12px; }}
QLabel#SideTitle {{ color: {T}; font-weight: bold; font-size: 15px; }}

QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {ENTRY}; color: {T};
    border: 1px solid {BD}; border-radius: 6px;
    padding: 6px 8px; selection-background-color: {ACC};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {ACC}; }}

QPushButton {{
    background: {ACC}; color: {BG}; border: none;
    border-radius: 6px; padding: 8px 16px; font-weight: bold;
}}
QPushButton:hover {{ background: {ACH}; }}
QPushButton:pressed {{ background: {ACC}; }}
QPushButton:disabled {{ background: {BD}; color: {TS}; }}
QPushButton#Danger {{ background: {D}; }}
QPushButton#Ghost {{ background: {CARD}; color: {T}; border: 1px solid {BD}; }}
QPushButton#Ghost:hover {{ border: 1px solid {ACC}; }}
QToolButton#Ghost {{ background: {CARD}; color: {T}; border: 1px solid {BD}; border-radius: 6px; }}
QToolButton#Ghost:hover {{ border: 1px solid {ACC}; background: {ENTRY}; }}
QToolButton#NavFold {{ background: {CARD}; color: {TS}; border: 1px solid {BD}; border-radius: 8px; padding: 0 10px; text-align: left; }}
QToolButton#NavFold:hover {{ border: 1px solid {ACC}; color: {T}; background: {ENTRY}; }}

QListWidget {{
    background: {ENTRY}; border: 1px solid {BD}; border-radius: 6px;
    padding: 4px; outline: 0;
}}
QListWidget::item {{ padding: 8px 10px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {ACC}; color: {BG}; }}
QListWidget::item:hover:!selected {{ background: {CARD}; }}

QListWidget#Nav {{
    background: {CARD}; border: 1px solid {BD}; border-radius: 8px;
    padding: 6px; outline: 0; color: {T}; font-size: 13px;
}}
QListWidget#Nav::item {{
    padding: 10px 12px; border-radius: 6px; margin: 2px 0;
}}
QListWidget#Nav::item:hover {{ background: {ENTRY}; }}
QListWidget#Nav::item:selected {{
    background: {ACC}; color: {BG}; font-weight: bold;
}}

QFrame#CardBox {{ background: {CARD}; border: 1px solid {BD}; border-radius: 8px; }}
QFrame#FieldBox {{ background: {CARD}; border: 1px solid {BD}; border-radius: 6px; }}

QTableWidget {{
    background: {ENTRY}; border: 1px solid {BD}; border-radius: 6px;
    gridline-color: {BD}; selection-background-color: {ACC}; selection-color: {BG};
}}
QHeaderView::section {{
    background: {CARD}; color: {T}; padding: 6px; border: none;
    border-bottom: 1px solid {BD}; font-weight: bold;
}}
QCheckBox {{ spacing: 8px; background: transparent; color: {T}; }}
QCheckBox#DeadCheck {{ color: {D}; }}
QCheckBox::indicator {{ width: 18px; height: 18px; }}
QScrollBar:vertical {{ background: {BG}; width: 12px; }}
QScrollBar::handle:vertical {{ background: {BD}; border-radius: 6px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {BD}; width: 2px; }}
QStatusBar {{ background: {BG}; color: {TS}; border-top: 1px solid {BD}; }}
QStackedWidget {{ background: {BG}; border: none; }}
"""

def _lerp_color(c1, c2, t):
    """线性插值两个 hex 颜色"""
    a = QColor(c1)
    b = QColor(c2)
    r = int(a.red() + (b.red() - a.red()) * t)
    g = int(a.green() + (b.green() - a.green()) * t)
    bl = int(a.blue() + (b.blue() - a.blue()) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"

def _interp_theme(t1, t2, t):
    """插值两个主题字典，返回新主题字典"""
    return {k: _lerp_color(t1[k], t2[k], t) for k in t1}

def _svg_icon(svg_bytes, size=18):
    """从 SVG 字符串创建 icon"""
    icon = QIcon()
    pm = QPixmap()
    pm.loadFromData(svg_bytes)
    icon.addPixmap(pm)
    icon.addPixmap(pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    return icon

def _chevron_icon(direction="left", color="#5b6080"):
    """生成圆滑的 chevron 折叠图标（direction: left/right）"""
    if direction == "left":
        path = "M14 6 L8 12 L14 18"
    else:
        path = "M10 6 L16 12 L10 18"
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" '
           f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
           f'<path d="{path}"/></svg>').encode("utf-8")
    return _svg_icon(svg)

# 当前启用的主题（对象在实例中管理，这里用于全局 QSS 默认）
CURRENT_THEME = "light"


# ==================== 工具函数 ====================
def safe_float(val, default=0.0):
    try:
        return float(val)
    except Exception:
        return default

def safe_int(val, default=0):
    try:
        return int(float(val))
    except Exception:
        return default

def safe_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes", "on")
    return bool(val)


# ==================== 升级项配置（按内部英文名匹配） ====================
# 存档 Upgrade 数组即 [{name, level}, ...]，name 是游戏内部英文名。
# 为避免"升级丢失"，绝不改 name，只对映射到的项按 name 作为唯一标识：
#   中文显示名, 最高等级上限。未在映射里的项（如 Upgrade / Tame Speed）一律不改动。
UPGRADE_MAP = {
    "Cleaner": ("清洁工具", 1),
    "Scam Sticker": ("诈骗广告贴纸", 5),
    "Trolley": ("手推车", 3),
    "Multigrab": ("多重抓取", 3),
    "Stamina": ("耐力", 3),
    "Hit Power": ("击倒力量", 4),
    "Electricity Capacity": ("电力容量", 6),
    "Weapon": ("武器", 4),
    "Backyard": ("后院", 4),
    "Pickup Number": ("接送数量", 4),
    "Automatic Capture Service": ("自动抓捕", 3),
    "Pee": ("尿尿", 3),
    "Brain Wash Success Chance": ("洗脑成功率", 2),
    "Level 2": ("二楼", 1),
    "Human Purchase Route": ("人口采购路线", 1),
    "RoomSize": ("房间大小", 1),
}


def _upgrade_setup(name):
    """按内部英文名返回 (中文名, 上限)；不在映射里则返回 None。"""
    return UPGRADE_MAP.get(name)


# 内存扫描：存档顶层英文键 → 中文显示名
_MEM_TOP_FIELD_CN = {
    "Currency": "货币",
    "Level": "等级",
    "Exp": "经验值",
    "Day": "天数",
    "Electricity": "电力",
    "CallData": "呼叫数据",
}


class Card(QFrame):
    """带标题的卡片容器"""
    def __init__(self, master, title):
        super().__init__(master)
        self.setObjectName("CardBox")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(14, 10, 14, 12)
        self._lay.setSpacing(6)
        lab = QLabel(title)
        lab.setObjectName("CardTitle")
        self._lay.addWidget(lab)


class _MemScanWorker(QThread):
    """后台内存扫描线程：一次读内存+多目标匹配，避免卡 UI。"""
    finished_ok = Signal(dict)   # {name:[addr,...], "_elapsed":秒}
    failed = Signal(str)

    def __init__(self, scanner, targets, regions, workers=4):
        super().__init__()
        self.scanner = scanner
        self.targets = targets      # [(name, value, vtype)]
        self.regions = regions
        self.workers = workers

    def _tick(self, _=0):
        pass

    def run(self):
        try:
            t0 = time.time()
            res = self.scanner.first_scan_multi(
                self.targets, regions=self.regions,
                workers=self.workers, progress=self._tick)
            res["_elapsed"] = time.time() - t0
            self.finished_ok.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class ES3Editor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("诈骗园区模拟器 - 存档修改器")
        self.setMinimumSize(1000, 700)

        self.data = None          # 解析后的整个 dict
        self.file_path = None

        # 主题
        self.theme = "light"
        self._action_theme = None
        self._theme_anim = None
        # 侧边栏
        self.sidebar_collapsed = False
        self._sidebar_anim = None

        # 基础数据控件引用
        self.entry_basic = {}
        # 列表表格键映射（各标签页列表表格 -> 对应顶层key）
        self._table_keys = {}
        # "其他"页当前选中键的标量输入框
        self._other_scalar_entry = None
        self._other_cur_key = None
        # 工人
        self.workers = []
        self.current_worker = None
        self.worker_entries = {}
        self.worker_check = {}
        self.cb_tamed = None
        self.cb_dead = None

        self.build_ui()
        self.log("程序已启动，请先打开 .es3 存档文件")
        # 默认全屏（窗口显示后立即最大化）
        QTimer.singleShot(0, self.showMaximized)

    # ---------- 主题切换（带过渡动画） ----------
    def _apply_theme_button_text(self):
        """按钮提示可切换到的目标主题（当前亮色则提示切暗色）"""
        if self.sidebar_collapsed:
            self._action_theme.setText("🌙" if self.theme == "light" else "☀️")
            self._action_theme.setToolTip("切换到暗色模式" if self.theme == "light" else "切换到亮色模式")
        else:
            self._action_theme.setText("🌙 暗色模式" if self.theme == "light" else "☀️ 亮色模式")

    def apply_theme(self, name, immediate=False):
        """切换暗色/亮色主题（立即生效，无过渡动画）"""
        global CURRENT_THEME
        if name == self.theme and not immediate:
            return
        dst_theme = DARK_THEME if name == "dark" else LIGHT_THEME
        self.theme = name
        CURRENT_THEME = name

        # 更新主题按钮提示文字
        if self._action_theme is not None:
            self._apply_theme_button_text()

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(dst_theme))

    def set_status(self, text):
        self.status_lbl.setText(text)

    # ==================== 界面 ====================
    def build_ui(self):
        # ========== 左右布局 ==========
        # 左栏：导航菜单（标题 + 项 + 左下设置）
        self.sidebar = QWidget()
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(10, 14, 10, 14)
        sb.setSpacing(10)
        self._sb_layout = sb

        # 顶部：主标题
        self.side_title = QLabel("💾 ES3 存档修改器")
        self.side_title.setObjectName("SideTitle")
        self.side_title.setContentsMargins(4, 0, 0, 0)
        sb.addWidget(self.side_title)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("Nav")
        self.nav_list.setWordWrap(True)
        # nav_items: (图标, 文字, key)
        self.nav_items = [
            ("📊", "基础数据", "basic"),
            ("👷", "工人", "workers"),
            ("💎", "加密货币", "crypto"),
            ("📦", "物品", "items"),
            ("🏗️", "放置物品", "placed"),
            ("⬆️", "升级", "upgrade"),
            ("🔬", "内存 BETA", "memory"),
            ("🏦", "银行还款", "debt"),
            ("📖", "剧情解锁", "story"),
            ("🎓", "教程解锁", "tutorial"),
            ("⚙️", "其他", "other"),
        ]
        self._nav_icons = [it[0] for it in self.nav_items]
        self._nav_labels = [it[1] for it in self.nav_items]
        self._nav_keys = [it[2] for it in self.nav_items]
        for icon, label, _ in self.nav_items:
            item = QListWidgetItem(f"{icon} {label}")
            self.nav_list.addItem(item)
        # 菜单内部最下面一行：折叠/展开侧边栏
        self._fold_row = len(self._nav_keys)
        self._fold_item = QListWidgetItem("◀ 折叠侧边栏")
        self.nav_list.addItem(self._fold_item)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self.on_nav_change)
        self.nav_list.itemClicked.connect(self.on_nav_item_clicked)
        sb.addWidget(self.nav_list, 1)

        # 左下角：设置（主题切换）
        self._action_theme = QPushButton("☀️ 亮色模式")
        self._action_theme.setObjectName("Ghost")
        self._action_theme.clicked.connect(
            lambda: self.apply_theme("light" if self.theme == "dark" else "dark"))
        sb.addWidget(self._action_theme)

        self.sidebar.setFixedWidth(212)

        # 右侧容器 = 上部按钮栏 + 内容栈
        right_outer = QWidget()
        rv = QVBoxLayout(right_outer)
        rv.setContentsMargins(8, 8, 8, 4)
        rv.setSpacing(6)

        # 右侧上部：文件操作按钮组
        btn_bar = QWidget()
        bh = QHBoxLayout(btn_bar)
        bh.setContentsMargins(4, 4, 4, 4)
        bh.setSpacing(8)

        btn_open = QPushButton("📂 打开存档")
        btn_find = QPushButton("🔍 查找存档")
        btn_save = QPushButton("💾 保存存档")
        btn_backup = QPushButton("📋 备份目录")
        btn_find.setObjectName("Ghost")
        btn_save.setObjectName("Ghost")
        btn_backup.setObjectName("Ghost")
        btn_open.clicked.connect(self.open_file)
        btn_find.clicked.connect(self.find_save_file)
        btn_save.clicked.connect(self.save_file)
        btn_backup.clicked.connect(self.open_backup_dir)
        self.btn_backup = btn_backup

        bh.addWidget(btn_open)
        bh.addWidget(btn_find)
        bh.addWidget(btn_save)
        bh.addWidget(btn_backup)
        bh.addStretch(1)
        rv.addWidget(btn_bar)

        # 右侧：内容栈
        self.stack = QStackedWidget()

        # 页面容器
        self.tab_basic = QWidget()
        self.tab_workers = QWidget()
        self.tab_crypto = QWidget()
        self.tab_items = QWidget()
        self.tab_placed = QWidget()
        self.tab_upgrade = QWidget()
        self.tab_memory = QWidget()
        self.tab_debt = QWidget()
        self.tab_story = QWidget()
        self.tab_tutorial = QWidget()
        self.tab_other = QWidget()

        for page in (self.tab_basic, self.tab_workers, self.tab_crypto,
                     self.tab_items, self.tab_placed, self.tab_upgrade,
                     self.tab_memory, self.tab_debt, self.tab_story,
                     self.tab_tutorial, self.tab_other):
            self.stack.addWidget(page)
        rv.addWidget(self.stack, 1)

        # 主布局：侧边栏 + 右侧（右侧拉伸填满）
        central = QWidget()
        cl = QHBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(self.sidebar)
        cl.addWidget(right_outer, 1)
        self._central_layout = cl

        self.setCentralWidget(central)

        self.build_basic_tab()
        self.build_workers_tab()
        self.build_crypto_tab()
        self.build_upgrade_tab()
        self.build_memory_tab()
        self.build_json_tab()  # 物品/放置/其他
        self.build_debt_story_tutorial_tabs()  # 银行债务/剧情解锁/教程解锁

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.status_lbl = QLabel("未加载文件")
        self.status_lbl.setObjectName("Muted")
        self.statusBar.addWidget(self.status_lbl)

        # 应用初始主题（即时，无动画）
        self.apply_theme(self.theme, immediate=True)

    def on_nav_change(self, row):
        # 折叠行不切换页面
        if row >= len(self._nav_keys):
            return
        self._last_page_row = row
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
        self._maybe_show_mem_force_read(row)

    def on_nav_item_clicked(self, item):
        # 点击菜单最下面的折叠/展开行
        if self.nav_list.row(item) == self._fold_row:
            self.toggle_sidebar()

    def _maybe_show_mem_force_read(self, row):
        """进入『内存』页首次时弹强制阅读提示（带10s倒计时）。"""
        if row != getattr(self, "_mem_nav_row", -1):
            return
        if QSettings().value("mem/dont_show_force_read", "0") == "1":
            return                                  # 用户勾选了『不再提示』
        if getattr(self, "_mem_force_read_on", False):
            return                                  # 本次会话已提示过
        self._mem_force_read_on = True
        self.show_mem_force_read_dialog()

    def show_mem_force_read_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("⚠️ 内存扫描须知")
        dlg.setModal(True)
        dlg.setMinimumWidth(540)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(18, 18, 18, 14)
        lb = QLabel(
            "请务必<b>重新进入存档</b>后再读取内存扫描，"
            "<b>不要开启新的一天</b>，否则会导致无法成功扫描到内存中的数据。<br><br>"
            "如果扫描后出现多个候选值，请<b>开启新的一天</b>让数值发生一次变化，"
            "再<b>多次重复扫描</b>（点击【下一次扫描】按钮），"
            "直到每个字段只剩 1 个地址。")
        lb.setWordWrap(True)
        lb.setStyleSheet("font-size: 13px; line-height: 150%;")
        lay.addWidget(lb)

        bot = QHBoxLayout(); bot.setSpacing(10)
        chk = QCheckBox("不再提示")
        bot.addWidget(chk)
        bot.addStretch(1)
        btn = QPushButton("知道了（10s）")
        btn.setEnabled(False)
        bot.addWidget(btn)
        lay.addLayout(bot)

        count = {"n": 10}
        timer = QTimer(dlg); timer.setInterval(1000)
        def _tick():
            count["n"] -= 1
            if count["n"] <= 0:
                timer.stop()
                btn.setText("知道了")
                btn.setEnabled(True)
            else:
                btn.setText(f"知道了（{count['n']}s）")
        timer.timeout.connect(_tick)
        timer.start()

        def _accept():
            if chk.isChecked():
                QSettings().setValue("mem/dont_show_force_read", "1")
            dlg.accept()
        btn.clicked.connect(_accept)
        dlg.exec()

    # ---------- 侧边栏折叠/展开 ----------
    def toggle_sidebar(self):
        self.sidebar_collapsed = not self.sidebar_collapsed
        if self.sidebar_collapsed:
            self.collapse_sidebar()
        else:
            self.expand_sidebar()
        # 折叠行被选中会高亮，恢复回当前页的选中
        self.nav_list.setCurrentRow(getattr(self, "_last_page_row", 0))

    def collapse_sidebar(self):
        """折叠侧边栏：仅菜单折叠为图标（宽度收窄），标题保留"""
        self.sidebar_collapsed = True
        self._fold_item.setText("▶")
        self._fold_item.setToolTip("展开侧边栏")
        self._fold_item.setTextAlignment(Qt.AlignCenter)
        self.side_title.setText(self._elide_title(58))
        for i in range(len(self._nav_keys)):
            self.nav_list.item(i).setText(self._nav_icons[i])
            self.nav_list.item(i).setTextAlignment(Qt.AlignCenter)
        self.nav_list.setWordWrap(False)
        self._apply_theme_button_text()
        self._sidebar_apply_width(90)

    def expand_sidebar(self):
        """展开侧边栏，显示图标 + 文字"""
        self.sidebar_collapsed = False
        self._fold_item.setText("◀ 折叠侧边栏")
        self._fold_item.setToolTip("折叠侧边栏")
        self._fold_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.side_title.setText("💾 ES3 存档修改器")
        for i in range(len(self._nav_keys)):
            self.nav_list.item(i).setText(f"{self._nav_icons[i]} {self._nav_labels[i]}")
            self.nav_list.item(i).setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.nav_list.setWordWrap(True)
        self._apply_theme_button_text()
        self._sidebar_apply_width(212)

    def _elide_title(self, max_width):
        """标题在窄侧栏下省略号截断，避免被撑宽"""
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.side_title.font())
        return fm.elidedText("💾 ES3 存档修改器", Qt.ElideRight, max_width)

    def _sidebar_apply_width(self, target):
        """侧边栏宽度过渡动画（完成后固定目标宽度）"""
        # 若窗口尚未布局完成，直接跳到目标宽度，避免动画起点错误
        if not self.isVisible() or self.sidebar.width() <= 0:
            self.sidebar.setFixedWidth(target)
            self._sb_layout.setContentsMargins(6 if target < 120 else 10, 14, 6 if target < 120 else 10, 14)
            return
        start = self.sidebar.width()

        def on_frame(t):
            w = int(start + (target - start) * t)
            self.sidebar.setFixedWidth(w)
            self._sb_layout.setContentsMargins(6 if w < 120 else 10, 14, 6 if w < 120 else 10, 14)

        def on_done():
            self.sidebar.setFixedWidth(target)
            self._sb_layout.setContentsMargins(6 if target < 120 else 10, 14, 6 if target < 120 else 10, 14)

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(260)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.valueChanged.connect(on_frame)
        anim.finished.connect(on_done)
        anim.start()
        self._sidebar_anim = anim

    # ---------- 基础数据 ----------
    def build_basic_tab(self):
        """真实因键: Currency/Level/Exp/Day/Electricity/ShopName/CallData/Difficulty"""
        # (ui_key, 标题, es3顶层key, 默认)
        fields = [
            ("currency", "💰 货币", "Currency", "0"),
            ("level", "⭐ 等级", "Level", "30"),
            ("exp", "✨ 经验值", "Exp", "0"),
            ("days", "📅 天数", "Day", "52"),
            ("electricity", "⚡ 电力", "Electricity", "50"),
            ("shopName", "🏪 店铺名称", "ShopName", ""),
            ("callData", "📞 呼叫数据", "CallData", "-1"),
            ("difficulty", "🌡️ 难度 (0/1/2)", "Difficulty", "1"),
        ]
        root = QWidget()
        lay = QGridLayout(root)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        for i, (key, title, es3, default) in enumerate(fields):
            row, col = divmod(i, 2)
            card = Card(root, title)
            card._lay.addWidget(self._make_value_line(key, default))
            lay.addWidget(card, row, col)

        # 💰 货币：修改时实时钳制上限，不允许超过 1e+35（与游戏上限一致）
        self.entry_basic["currency"].textChanged.connect(self._clamp_currency)

        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)
        for r in range(4):
            lay.setRowStretch(r, 1)

        hint = QLabel("提示：修改后点击顶部【保存存档】写入文件。Difficulty为游戏难度枚举(0/1/2)。")
        hint.setObjectName("Hint")
        lay.addWidget(hint, 4, 0, 1, 2)

        self.tab_basic_layout_add(root)

    def _make_value_line(self, key, default):
        """生成 当前值 + 输入框 一行"""
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        lab = QLabel("当前值")
        lab.setObjectName("Muted")
        entry = QLineEdit(default)
        entry.setAlignment(Qt.AlignRight)
        entry.setFixedHeight(34)
        h.addWidget(lab)
        h.addWidget(entry, 1)
        self.entry_basic[key] = entry
        return box

    def _clamp_currency(self, text):
        """货币上限 1e+35：用户输入超过该值时立即钳回上限（修改时限制）。"""
        try:
            v = float(text)
        except (TypeError, ValueError):
            return
        MAXC = 1e35
        if v > MAXC:
            e = self.entry_basic["currency"]
            e.blockSignals(True)
            e.setText(str(MAXC))
            e.blockSignals(False)

    # 把根布局塞进 tab（保持结构清晰）
    def tab_basic_layout_add(self, root):
        outer = QVBoxLayout(self.tab_basic)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(root)

    # ---------- 加密货币 ----------
    def build_crypto_tab(self):
        lay = QVBoxLayout(self.tab_crypto)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        self.crypto_table = QTableWidget(0, 4)
        self.crypto_table.setHorizontalHeaderLabels(
            ["币种", "当前价格", "持有量 coinAmount", "均价"]
        )
        self.crypto_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.crypto_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        self.crypto_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self.crypto_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch)
        lay.addWidget(self.crypto_table)

        hint = QLabel("⚠️ 可在【持有量】列直接修改数量，保存时写入存档。")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

    # ---------- 升级 ----------
    def build_upgrade_tab(self):
        lay = QVBoxLayout(self.tab_upgrade)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)

        # 一键操作按钮
        bar = QHBoxLayout()
        bar.setSpacing(8)
        b = QPushButton("🚀 一键升级全部满级")
        b.clicked.connect(self._upgrade_max_all)
        bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)

        self.upgrade_table = QTableWidget(0, 2)
        self.upgrade_table.setHorizontalHeaderLabels(["升级项", "等级 level"])
        self.upgrade_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.upgrade_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        # 等级列输入即实时钳制：超上限立马替换为上限（避免递归用钳制锁）
        self._upgrade_clamping = False
        self.upgrade_table.itemChanged.connect(self._on_upgrade_level_edit)
        lay.addWidget(self.upgrade_table)

        hint = QLabel("⚠️ 可在【等级】列直接修改数值，保存时写入存档。")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

    # ---------- 内存修改（外部进程内存扫描，不写入存档文件） ----------
    def build_memory_tab(self):
        lay = QVBoxLayout(self.tab_memory)
        lay.setContentsMargins(14, 14, 14, 10)
        lay.setSpacing(8)

        self._mem_scanner = None    # MemScanner（附加到游戏进程）
        self._mem_targets = []      # [(name, value, vtype)] 从存档提取的扫描目标
        self._mem_hits = {}         # {name:[addr,...]} 最近一次扫描结果
        self._mem_rows = []         # 结果表每行: (name, addr, vtype)
        self._mem_prev = None       # 二次扫描的基准快照 {addr: 上次扫描时的值}
        self._mem_nav_row = self._nav_keys.index("memory")

        # 1) 进程区
        prow = QHBoxLayout(); prow.setSpacing(8)
        self.mem_proc_lbl = QLabel("检测游戏进程…")
        self.mem_proc_lbl.setObjectName("Muted")
        btn_refresh = QPushButton("🔍 检测进程")
        btn_refresh.setObjectName("Ghost")
        btn_refresh.clicked.connect(self._mem_refresh_process)
        prow.addWidget(self.mem_proc_lbl, 1)
        prow.addWidget(btn_refresh)
        lay.addLayout(prow)

        # 2) 存档区
        srow = QHBoxLayout(); srow.setSpacing(8)
        base = os.path.basename(self.file_path) if self.file_path else "未选择存档"
        self.mem_save_lbl = QLabel(f"当前存档: {base}")
        self.mem_save_lbl.setObjectName("Muted")
        btn_choose = QPushButton("💾 选择使用的存档")
        btn_choose.setObjectName("Ghost")
        btn_choose.clicked.connect(self.find_save_file)
        srow.addWidget(self.mem_save_lbl, 1)
        srow.addWidget(btn_choose)
        lay.addLayout(srow)

        # 3) 目标提取按钮
        brow = QHBoxLayout(); brow.setSpacing(8)
        b = QPushButton("📥 从存档提取扫描目标")
        b.clicked.connect(self._mem_extract_targets)
        brow.addWidget(b)
        b_sel = QPushButton("全选"); b_sel.setObjectName("Ghost")
        b_sel.clicked.connect(lambda: self._mem_check_all(True))
        brow.addWidget(b_sel)
        b_un = QPushButton("全不选"); b_un.setObjectName("Ghost")
        b_un.clicked.connect(lambda: self._mem_check_all(False))
        brow.addWidget(b_un)
        brow.addStretch(1)
        lay.addLayout(brow)

        # 4) 目标表格
        self.mem_target_table = QTableWidget(0, 4)
        self.mem_target_table.setHorizontalHeaderLabels(["☑", "字段", "存档值", "类型"])
        hh = self.mem_target_table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.mem_target_table.setMaximumHeight(190)
        lay.addWidget(self.mem_target_table)

        # 5) 扫描操作
        act = QHBoxLayout(); act.setSpacing(8)
        b_scan = QPushButton("🚀 开始扫描")
        b_scan.clicked.connect(self._mem_start_scan)
        act.addWidget(b_scan)
        b_ref = QPushButton("🔁 重读选中地址"); b_ref.setObjectName("Ghost")
        b_ref.clicked.connect(self._mem_reread)
        act.addWidget(b_ref)
        b_write = QPushButton("✍ 写入全部选中地址"); b_write.setObjectName("Ghost")
        b_write.clicked.connect(self._mem_write_selected)
        act.addWidget(b_write)
        b_clear = QPushButton("🗑 清空结果"); b_clear.setObjectName("Ghost")
        b_clear.clicked.connect(self._mem_clear)
        act.addWidget(b_clear)
        b_scan2 = QPushButton("🔎 下一次扫描(只保留已变化)")
        b_scan2.clicked.connect(self._mem_scan_again)
        act.addWidget(b_scan2)
        self._mem_fold_btn = QPushButton("👁 展开候选"); self._mem_fold_btn.setObjectName("Ghost")
        self._mem_fold_btn.setCheckable(True)
        self._mem_fold_btn.clicked.connect(self._mem_toggle_fold)
        act.addWidget(self._mem_fold_btn)
        b_sync = QPushButton("🔁 自动同步10s：开")
        b_sync.setObjectName("Ghost")
        b_sync.setCheckable(True)
        b_sync.setChecked(True)
        b_sync.clicked.connect(self._mem_toggle_sync)
        act.addWidget(b_sync)
        self._mem_sync_btn = b_sync
        b_sync.hide()                                        # 仅隐藏按钮，不影响同步功能
        self._mem_sync_timer = QTimer(self)
        self._mem_sync_timer.setInterval(10000)                # 每 10s 同步一次
        self._mem_sync_timer.timeout.connect(self._mem_sync_once)
        self._mem_sync_timer.start()
        act.addStretch(1)
        lay.addLayout(act)

        # 6) 结果树（按字段分组，子列表显示详细地址，默认不展开避免卡死）
        self.mem_result_table = QTreeWidget()
        self.mem_result_table.setColumnCount(4)
        self.mem_result_table.setHeaderLabels(["☑", "字段 / 地址", "当前值", "目标值(双击改)"])
        self.mem_result_table.setUniformRowHeights(True)
        hh2 = self.mem_result_table.header()
        hh2.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh2.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh2.setSectionResizeMode(3, QHeaderView.Stretch)
        hh2.setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.mem_result_table, 1)

        hint = QLabel("💡 先选存档→从存档提取目标→开始扫描定位真实内存地址；"
                      "在【目标值】列双击输入新数值，点【写入全部选中地址】即刻修改内存（不写存档）。")
        hint.setObjectName("Hint"); hint.setWordWrap(True)
        lay.addWidget(hint)

        QTimer.singleShot(0, self._mem_refresh_process)

    # ---------- 内存：后端逻辑 ----------
    def _mem_refresh_process(self):
        pid, exe = find_game_process()
        if not pid:
            self.mem_proc_lbl.setText("❌ 未检测到游戏进程（请先启动游戏）")
            return
        try:
            if self._mem_scanner is None or self._mem_scanner.pid != pid:
                if self._mem_scanner is not None:
                    try:
                        self._mem_scanner.close()
                    except Exception:
                        pass
                self._mem_scanner = MemScanner(pid)
            self.mem_proc_lbl.setText(f"✅ 已绑定游戏: {exe}  (PID {pid})")
            self.log(f"🔬 已绑定游戏进程 {exe} (PID {pid})")
        except Exception as e:
            self.mem_proc_lbl.setText(f"❌ 无法打开进程: {e}")

    def _collect_save_targets(self):
        """从当前存档抽取可扫描的标量字段。"""
        t = []
        if not isinstance(self.data, dict):
            return t

        def ok_num(v):
            return isinstance(v, (int, float)) and not isinstance(v, bool)

        for key in ("Currency", "Level", "Exp", "Day", "Electricity", "CallData"):
            v = self.es3_get(key)
            if not ok_num(v):
                continue
            label = _MEM_TOP_FIELD_CN.get(key, key)
            if isinstance(v, float):
                t.append((f"顶层.{label}", float(v), "float32"))
            else:
                t.append((f"顶层.{label}", int(v), "int32"))

        cd = self.es3_get("CryptoData")
        if isinstance(cd, list):
            for i, c in enumerate(cd):
                if not isinstance(c, dict):
                    continue
                amt = c.get("coinAmount")
                if not ok_num(amt):
                    continue
                nm = c.get("coin", c.get("name", f"Crypto[{i}]"))
                t.append((f"加密货币.{nm}", float(amt) if isinstance(amt, float) else int(amt),
                          "float32" if isinstance(amt, float) else "int32"))

        uarr = self.es3_get("Upgrade")
        if isinstance(uarr, list):
            for i, u in enumerate(uarr):
                if not isinstance(u, dict):
                    continue
                nm = u.get("name", f"Upgrade[{i}]")
                lv = u.get("level")
                if not ok_num(lv):
                    continue
                cn = UPGRADE_MAP.get(nm, (nm, None))[0]   # 升级名 → 中文
                t.append((f"升级.{cn}", float(lv) if isinstance(lv, float) else int(lv),
                          "float32" if isinstance(lv, float) else "int32"))
        return t

    def _mem_extract_targets(self):
        if not isinstance(self.data, dict):
            QMessageBox.warning(self, "未加载存档", "请先打开/选择存档！")
            return
        tgts = self._collect_save_targets()
        self._mem_targets = tgts
        self.mem_target_table.setRowCount(0)
        for nm, v, vt in tgts:
            r = self.mem_target_table.rowCount()
            self.mem_target_table.insertRow(r)
            c0 = QTableWidgetItem()
            c0.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            # 顶层关键标量默认勾选；加密货币/升级项常见小整数易命中爆炸，默认不勾选
            c0.setCheckState(Qt.Checked if nm.startswith("顶层.") else Qt.Unchecked)
            self.mem_target_table.setItem(r, 0, c0)
            self.mem_target_table.setItem(r, 1, QTableWidgetItem(nm))
            self.mem_target_table.setItem(r, 2, QTableWidgetItem(str(v)))
            self.mem_target_table.setItem(r, 3, QTableWidgetItem(vt))
        self._mem_sync_save_label()
        self.log(f"📥 已从存档提取 {len(tgts)} 个扫描目标")

    def _mem_sync_save_label(self):
        base = os.path.basename(self.file_path) if self.file_path else "未选择存档"
        self.mem_save_lbl.setText(f"当前存档: {base}")

    def _mem_check_all(self, checked):
        st = Qt.Checked if checked else Qt.Unchecked
        for r in range(self.mem_target_table.rowCount()):
            it0 = self.mem_target_table.item(r, 0)
            if it0 is not None:
                it0.setCheckState(st)

    def _mem_checked_targets(self):
        out = []
        for r in range(self.mem_target_table.rowCount()):
            it0 = self.mem_target_table.item(r, 0)
            if it0 is None or it0.checkState() != Qt.Checked:
                continue
            nm = self.mem_target_table.item(r, 1).text()
            vt = self.mem_target_table.item(r, 3).text()
            for tn, tv, _ in self._mem_targets:
                if tn == nm:
                    out.append((nm, tv, vt))
                    break
        return out

    def _mem_start_scan(self):
        if self._mem_scanner is None:
            QMessageBox.warning(self, "未绑定进程", "请先点【检测进程】绑定游戏！")
            return
        tgts = self._mem_checked_targets()
        if not tgts:
            QMessageBox.warning(self, "没有目标",
                                "请先【从存档提取扫描目标】并勾选至少一项！")
            return
        self.status_lbl.setText("🚀 正在扫描…（约需 1 分钟，请勿点击）")
        self.log(f"🚀 开始内存首扫，共 {len(tgts)} 个目标")
        self._mem_worker = _MemScanWorker(self._mem_scanner, tgts, None, workers=4)
        self._mem_worker.finished_ok.connect(self._mem_on_scan_done)
        self._mem_worker.failed.connect(self._mem_on_scan_fail)
        self._mem_worker.start()
        # 轮询扫描进度，让用户看到实时推进而不是"一直没反应"
        self._mem_progress_timer = QTimer(self)
        self._mem_progress_timer.timeout.connect(self._mem_tick_progress)
        self._mem_progress_timer.start(150)

    def _mem_tick_progress(self):
        try:
            scanned, total = self._mem_scanner.scan_progress()
        except Exception:
            return
        if total <= 0:
            return
        pct = min(100.0, scanned * 100.0 / total)
        sm = scanned / (1024 * 1024)
        tm = total / (1024 * 1024)
        self.status_lbl.setText(
            f"🚀 正在首扫 {pct:.1f}%  (已读 {sm:.0f}/{tm:.0f} MB)")

    def _mem_on_scan_done(self, res):
        self._mem_stop_progress()
        el = res.pop("_elapsed", 0)
        self._mem_hits = dict(res)
        total = sum(len(v) for v in res.values() if isinstance(v, list))
        self.log(f"✅ 首扫完成 {el:.1f}s，共 {total} 个候选地址")
        self.status_lbl.setText(f"✅ 扫描完成：{total} 个候选地址，耗时 {el:.1f}s")
        self._mem_render_results()

    def _mem_on_scan_fail(self, msg):
        self._mem_stop_progress()
        self.status_lbl.setText(f"❌ 扫描失败: {msg}")
        self.log(f"❌ 扫描失败: {msg}")

    def _mem_stop_progress(self):
        t = getattr(self, "_mem_progress_timer", None)
        if t is not None:
            t.stop()
            t.deleteLater()
            self._mem_progress_timer = None

    def _mem_render_results(self):
        # 按字段分组显示：每个字段一个顶层节点（节点名后显示该字段的总数据量），
        # 子节点列出全部候选地址的详细（地址/当前值/目标值）。
        # 为免卡死：默认所有字段节点折叠，只显示字段名与总数据量；
        # 可点【👁 展开候选】一次性展开全部查看明细。写入只写☑勾选的子行，绝不自动批量写。
        CAP = 400                      # 每字段最多列出的候选地址
        if self._mem_prev is None:
            self._mem_prev = {}        # 首扫时建基准快照；后续 render 不再覆盖
        tv_map = {n: v for n, v, _ in self._mem_targets}
        vt_map = {n: vt for n, _, vt in self._mem_targets}
        self.mem_result_table.clear()
        self._mem_rows = []            # (叶子 item, nm, addr, vt)
        for nm, addrs in self._mem_hits.items():
            if not isinstance(addrs, list) or not addrs:
                continue
            vt = vt_map.get(nm, "int32")
            tv = tv_map.get(nm)
            cand = []
            for addr in addrs[:CAP]:
                cur = self._mem_safe_read(addr, vt)
                if cur is not None and addr not in self._mem_prev:
                    self._mem_prev[addr] = cur
                cand.append((addr, cur))
            if not cand:
                continue
            best = None
            if tv is not None:
                def _dist(c):
                    return float("inf") if c is None else abs(float(c) - float(tv))
                best = min(range(len(cand)), key=lambda i: _dist(cand[i][1]))
            # 顶层字段节点：列1显示字段名，并在其后显示总数据量
            top = QTreeWidgetItem([str(len(cand)), f"{nm}（共 {len(cand)} 个）", "", ""])
            tf = top.font(1); tf.setBold(True)
            top.setFont(1, tf)
            top.setSizeHint(0, QSize(28, 32))   # 字段节点行高
            for ai, (addr, cur) in enumerate(cand):
                is_best = (ai == best)
                leaf = QTreeWidgetItem()
                leaf.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                leaf.setCheckState(0, Qt.Checked if is_best else Qt.Unchecked)
                leaf.setText(1, hex(addr))
                leaf.setText(2, "" if cur is None else self._mem_fmt(cur))
                leaf.setText(3, "")
                leaf.setFlags(leaf.flags() | Qt.ItemIsEditable)
                leaf.setToolTip(3, "双击输入新值")
                leaf.setSizeHint(0, QSize(28, 34))          # 行加高 → 编辑框更大
                vf = leaf.font(3); vf.setPointSizeF(max(vf.pointSizeF() or 10, 12.0))
                leaf.setFont(3, vf)                          # 目标值编辑字体放大
                top.addChild(leaf)
                self._mem_rows.append((leaf, nm, addr, vt))
            self.mem_result_table.addTopLevelItem(top)
            top.setExpanded(False)     # 默认折叠
            top.setToolTip(1, f"{nm}：共 {len(cand)} 个候选地址，点击展开查看")

    def _mem_toggle_fold(self):
        """展开/收起所有字段节点：展开显示全部地址明细；收起仅显示字段+总数据量。"""
        expanded = self._mem_fold_btn.isChecked()
        self._mem_fold_btn.setText("🙈 收起候选" if expanded else "👁 展开候选")
        for i in range(self.mem_result_table.topLevelItemCount()):
            self.mem_result_table.topLevelItem(i).setExpanded(expanded)

    def _mem_toggle_sync(self, checked):
        """开关每 10s 自动同步。"""
        self._mem_sync_btn.setText("🔁 自动同步10s：开" if checked else "🔁 自动同步10s：关")
        if checked:
            self._mem_sync_timer.start()
        else:
            self._mem_sync_timer.stop()

    def _mem_sync_once(self):
        """每 10s：重读已列候选地址的当前值，只刷新『值发生变化』的叶子行（增量同步）。"""
        if not self._mem_rows:
            return
        changes = 0
        for leaf, nm, addr, vt in self._mem_rows:
            cur = self._mem_safe_read(addr, vt)
            newtxt = "" if cur is None else self._mem_fmt(cur)
            if leaf.text(2) != newtxt:
                leaf.setText(2, newtxt)
                changes += 1
        if changes:
            self.log(f"🔁 已同步 {changes} 个地址的最新值")

    def _mem_safe_read(self, addr, vt):
        try:
            return self._mem_scanner.read_value(addr, vt)
        except Exception:
            return None

    def _mem_fmt(self, v):
        if isinstance(v, int):
            return str(v)
        if isinstance(v, float):
            return f"{v:.6g}"
        return str(v)

    def _mem_reread(self):
        for leaf, nm, addr, vt in self._mem_rows:
            cur = self._mem_safe_read(addr, vt)
            leaf.setText(2, "" if cur is None else self._mem_fmt(cur))
        self.log("🔁 已重读当前内存值")

    def _mem_clear(self):
        self.mem_result_table.clear()
        self._mem_rows = []
        self._mem_hits = {}
        self._mem_prev = None

    def _mem_write_selected(self):
        if self._mem_scanner is None:
            QMessageBox.warning(self, "未绑定进程", "请先点【检测进程】绑定游戏！")
            return
        rows = [
            r for r in self._mem_rows
            if r[0].checkState(0) == Qt.Checked
        ]
        if not rows:
            QMessageBox.information(
                self, "未勾选",
                "请在结果树【☑】列勾选要写入的地址行\n（默认已勾选每字段最接近目标值的一条）。")
            return
        n = 0
        for leaf, nm, addr, vt in rows:
            txt = leaf.text(3).strip()
            if not txt:
                continue
            try:
                val = int(float(txt)) if vt == "int32" else float(txt)
            except ValueError:
                continue
            if self._mem_scanner.write_value(addr, vt, val):
                leaf.setText(2, self._mem_fmt(self._mem_safe_read(addr, vt)))
                n += 1
        self.log(f"✍ 已写入 {n} 个地址")
        tip = "修改后可能需要执行一次对应值的操作（如消费）才可在游戏内生效。"
        self.status_lbl.setText(f"已写入 {n} 个地址：{tip}")

    def _mem_scan_again(self):
        """Cheat-Engine 式下一次扫描（只读、不写、安全）：
        与『上次扫描时的基准值』对比，只保留『当前值已发生变化』的地址。
        流程：首扫存基准 → 去游戏让数值变化（如开始新的一天）→ 点本按钮过滤 →
        重复过滤直到每个字段只剩 1 个地址。"""
        sc = self._mem_scanner
        if sc is None:
            QMessageBox.warning(self, "未绑定进程", "请先点【检测进程】绑定游戏！")
            return
        if not self._mem_hits:
            QMessageBox.information(
                self, "需先首扫",
                "请先点【开始扫描】得到候选地址；\n"
                "然后在游戏里让该值发生变化（如开始新的一天），再进行下一次扫描。")
            return
        prev = self._mem_prev or {}
        vt_map = {n: vt for n, _, vt in self._mem_targets}
        new = {}
        kept = dropped = 0
        converged = 0                       # 已收敛到唯一地址、本次自动保留的字段数
        for nm, addrs in self._mem_hits.items():
            # 一旦该字段已收敛到只剩 1 个地址，下次扫描直接跳过过滤、原样保留，
            # 防止它被误删/误收敛导致字段整个消失。
            if len(addrs) == 1:
                new[nm] = addrs
                converged += 1
                continue
            vt = vt_map.get(nm, "int32")
            keep = []
            for addr in addrs[:400]:
                cur = self._mem_safe_read(addr, vt)
                if cur is None:
                    dropped += 1
                    continue
                last = prev.get(addr)
                if last is not None and float(cur) != float(last):
                    keep.append(addr)
                    kept += 1
                else:
                    dropped += 1
            if keep:
                new[nm] = keep
        if not new:
            self.status_lbl.setText(
                "❌ 下一次扫描没有保留任何地址：似乎数值没变化。"
                "请回到游戏让该值变化（开始新的一天）后再点【下一次扫描】。")
            self.log("下一次扫描无保留：数值未发生变化。")
            return
        # 用保留集的当前值作为下一轮基准
        new_prev = {}
        for nm, addrs in new.items():
            vt = vt_map.get(nm, "int32")
            for addr in addrs:
                c = self._mem_safe_read(addr, vt)
                if c is not None:
                    new_prev[addr] = c
        self._mem_prev = new_prev
        self._mem_hits = new
        self._mem_render_results()
        total = sum(len(v) for v in new.values())
        per = "、".join(f"{nm}:{len(v)}" for nm, v in new.items())
        if converged and all(len(v) == 1 for v in new.values()):
            self.status_lbl.setText(
                f"✅ 所有字段均已收敛到唯一地址（{per}）。"
                "后续点击【下一次扫描】将自动保留已收敛地址，不再过滤。")
        else:
            self.status_lbl.setText(
                f"🔎 下一次扫描保留下 {total} 个地址（{per}）。"
                f"已收敛字段 {converged} 个自动保留。"
                "若每字段仍 >1 个，请再次在游戏里触发变化并点【下一次扫描】；"
                "直到每字段只剩 1 个即为目标地址。")
        self.log(f"🔎 下一次扫描：剔除 {dropped}，保留 {total}（{per}），已收敛 {converged}")

    # ---------- 银行还款 / 剧情解锁 / 教程解锁（表格 + 一键操作） ----------
    def build_debt_story_tutorial_tabs(self):
        # === 银行还款管理 ===
        lay = QVBoxLayout(self.tab_debt)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("🏦 银行还款管理")
        title.setObjectName("CardTitle")
        lay.addWidget(title)

        # 一键操作按钮
        bar = QHBoxLayout()
        bar.setSpacing(8)
        b1 = QPushButton("🎁 一键全还清")
        b2 = QPushButton("🔓 一键解锁债务")
        b3 = QPushButton("♻️ 重置债务")
        b3.setObjectName("Ghost")
        b1.clicked.connect(self._debt_clear_all)
        b2.clicked.connect(self._debt_unlock_all)
        b3.clicked.connect(self._debt_reset)
        bar.addWidget(b1)
        bar.addWidget(b2)
        bar.addWidget(b3)
        bar.addStretch(1)
        lay.addLayout(bar)

        self.debt_table = self._build_list_editor(lay)
        # 标记列名映射：原始字段 -> 中文表头
        self._debt_headers = {
            "paidAmount": "已还金额",
            "curAmount": "当前金额",
            "dayLeft": "总天数",
            "curDayLeft": "剩余天数",
            "isPaid": "是否已还",
            "unlocked": "是否解锁",
            "interestRate": "利率(%)",
        }
        self.debt_table._header_map = self._debt_headers
        self._table_keys["Debt"] = self.debt_table
        hint = QLabel("💡 双击单元格编辑数值。【是否已还/是否解锁】点击勾选切换。保存时写入存档。")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

        # === 剧情解锁 ===
        lay = QVBoxLayout(self.tab_story)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("📖 剧情 & 任务解锁")
        title.setObjectName("CardTitle")
        lay.addWidget(title)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        b1 = QPushButton("🎁 一键解锁全部剧情")
        b2 = QPushButton("♻️ 重置剧情进度")
        b2.setObjectName("Ghost")
        b1.clicked.connect(self._story_unlock_all)
        b2.clicked.connect(self._story_reset)
        bar.addWidget(b1)
        bar.addWidget(b2)
        bar.addStretch(1)
        lay.addLayout(bar)

        self.story_table = self._build_list_editor(lay)
        self._story_headers = {
            "id": "剧情索引",
            "currentProgress": "当前进度",
            "unlockProgress": "解锁所需",
            "isCompleted": "是否完成",
            "unlocked": "是否解锁",
        }
        self.story_table._header_map = self._story_headers
        self.story_table._readonly_cols = ("id",)
        self._table_keys["MissionProgress"] = self.story_table
        hint = QLabel("💡 【解锁所需/当前进度】可直接编辑实现任务完成。【是否完成/是否解锁】点击勾选切换。保存时写入存档。")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

        # === 教程解锁 ===
        lay = QVBoxLayout(self.tab_tutorial)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("🎓 教程解锁")
        title.setObjectName("CardTitle")
        lay.addWidget(title)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        b1 = QPushButton("🎁 一键解锁全部教程")
        b2 = QPushButton("♻️ 重置教程状态")
        b2.setObjectName("Ghost")
        b1.clicked.connect(self._tutorial_unlock_all)
        b2.clicked.connect(self._tutorial_reset)
        bar.addWidget(b1)
        bar.addWidget(b2)
        bar.addStretch(1)
        lay.addLayout(bar)

        self.tutorial_table = self._build_list_editor(lay)
        self._tutorial_headers = {
            "index": "教程索引",
            "unlocked": "是否解锁",
        }
        self.tutorial_table._header_map = self._tutorial_headers
        self.tutorial_table._readonly_cols = ("index",)
        self._table_keys["TutorialSaveData"] = self.tutorial_table
        hint = QLabel("💡 【是否解锁】点击勾选切换。教程索引列只读。保存时写入存档。")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

    # ---------- 银行/剧情/教程 一键操作 ----------
    def _debt_clear_all(self):
        """一键全还清：把每条债务的 paidAmount 设为 curAmount，isPaid=True，dayLeft 保留。"""
        if not isinstance(self.data, dict):
            return
        items = self.es3_get("Debt")
        if not isinstance(items, list):
            return
        changed = 0
        for d in items:
            if isinstance(d, dict):
                if d.get("isPaid") is not True:
                    d["isPaid"] = True
                    changed += 1
                # 已还金额等于当前金额
                d["paidAmount"] = d.get("curAmount", 0)
        # 同步刷新表格
        if hasattr(self, "debt_table"):
            self._list_load(self.debt_table, items)
        self.set_status(f"已一键还清 {changed} 笔未还债务")

    def _debt_unlock_all(self):
        items = self.es3_get("Debt")
        if not isinstance(items, list):
            return
        for d in items:
            if isinstance(d, dict):
                d["unlocked"] = True
        if hasattr(self, "debt_table"):
            self._list_load(self.debt_table, items)
        self.set_status("已一键解锁全部债务")

    def _debt_reset(self):
        items = self.es3_get("Debt")
        if not isinstance(items, list):
            return
        for d in items:
            if isinstance(d, dict):
                d["isPaid"] = False
                d["unlocked"] = False
                d["paidAmount"] = 0
        if hasattr(self, "debt_table"):
            self._list_load(self.debt_table, items)
        self.set_status("已重置债务状态")

    def _story_unlock_all(self):
        items = self.es3_get("MissionProgress")
        if not isinstance(items, list):
            return
        for d in items:
            if isinstance(d, dict):
                d["unlocked"] = True
                d["isCompleted"] = True
                # 进度拉到解锁所需的 + 1（保险）
                up = d.get("unlockProgress", 0)
                d["currentProgress"] = max(d.get("currentProgress", 0), (up or 0) + 1)
        if hasattr(self, "story_table"):
            self._list_load(self.story_table, items)
        self.set_status(f"已一键解锁全部 {len(items)} 个剧情任务")

    def _story_reset(self):
        items = self.es3_get("MissionProgress")
        if not isinstance(items, list):
            return
        for d in items:
            if isinstance(d, dict):
                d["unlocked"] = False
                d["isCompleted"] = False
                d["currentProgress"] = 0
        if hasattr(self, "story_table"):
            self._list_load(self.story_table, items)
        self.set_status("已重置剧情进度")

    def _tutorial_unlock_all(self):
        items = self.es3_get("TutorialSaveData")
        if not isinstance(items, list):
            return
        for d in items:
            if isinstance(d, dict):
                d["unlocked"] = True
        if hasattr(self, "tutorial_table"):
            self._list_load(self.tutorial_table, items)
        self.set_status(f"已一键解锁全部 {len(items)} 个教程")

    def _tutorial_reset(self):
        items = self.es3_get("TutorialSaveData")
        if not isinstance(items, list):
            return
        for d in items:
            if isinstance(d, dict):
                d["unlocked"] = False
        if hasattr(self, "tutorial_table"):
            self._list_load(self.tutorial_table, items)
        self.set_status("已重置教程状态")

    # ---------- 物品 / 放置物品 / 其他（列表式编辑） ----------
    def build_json_tab(self):
        # 物品：列表表格编辑
        lay = QVBoxLayout(self.tab_items)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.items_table = self._build_list_editor(lay)
        lay.addWidget(self._build_row_ops_bar(self.items_table))
        self._table_keys["Items"] = self.items_table
        h = QLabel("⚠️ 物品列表：每个元素一行，标量列直接改；嵌套列(position/rotation等)为紧凑 JSON，"
                   "形如 {\"x\":0,...}，保存时会校验。")
        h.setObjectName("Hint")
        lay.addWidget(h)

        # 放置物品：列表表格编辑
        lay = QVBoxLayout(self.tab_placed)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.placed_table = self._build_list_editor(lay)
        lay.addWidget(self._build_row_ops_bar(self.placed_table))
        self._table_keys["PlaceItems"] = self.placed_table
        h = QLabel("⚠️ 放置物品列表：每个元素一行，标量列直接改；嵌套列(id/position/rotation等)为紧凑 JSON。")
        h.setObjectName("Hint")
        lay.addWidget(h)

        # 其他：可编辑的通用数据查看器（标量→输入框，列表→表格，复杂结构→JSON）
        lay = QVBoxLayout(self.tab_other)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # 键选择栏
        sel_bar = QHBoxLayout()
        lbl = QLabel("数据键")
        lbl.setObjectName("Muted")
        self.other_key_box = QComboBox()
        self.other_key_box.setMinimumWidth(260)
        self.other_key_box.setFixedHeight(32)
        self.other_key_box.currentIndexChanged.connect(self._on_other_key_changed)
        sel_bar.addWidget(lbl)
        sel_bar.addWidget(self.other_key_box)
        sel_bar.addStretch(1)
        lay.addLayout(sel_bar)

        # 分段：标量输入 / 通用表格（含行操作）/ JSON 编辑器
        self.other_scalar = QWidget()
        osl = QHBoxLayout(self.other_scalar)
        osl.setContentsMargins(0, 0, 0, 0)
        osl.addWidget(QLabel("值"))
        osl.addWidget(QLabel(""))  # 占位，动态填充
        self._other_scalar_txt = QWidget()

        self.other_table = self._build_list_editor(QWidget())  # 稍后加入布局

        self.other_json = QPlainTextEdit()
        self.other_json.setFont(QFont("Consolas", 10))

        self._other_stack = QStackedWidget()
        self._other_stack.addWidget(self.other_scalar)
        self._other_stack.addWidget(self.other_table)
        self._other_stack.addWidget(self.other_json)
        lay.addWidget(self._other_stack, 1)

        # 行操作按钮（只在表格模式显示）
        self.other_row_bar = self._build_row_ops_bar(self.other_table)
        lay.addWidget(self.other_row_bar)

    def _build_list_editor(self, parent):
        """创建一个通用列表表格，作者返回该表格。
        表格用于展示 list[dict]，列格式由第一个元素决定；保存时按 _list_meta 还原类型。"""
        table = QTableWidget(0, 0)
        table.setObjectName("ListTable")
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.verticalHeader().setVisible(False)
        table._list_meta = {}  # 由 load/save 读写
        return table

    def _build_row_ops_bar(self, table):
        """新增行 / 删除选中行 按钮栏"""
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        btn_add = QPushButton("➕ 新增行")
        btn_del = QPushButton("➖ 删除选中行")
        btn_del.setObjectName("Ghost")
        btn_add.clicked.connect(lambda: self._list_add_row(table))
        btn_del.clicked.connect(lambda: self._list_del_row(table))
        h.addWidget(btn_add)
        h.addWidget(btn_del)
        h.addStretch(1)
        return bar

    # ---------- 通用列表表格：加载 / 保存 ----------
    def _list_meta_from_seed(self, items):
        """从种子数据建立列定义：列顺序 + 每列类型(用于文本还原)"""
        if not isinstance(items, list) or not items:
            return [], []
        keys = []
        types = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            for k, v in it.items():
                if k not in types:
                    keys.append(k)
                    types[k] = self._type_of(v)
        return keys, [types.get(k) for k in keys]

    def _type_of(self, val):
        if isinstance(val, bool):
            return "bool"
        if isinstance(val, int):
            return "int"
        if isinstance(val, float):
            return "float"
        if isinstance(val, str):
            return "str"
        return None  # 复杂结构 → 按 JSON 处理

    def _new_bool_cell(self, value):
        """创建一个居中、可勾选的布尔单元格"""
        item = QTableWidgetItem()
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if value else Qt.Unchecked)
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _is_scalar_list(self, items):
        """是否为纯标量列表（如 Tutorial: [bool,...]，NpcRoleFound:[int,...]）"""
        return (isinstance(items, list) and items
                and not isinstance(items[0], dict)
                and all(not isinstance(i, dict) and not isinstance(i, list)
                        for i in items))

    def _list_load(self, table, items):
        """把列表填入表格（支持 list[dict] 与纯标量列表），并记录类型元数据。"""
        # 纯标量列表：单列编辑
        if self._is_scalar_list(items):
            t0 = self._type_of(items[0])
            table._list_meta = {"scalar": t0}
            header = self._scalar_header(t0)
            table.setColumnCount(1)
            table.setHorizontalHeaderLabels([header])
            table.setRowCount(len(items))
            table.blockSignals(True)
            for r, v in enumerate(items):
                if t0 == "bool":
                    table.setItem(r, 0, self._new_bool_cell(bool(v)))
                else:
                    table.setItem(r, 0, QTableWidgetItem(self._cell_to_text(v)))
            table.blockSignals(False)
            return

        meta = self._list_meta_from_seed(items)
        table._list_meta = {"columns": meta[0], "types": meta[1]}
        cols = meta[0]
        types = meta[1]
        # 中文表头映射（如有）
        header_map = getattr(table, "_header_map", {}) or {}
        headers = [header_map.get(k, k) for k in cols]
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(items) if isinstance(items, list) else 0)
        table.blockSignals(True)
        # 只读列（id/index 等不参与编辑）
        readonly_cols = set(getattr(table, "_readonly_cols", ()) or ())
        for r, it in enumerate(items or []):
            if not isinstance(it, dict):
                continue
            for c, k in enumerate(cols):
                v = it.get(k)
                if types[c] == "bool":
                    cell = self._new_bool_cell(bool(v))
                    if k in readonly_cols:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEnabled)
                    table.setItem(r, c, cell)
                else:
                    cell = QTableWidgetItem(self._cell_to_text(v))
                    if k in readonly_cols:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    table.setItem(r, c, cell)
        table.blockSignals(False)

    def _scalar_header(self, t):
        return {bool: "是否(勾选切换)", int: "数值", float: "数值", str: "文本"}.get(t, "值")

    def _cell_to_text(self, v):
        if v is None:
            return ""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return v
        if isinstance(v, (int, float)):
            return repr(v)
        return json.dumps(v, ensure_ascii=False)  # dict/list

    def _list_save(self, table):
        """把表格读回为 list（list[dict] 或纯标量列表），按列类型还原。"""
        meta = getattr(table, "_list_meta", {})
        # 纯标量列表
        if "scalar" in meta:
            t = meta.get("scalar")
            out = []
            for r in range(table.rowCount()):
                it = table.item(r, 0)
                if t == "bool" and it is not None:
                    out.append(it.checkState() == Qt.Checked)
                else:
                    text = it.text() if it is not None else ""
                    out.append(self._text_to_cell(text, t))
            return out

        cols = meta.get("columns", [])
        types = meta.get("types", [])
        n = table.rowCount()
        out = []
        for r in range(n):
            d = {}
            for c, k in enumerate(cols):
                it = table.item(r, c)
                if c < len(types) and types[c] == "bool" and it is not None:
                    d[k] = (it.checkState() == Qt.Checked)
                    continue
                text = it.text() if it is not None else ""
                d[k] = self._text_to_cell(text, types[c] if c < len(types) else None)
            out.append(d)
        return out

    def _text_to_cell(self, text, t):
        txt = text
        if t == "int":
            return self._to_int(txt)
        if t == "float":
            return self._to_float(txt)
        if t == "bool":
            return self._parse_bool_text(txt)
        if t == "str":
            return txt
        # None：复杂结构，尽量还原 dict/list
        s = txt.strip()
        if not s:
            return None
        try:
            return json.loads(s)
        except Exception:
            return s

    def _to_int(self, txt):
        s = str(txt).strip()
        if not s:
            return 0
        try:
            return int(float(s))
        except Exception:
            return 0

    def _to_float(self, txt):
        s = str(txt).strip()
        if not s:
            return 0.0
        try:
            return float(s)
        except Exception:
            return 0.0

    def _parse_bool_text(self, txt):
        """宽松布尔解析：true/false/yes/no/on/off/1/0/是/否/有/无/✓/✗ 等"""
        s = str(txt).strip().lower()
        if s in ("true", "1", "yes", "on", "是", "y", "t", "有", "✓", "✔", "是√", "对", "好"):
            return True
        if s in ("false", "0", "no", "off", "否", "n", "f", "无", "✗", "✘", "错", "不", "否√"):
            return False
        # 空/未知 → False
        if not s:
            return False
        # 兼容中文"是xxx" "否xxx"：以前缀判断
        if s.startswith("是") or s.startswith("有") or s.startswith("对"):
            return True
        if s.startswith("否") or s.startswith("无") or s.startswith("不") or s.startswith("错"):
            return False
        return s in ("true", "1")

    def _list_add_row(self, table):
        table.insertRow(table.rowCount())
        meta = getattr(table, "_list_meta", {})
        # 纯标量 bool 列表：新增行放一个未勾选复选框
        if "scalar" in meta and meta.get("scalar") == "bool":
            table.setItem(table.rowCount() - 1, 0, self._new_bool_cell(False))
            return
        cols = meta.get("columns", [])
        types = meta.get("types", [])
        r = table.rowCount() - 1
        for c in range(table.columnCount()):
            if table.item(r, c) is not None:
                continue
            if c < len(types) and types[c] == "bool":
                table.setItem(r, c, self._new_bool_cell(False))
            else:
                table.setItem(r, c, QTableWidgetItem(""))

    def _list_del_row(self, table):
        rows = set(i.row() for i in table.selectedIndexes())
        for r in sorted(rows, reverse=True):
            table.removeRow(r)
        if isinstance(table, QPlainTextEdit):
            return

    # ---------- "其他"页通用编辑器 ----------
    def _on_other_key_changed(self):
        self._render_other_key()

    def _render_other_key(self):
        """根据下拉选中的键，渲染 标量/表格/JSON 编辑器。"""
        key = self.other_key_box.currentData()
        self._other_cur_key = key
        val = self.es3_get(key)
        # 清除旧的标量输入
        if self._other_scalar_entry is not None:
            self._other_scalar_entry.deleteLater()
            self._other_scalar_entry = None

        # 标量类型
        if self._is_scalar(val):
            self._other_stack.setCurrentIndex(0)  # 标量
            self.other_row_bar.setVisible(False)
            row = self.other_scalar.layout()
            # 删除旧的第二格占位
            while row.count() > 1:
                it = row.takeAt(1)
                w = it.widget()
                if w:
                    w.deleteLater()
            entry = QLineEdit(self._scalar_to_text(val))
            entry.setFixedHeight(32)
            entry.setAlignment(Qt.AlignLeft)
            row.addWidget(entry, 1)
            self._other_scalar_entry = entry
        elif isinstance(val, list):
            self._other_stack.setCurrentIndex(1)  # 表格
            self.other_row_bar.setVisible(True)
            self._list_load(self.other_table, val)
        else:
            # 复杂 dict → JSON 编辑器
            self._other_stack.setCurrentIndex(2)
            self.other_row_bar.setVisible(False)
            self.other_json.setPlainText(
                json.dumps(val, ensure_ascii=False, indent="\t") if val is not None else "")

    def _is_scalar(self, val):
        return isinstance(val, (bool, int, float, str))

    def _scalar_to_text(self, v):
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    # ---------- 工人 ----------
    def build_workers_tab(self):
        root = QWidget()
        v = QVBoxLayout(root)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        # 顶部工具行
        top = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("🔍 搜索工人名字或编号...")
        self.search_entry.setFixedHeight(34)
        self.search_entry.textChanged.connect(self.filter_workers)
        btn_max = QPushButton("🔼 全部加满")
        btn_reset = QPushButton("🔄 重置状态")
        btn_copy = QPushButton("📋 复制员工")
        btn_copy.setObjectName("Ghost")
        btn_reset.setObjectName("Ghost")
        btn_max.clicked.connect(self.max_all_workers)
        btn_reset.clicked.connect(self.reset_workers_status)
        btn_copy.clicked.connect(self.copy_worker)

        self.count_lbl = QLabel("共 0 个工人")
        self.count_lbl.setObjectName("Muted")
        top.addWidget(self.search_entry, 1)
        top.addWidget(self.count_lbl)
        top.addWidget(btn_copy)
        top.addWidget(btn_reset)
        top.addWidget(btn_max)
        v.addLayout(top)

        # 分栏
        split = QSplitter(Qt.Horizontal)
        self.worker_list = QListWidget()
        self.worker_list.currentRowChanged.connect(self.on_worker_select)
        split.addWidget(self.worker_list)

        self.worker_panel = QWidget()
        pv = QVBoxLayout(self.worker_panel)
        self.worker_title = QLabel("👤 请选择一个工人")
        self.worker_title.setObjectName("CardTitle")
        pv.addWidget(self.worker_title)

        # 属性网格
        grid = QGridLayout()
        self.worker_entries = {}
        attrs = [
            ("money", "💵 金钱"),
            ("intelligence", "🧠 智力"),
            ("strength", "💪 力量"),
            ("focus", "🎯 专注"),
            ("sickValue", "🤒 疾病值"),
            ("starveValue", "🍗 饥饿值"),
            ("thirstValue", "💧 口渴值"),
            ("sanityValue", "🧘 理智值"),
            ("tameProgress", "🦴 驯服进度"),
        ]
        for i, (key, label) in enumerate(attrs):
            row, col = divmod(i, 2)
            f = QFrame()
            f.setObjectName("FieldBox")
            fv = QVBoxLayout(f)
            fv.setContentsMargins(10, 6, 10, 6)
            fv.setSpacing(4)
            lb = QLabel(label)
            lb.setObjectName("Muted")
            e = QLineEdit()
            e.setFixedHeight(32)
            e.textChanged.connect(lambda *a, k=key: self.on_worker_field_changed(k))
            fv.addWidget(lb)
            fv.addWidget(e)
            grid.addWidget(f, row, col)
            self.worker_entries[key] = e
        pv.addLayout(grid)

        # 复选框
        chkrow = QHBoxLayout()
        self.cb_tamed = QCheckBox("✅ 已驯服")
        self.cb_dead = QCheckBox("💀 已死亡")
        self.cb_dead.setObjectName("DeadCheck")
        self.cb_tamed.toggled.connect(self.on_worker_checkbox_changed)
        self.cb_dead.toggled.connect(self.on_worker_checkbox_changed)
        chkrow.addWidget(self.cb_tamed)
        chkrow.addSpacing(24)
        chkrow.addWidget(self.cb_dead)
        chkrow.addStretch()
        pv.addLayout(chkrow)

        hint = QLabel("提示：修改数值自动保存到内存，最后点击顶部【保存存档】写入文件。")
        hint.setObjectName("Hint")
        pv.addWidget(hint)

        split.addWidget(self.worker_panel)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([280, 800])
        v.addWidget(split)

        outer = QVBoxLayout(self.tab_workers)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(root)

    # ==================== 日志 ====================
    def log(self, msg):
        self.statusBar.showMessage(msg, 8000)

    # ==================== ES3 取值辅助 ====================
    def es3_get(self, key):
        """返回 data[key]['value']，否则 None"""
        d = self.data
        if not isinstance(d, dict):
            return None
        node = d.get(key)
        if isinstance(node, dict) and "value" in node:
            return node["value"]
        return None

    def es3_set(self, key, value):
        d = self.data
        if not isinstance(d, dict):
            return
        node = d.get(key)
        if isinstance(node, dict) and "value" in node:
            node["value"] = value

    # ==================== 文件操作 ====================
    def _guess_default_dir(self):
        """自动查找常见位置的存档，返回打开对话框的默认目录。
        依次扫描：游戏 slots 目录、程序所在目录，取命中存档数最多的目录。
        """
        # 游戏存档目录: C:\Users\<用户>\AppData\LocalLow\Jiao Games\...
        # LocalLow 是 Local 的兄弟目录, 不能直接 LOCALAPPDATA + "Low"
        local_low = os.path.join(
            os.path.dirname(os.environ.get("LOCALAPPDATA", "")), "LocalLow")
        game_slots = os.path.join(
            local_low, "Jiao Games",
            "Scam Center Simulator_ UnderKingdom", "slots")
        local = os.path.dirname(os.path.abspath(__file__))

        save_dirs = {}  # dir -> 命中存档数量
        for d in (game_slots, local):
            if not os.path.isdir(d):
                continue
            cnt = 0
            for root, _, files in os.walk(d):
                for fn in files:
                    if fn.lower().endswith((".es3", ".json")):
                        cnt += 1
            if cnt:
                save_dirs[d] = cnt

        if not save_dirs:
            return ""
        return max(save_dirs, key=save_dirs.get)

    def open_file(self):
        try:
            start_dir = self._guess_default_dir()
            if start_dir:
                self.log(f"🔍 已自动定位到存档目录: {start_dir}")
            path, _ = QFileDialog.getOpenFileName(
                self, "选择 ES3 存档文件", start_dir,
                "ES3 存档 (*.es3);;JSON 文件 (*.json);;所有文件 (*.*)")
            if not path:
                return
            self._load_file(path)
        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"错误: {e}")
            self.log(f"❌ 打开失败: {e}")

    def _scan_saves(self):
        """扫描两个默认位置，返回找到的存档路径列表（去重、按路径排序）。"""
        # 游戏存档目录: C:\Users\<用户>\AppData\LocalLow\Jiao Games\...
        # LocalLow 是 Local 的兄弟目录, 不能直接 LOCALAPPDATA + "Low"
        local_low = os.path.join(
            os.path.dirname(os.environ.get("LOCALAPPDATA", "")), "LocalLow")
        game_slots = os.path.join(
            local_low, "Jiao Games",
            "Scam Center Simulator_ UnderKingdom", "slots")
        local = os.path.dirname(os.path.abspath(__file__))
        found = set()
        for d in (game_slots, local):
            if os.path.isdir(d):
                for root, _, files in os.walk(d):
                    for fn in files:
                        if fn.lower().endswith((".es3", ".json")):
                            found.add(os.path.join(root, fn))
        return sorted(found)

    def find_save_file(self):
        """查找并存档选择弹窗，用户选择后直接加载。"""
        try:
            saves = self._scan_saves()
        except Exception as e:
            QMessageBox.warning(self, "查找失败", f"扫描存档时出错:\n{e}")
            self.log(f"❌ 扫描失败: {e}")
            return

        if not saves:
            QMessageBox.information(
                self, "未找到存档",
                "未找到存档。已搜索以下位置：\n1. 程序运行目录\n"
                "2. C:\\Users\\<用户名>\\AppData\\LocalLow\\Jiao Games\\"
                "Scam Center Simulator_ UnderKingdom\\slots\\")
            self.log("🔍 未找到存档")
            return

        picked = self._pick_save_dialog(saves)
        if picked:
            self._load_file(picked)

    def _pick_save_dialog(self, saves):
        """列出找到的存档，返回用户选中的路径；取消则返回 None。"""
        from PySide6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowTitle(f"查找存档（共 {len(saves)} 个）")
        dlg.resize(640, 460)
        lay = QVBoxLayout(dlg)
        hint = QLabel("双击或选中后点【打开】加载对应的存档：")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

        listw = QListWidget()
        for p in saves:
            # 显示: 文件名 —— 所在目录 (tooltip 保留完整路径)
            name = os.path.basename(p)
            folder = os.path.dirname(p)
            it = QListWidgetItem(f"{name}   ——   {folder}")
            it.setToolTip(p)
            it.setData(Qt.UserRole, p)
            listw.addItem(it)
        if saves:
            listw.setCurrentRow(0)
        listw.itemDoubleClicked.connect(lambda _: dlg.accept())
        lay.addWidget(listw, 1)

        btn_ok = QPushButton("打开")
        btn_cancel = QPushButton("取消")
        btn_cancel.setObjectName("Ghost")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(btn_ok)
        h.addWidget(btn_cancel)
        lay.addLayout(h)

        if dlg.exec() and listw.currentItem():
            return listw.currentItem().data(Qt.UserRole)
        return None

    def _load_file(self, path):
        """加载指定存档：解析 JSON、自动备份、刷新界面。"""
        try:
            self.file_path = path
            self.log(f"正在打开: {path}")

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.data = json.loads(content)
            self.log("✅ JSON 解析成功")

            # 自动备份
            backup_dir = os.path.join(os.path.dirname(path), "ES3_Backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_name = (f"{os.path.basename(path)}.backup_"
                           f"{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            backup_path = os.path.join(backup_dir, backup_name)
            shutil.copy2(path, backup_path)
            self.log(f"📋 已自动备份到: {backup_path}")

            self.parse_data_to_ui()
            base = os.path.basename(path)
            self.setWindowTitle(f"诈骗园区模拟器 - 存档修改器  —  {base}")
            self.status_lbl.setText(f"已加载: {base}")
            if getattr(self, "mem_save_lbl", None) is not None:
                self._mem_sync_save_label()
            QMessageBox.information(self, "打开成功",
                                    f"存档已加载！\n自动备份已保存到:\n{backup_path}")

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON解析错误",
                                 f"文件不是标准JSON格式！\n错误: {e}\n\n请确认这是ES3导出的JSON存档。")
            self.log(f"❌ JSON解析失败: {e}")
        except Exception as e:
            QMessageBox.critical(self, "打开失败", f"错误: {e}")
            self.log(f"❌ 打开失败: {e}")

    def save_file(self):
        if not self.file_path or self.data is None:
            QMessageBox.warning(self, "未打开文件", "请先打开一个存档文件！")
            return

        try:
            # 1. 集数据
            self.save_ui_to_data()

            # 2. 合并 JSON tab
            self.merge_json_tabs()

            # 3. 再备份
            backup_dir = os.path.join(os.path.dirname(self.file_path), "ES3_Backups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_name = (f"{os.path.basename(self.file_path)}.backup_save_"
                           f"{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            backup_path = os.path.join(backup_dir, backup_name)
            shutil.copy2(self.file_path, backup_path)

            # 4. 写临时文件
            temp_path = self.file_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent="\t")

            # 5. 原子替换
            os.replace(temp_path, self.file_path)

            self.log(f"✅ 保存成功！备份: {backup_name}")
            QMessageBox.information(self, "保存成功",
                                    f"存档已保存！\n同时创建了备份:\n{backup_path}")

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON格式错误",
                                 f"物品/放置物品等标签页的JSON格式有误！\n"
                                 f"请检查各文本框中的JSON语法。\n错误: {e}")
            self.log(f"❌ JSON格式错误: {e}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"错误: {e}")
            self.log(f"❌ 保存失败: {e}")
            if os.path.exists(self.file_path + ".tmp"):
                try:
                    os.remove(self.file_path + ".tmp")
                except Exception:
                    pass

    def save_ui_to_data(self):
        if not isinstance(self.data, dict):
            return
        # 基础数据
        self.es3_set("Currency", safe_float(self.entry_basic["currency"].text()))
        self.es3_set("Level", safe_int(self.entry_basic["level"].text()))
        self.es3_set("Exp", safe_int(self.entry_basic["exp"].text()))
        self.es3_set("Day", safe_int(self.entry_basic["days"].text()))
        self.es3_set("Electricity", safe_int(self.entry_basic["electricity"].text()))
        self.es3_set("ShopName", self.entry_basic["shopName"].text())
        self.es3_set("CallData", safe_int(self.entry_basic["callData"].text(), -1))
        self.es3_set("Difficulty", safe_int(self.entry_basic["difficulty"].text(), 1))

        # 加密货币（表格列: 币种/价格/持有量/均价）
        circ = self.es3_get("CryptoData")
        if isinstance(circ, list) and self.crypto_table.rowCount() == len(circ):
            for i, c in enumerate(circ):
                if not isinstance(c, dict):
                    continue
                it0 = self.crypto_table.item(i, 0)
                it1 = self.crypto_table.item(i, 1)
                it2 = self.crypto_table.item(i, 2)
                it3 = self.crypto_table.item(i, 3)
                c["cryptoName"] = it0.text() if it0 else (c.get("cryptoName", ""))
                c["currentPrice"] = self._to_float(it1.text() if it1 else 0)
                c["coinAmount"] = self._to_int(it2.text() if it2 else 0)
                c["avgBuyPrice"] = self._to_int(it3.text() if it3 else 0)

        # 升级（表格列: 名称[只读]/等级）：
        # 只读名称列不写回；仅当该升级项（按内部英文名）在配置中时，才对等级做上限钳制并写回。
        # 未配置的升级项（如 Upgrade / Tame Speed）保留原样，杜绝"升级丢失"。
        uarr = self.es3_get("Upgrade")
        if isinstance(uarr, list):
            # 先按内部英文名收集界面各行的等级（避免依赖行号与数组下标一一对应）
            table_level = {}
            for r in range(self.upgrade_table.rowCount()):
                it0 = self.upgrade_table.item(r, 0)
                it1 = self.upgrade_table.item(r, 1)
                if it0 is None or it1 is None:
                    continue
                table_level[str(it0.data(Qt.UserRole) or "")] = it1

            for u in uarr:
                if not isinstance(u, dict):
                    continue
                eng = str(u.get("name", ""))
                setup = _upgrade_setup(eng)
                if setup is None or eng not in table_level:
                    continue
                it1 = table_level[eng]
                lv = self._to_int(it1.text() if it1.text() else 0)
                if lv > setup[1]:
                    lv = setup[1]
                u["level"] = lv
                # 让界面等级单元格同步为纠正后的值
                if it1 and it1.text() != str(lv):
                    it1.setText(str(lv))

        # 工人已实时写回 workers，无需再次写（但确保整段写回）
        if self.workers is not None:
            self.es3_set("Workers", self.workers)

    def merge_json_tabs(self):
        """把物品/放置物品列表表格、"其他"页编辑器 合并写入 data。"""
        # 物品 / 放置物品
        for key, table in self._table_keys.items():
            try:
                items = self._list_save(table)
                self.es3_set(key, items)
            except Exception as e:
                self.log(f"⚠️ [{key}] 列表解析失败: {e}")

        # "其他"页当前键
        key = self._other_cur_key
        if key and isinstance(self.data, dict) and key in self.data:
            if self._other_scalar_entry is not None:
                val = self.es3_get(key)
                if isinstance(val, bool):
                    v = self._other_scalar_entry.text()
                    self.es3_set(key, v.lower() in ("true", "1", "yes", "on"))
                elif isinstance(val, (int, float)):
                    v = self._other_scalar_entry.text()
                    self.es3_set(key, self._to_float(v) if isinstance(val, float)
                                 else self._to_int(v))
                else:
                    self.es3_set(key, self._other_scalar_entry.text())
            elif self._other_stack.currentIndex() == 1:
                # 列表表格
                try:
                    self.es3_set(key, self._list_save(self.other_table))
                except Exception as e:
                    self.log(f"⚠️ [{key}] 解析失败: {e}")
            elif self._other_stack.currentIndex() == 2:
                # JSON
                raw = self.other_json.toPlainText().strip()
                if raw:
                    self.es3_set(key, json.loads(raw))

    # ==================== 解析进界面 ====================
    def parse_data_to_ui(self):
        if not self.data:
            return

        # 基础数据
        self.entry_basic["currency"].setText(str(self.es3_get("Currency") or 0))
        self.entry_basic["level"].setText(str(self.es3_get("Level") or 1))
        self.entry_basic["exp"].setText(str(self.es3_get("Exp") or 0))
        self.entry_basic["days"].setText(str(self.es3_get("Day") or 0))
        self.entry_basic["electricity"].setText(str(self.es3_get("Electricity") or 0))
        self.entry_basic["shopName"].setText(str(self.es3_get("ShopName") or ""))
        self.entry_basic["callData"].setText(str(self.es3_get("CallData") if self.es3_get("CallData") is not None else -1))
        self.entry_basic["difficulty"].setText(str(self.es3_get("Difficulty") or 1))

        # 加密货币
        self.load_crypto_ui()

        # 升级
        self.load_upgrade_ui()

        # 物品 / 放置物品 → 列表表格
        self._list_load(self.items_table, self.es3_get("Items"))
        self._list_load(self.placed_table, self.es3_get("PlaceItems"))

        # 银行债务 / 剧情解锁 / 教程解锁 → 列表表格
        self._list_load(self.debt_table, self.es3_get("Debt"))
        self._list_load(self.story_table, self.es3_get("MissionProgress"))
        self._list_load(self.tutorial_table, self.es3_get("TutorialSaveData"))

        # "其他"页：重建键选择下拉（按原存档 key 顺序）
        self.other_key_box.blockSignals(True)
        self.other_key_box.clear()
        for k, node in self.data.items():
            if isinstance(node, dict) and "value" in node:
                self.other_key_box.addItem(k, k)
        self.other_key_box.blockSignals(False)
        if self.other_key_box.count():
            self.other_key_box.setCurrentIndex(0)
        self._render_other_key()

        # 工人
        self.load_workers()

    # ---------- 加密货币 ----------
    def load_crypto_ui(self):
        arr = self.es3_get("CryptoData")
        self.crypto_table.setRowCount(0)
        if not isinstance(arr, list):
            return
        for c in arr:
            if not isinstance(c, dict):
                continue
            row = self.crypto_table.rowCount()
            self.crypto_table.insertRow(row)
            self.crypto_table.setItem(row, 0, QTableWidgetItem(str(c.get("cryptoName", ""))))
            self.crypto_table.setItem(row, 1, QTableWidgetItem(str(c.get("currentPrice", 0))))
            self.crypto_table.setItem(row, 2, QTableWidgetItem(str(c.get("coinAmount", 0))))
            self.crypto_table.setItem(row, 3, QTableWidgetItem(str(c.get("avgBuyPrice", 0))))

    # ---------- 升级 ----------
    def load_upgrade_ui(self):
        arr = self.es3_get("Upgrade")
        self.upgrade_table.setRowCount(0)
        if not isinstance(arr, list):
            return
        for u in arr:
            if not isinstance(u, dict):
                continue
            eng = str(u.get("name", ""))
            setup = _upgrade_setup(eng)
            row = self.upgrade_table.rowCount()
            self.upgrade_table.insertRow(row)
            # 名称列只读；按内部英文名映射到中文，未映射则原样显示英文
            display = setup[0] if setup else eng
            inm = QTableWidgetItem(display)
            inm.setFlags(inm.flags() & ~Qt.ItemIsEditable)
            inm.setData(Qt.UserRole, eng)  # 保留内部英文名，供保存/钳制使用
            self.upgrade_table.setItem(row, 0, inm)
            lv = self._to_int(u.get("level", 0))
            if setup and lv > setup[1]:
                lv = setup[1]
            self.upgrade_table.setItem(row, 1, QTableWidgetItem(str(lv)))

    def _upgrade_max_all(self):
        """一键升级：把所有已配置升级项（按内部英文名在 UPGRADE_MAP 中）置为满级。"""
        row = self.upgrade_table.rowCount()
        self._upgrade_clamping = True
        try:
            for r in range(row):
                it0 = self.upgrade_table.item(r, 0)
                if it0 is None:
                    continue
                setup = _upgrade_setup(str(it0.data(Qt.UserRole) or ""))
                if setup is None:
                    continue
                self.upgrade_table.item(r, 1).setText(str(setup[1]))
        finally:
            self._upgrade_clamping = False

    def _on_upgrade_level_edit(self, item):
        """升级等级列：输入超上限时，立即把格子内容纠正为上限（直接替换用户输入）。"""
        if item is None or item.column() != 1:
            return
        it0 = self.upgrade_table.item(item.row(), 0)
        if it0 is None:
            return
        setup = _upgrade_setup(str(it0.data(Qt.UserRole) or ""))
        if setup is None:
            return
        txt = item.text().strip()
        if not txt.isdigit():
            return
        lv = int(txt)
        if lv > setup[1] and not self._upgrade_clamping:
            self._upgrade_clamping = True
            try:
                item.setText(str(setup[1]))
            finally:
                self._upgrade_clamping = False

    # ---------- 工人 ----------
    def load_workers(self):
        arr = self.es3_get("Workers")
        self.workers = arr if isinstance(arr, list) else []
        self.current_worker = None
        self.refresh_worker_list()

    def worker_display(self, w, idx):
        npc = w.get("npcDataRole") if isinstance(w, dict) else None
        name = npc.get("npcName") if isinstance(npc, dict) else ""
        return name or f"工人 #{idx}"

    def refresh_worker_list(self):
        self.worker_list.blockSignals(True)
        self.worker_list.clear()
        query = self.search_entry.text().strip().lower()
        shown = 0
        for i, w in enumerate(self.workers):
            text = self.worker_display(w, i).lower()
            if query == "" or query in text:
                self.worker_list.addItem(self.worker_display(w, i))
                shown += 1
        self.worker_list.blockSignals(False)
        self.count_lbl.setText(f"共 {len(self.workers)} 个工人")

    def filter_workers(self):
        self.refresh_worker_list()

    def on_worker_select(self, row):
        if row < 0 or row >= len(self.workers):
            self.current_worker = None
            return
        self.current_worker = row
        self.load_worker_to_ui(self.workers[row])

    def load_worker_to_ui(self, worker):
        npc = worker.get("npcDataRole") if isinstance(worker, dict) else {}
        if not isinstance(npc, dict):
            npc = {}
        name = npc.get("npcName", f"工人 #{worker.get('_index', '')}")

        self.worker_title.setText(f"👤 {name}")

        # 金钱
        self.worker_entries["money"].setText(str(npc.get("money", 0)))

        # 能力值
        abilities = npc.get("abilities") if isinstance(npc.get("abilities"), list) else []
        ab_map = {}
        for ab in abilities:
            if isinstance(ab, dict):
                key = str(ab.get("abilityName", "")).lower()
                ab_map[key] = ab
        self.worker_entries["intelligence"].setText(str(ab_map.get("intelligence", {}).get("value", 0)))
        self.worker_entries["strength"].setText(str(ab_map.get("strength", {}).get("value", 0)))
        self.worker_entries["focus"].setText(str(ab_map.get("focus", {}).get("value", 0)))

        # 状态
        for k in ("sickValue", "starveValue", "thirstValue", "sanityValue", "tameProgress"):
            self.worker_entries[k].setText(str(worker.get(k, 0)))

        # 复选框
        self.cb_tamed.blockSignals(True)
        self.cb_dead.blockSignals(True)
        self.cb_tamed.setChecked(safe_bool(worker.get("isTamed", False)))
        self.cb_dead.setChecked(safe_bool(worker.get("isDead", False)))
        self.cb_tamed.blockSignals(False)
        self.cb_dead.blockSignals(False)

    def current_worker_dict(self):
        if self.current_worker is None or self.current_worker >= len(self.workers):
            return None
        return self.workers[self.current_worker]

    def on_worker_field_changed(self, key):
        w = self.current_worker_dict()
        if w is None or self.worker_entries.get(key) is None:
            return
        if key == "money":
            npc = w.setdefault("npcDataRole", {})
            if not isinstance(npc, dict):
                npc = w["npcDataRole"] = {}
            npc["money"] = safe_float(self.worker_entries["money"].text())
        elif key in ("intelligence", "strength", "focus"):
            npc = w.setdefault("npcDataRole", {})
            if not isinstance(npc, dict):
                npc = w["npcDataRole"] = {}
            abilities = npc.setdefault("abilities", [])
            if not isinstance(abilities, list):
                abilities = npc["abilities"] = []
            ab_map = {str(a.get("abilityName", "")).lower(): a
                      for a in abilities if isinstance(a, dict)}
            # 力量上限80：输入超过80则强制钳制到80
            if key == "strength":
                STRENGTH_MAX = 80
                val = min(safe_float(self.worker_entries[key].text()), STRENGTH_MAX)
                self.worker_entries["strength"].blockSignals(True)
                self.worker_entries["strength"].setText(str(val))
                self.worker_entries["strength"].blockSignals(False)
            else:
                val = safe_float(self.worker_entries[key].text())
            cap = key.capitalize()
            if key in ab_map:
                ab_map[key]["value"] = val
            else:
                abilities.append({
                    "abilityName": cap, "minValue": 1, "maxValue": 4,
                    "value": val})
        else:
            w[key] = safe_float(self.worker_entries[key].text())

    def on_worker_checkbox_changed(self):
        w = self.current_worker_dict()
        if w is None:
            return
        w["isTamed"] = self.cb_tamed.isChecked()
        w["isDead"] = self.cb_dead.isChecked()

    def max_all_workers(self):
        if not self.workers:
            return
        try:
            for w in self.workers:
                if not isinstance(w, dict):
                    continue
                npc = w.setdefault("npcDataRole", {})
                if not isinstance(npc, dict):
                    npc = w["npcDataRole"] = {}
                abilities = npc.setdefault("abilities", [])
                if not isinstance(abilities, list):
                    abilities = npc["abilities"] = []
                ab_map = {str(a.get("abilityName", "")).lower(): a
                          for a in abilities if isinstance(a, dict)}
                for name in ("Intelligence", "Strength", "Focus"):
                    key = name.lower()
                    if key in ab_map:
                        ab_map[key]["value"] = 9999.0
                    else:
                        abilities.append({"abilityName": name, "minValue": 1,
                                          "maxValue": 4, "value": 9999.0})
                w["sickValue"] = 0
                w["starveValue"] = 0
                w["thirstValue"] = 0
                w["sanityValue"] = 999.0
                w["tameProgress"] = 100
                w["isTamed"] = True
                w["isDead"] = False
            self.log("✅ 已全部加满所有工人属性")
            if self.current_worker is not None:
                self.load_worker_to_ui(self.workers[self.current_worker])
        except Exception as e:
            self.log(f"❌ 批量修改失败: {e}")

    def reset_workers_status(self):
        if not self.workers:
            return
        try:
            for w in self.workers:
                if not isinstance(w, dict):
                    continue
                w["sickValue"] = 0
                w["thirstValue"] = 0
                w["starveValue"] = 0
            self.log("✅ 已重置所有工人状态（疾病/饥饿/口渴清零）")
            if self.current_worker is not None:
                self.load_worker_to_ui(self.workers[self.current_worker])
        except Exception as e:
            self.log(f"❌ 重置失败: {e}")

    def copy_worker(self):
        """复制当前选中的员工。新员工 ID 重新生成（随机或按新名字计算），
        避免与原件 ID 冲突；复制后仅改内存(self.workers + 列表)，需点【保存】写盘。"""
        src = self.current_worker_dict()
        if src is None or not isinstance(src, dict):
            QMessageBox.information(self, "未选择", "请先在左侧选择一个要复制的工人。")
            return
        base_npc = src.get("npcDataRole") if isinstance(src.get("npcDataRole"), dict) else {}
        base_name = str(base_npc.get("npcName", "工人"))

        # 复制选项对话框
        dlg = QDialog(self)
        dlg.setWindowTitle("📋 复制员工")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 14)

        lay.addWidget(QLabel(f"复制　{base_name}　→ 生成新员工："))
        form = QGridLayout(); form.setSpacing(8)
        form.addWidget(QLabel("复制份数"), 0, 0)
        spin = QSpinBox(); spin.setRange(1, 50); spin.setValue(1)
        form.addWidget(spin, 0, 1)
        form.addWidget(QLabel("新名字(留空=沿用原名)"), 1, 0)
        name_edit = QLineEdit(); name_edit.setPlaceholderText(f"{base_name}")
        form.addWidget(name_edit, 1, 1)
        form.addWidget(QLabel("ID 生成方式"), 2, 0)
        combo = QComboBox()
        combo.addItem("随机生成 (不冲突)")
        combo.addItem("按名字生成 (同名同ID)")
        form.addWidget(combo, 2, 1)
        lay.addLayout(form)

        btns = QHBoxLayout()
        ok = QPushButton("复制")
        cancel = QPushButton("取消"); cancel.setObjectName("Ghost")
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)

        if not (dlg.exec() and spin.value() >= 1):
            return

        n = spin.value()
        name_or_empty = name_edit.text().strip()
        by_name = combo.currentIndex() == 1
        added = 0
        for i in range(n):
            cp = copy.deepcopy(src)
            nm = name_or_empty or base_name
            if n > 1:
                nm = f"{nm} 副本{i + 1}"
            npc = cp.setdefault("npcDataRole", {})
            if not isinstance(npc, dict):
                npc = cp["npcDataRole"] = {}
            npc["npcName"] = nm
            if by_name:
                cp["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, nm))
            else:
                cp["id"] = str(uuid.uuid4())
            # 新员工未放置/未生成，避免直接卡在原本位置
            cp["isSpawned"] = False
            self.workers.append(cp)
            added += 1

        self.refresh_worker_list()
        self.worker_list.setCurrentRow(len(self.workers) - 1)   # 选中最前端一个副本
        self.count_lbl.setText(f"共 {len(self.workers)} 个工人")
        self.log(f"📋 已复制 {added} 个员工（{'按名字生成ID' if by_name else '随机ID'}）。"
                 "记得点【保存】写盘生效。")
        self.status_lbl.setText(f"已复制 {added} 个员工，记得点【保存】写盘生效。")

    # ==================== 备份目录 ====================
    def open_backup_dir(self):
        if self.file_path:
            backup_dir = os.path.join(os.path.dirname(self.file_path), "ES3_Backups")
            if os.path.exists(backup_dir):
                os.startfile(backup_dir)
            else:
                QMessageBox.information(self, "备份目录", "尚未创建备份目录。打开存档后会自动创建。")
        else:
            QMessageBox.information(self, "备份目录", "请先打开一个存档文件。")


# ==================== 启动 ====================
def main():
    import sys
    import os
    app = QApplication(sys.argv)
    app.setStyleSheet(build_qss(LIGHT_THEME))
    app.setFont(QFont("Microsoft YaHei UI", 10))

    # 设置程序图标（exe/窗口图标来自 icon.ico）
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(icon_path):
        ico = QIcon(icon_path)
        app.setWindowIcon(ico)
        win = ES3Editor()
        win.setWindowIcon(ico)
    else:
        win = ES3Editor()

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()