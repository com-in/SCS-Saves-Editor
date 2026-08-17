#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诈骗园区模拟器 - ES3存档修改器 (PySide6版)
功能: 安全编辑Unity ES3 JSON存档(真实ES3结构)，自动备份，防闪退
适配结构: 顶层 key -> {"__type":..., "value":...}
"""
import os
import shutil
import json
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QListWidget, QTextEdit, QPlainTextEdit,
    QPushButton, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QSplitter, QFrame, QStatusBar, QToolButton,
    QStackedWidget, QListWidgetItem, QSizePolicy,
)
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap
from PySide6.QtCore import Qt, QVariantAnimation, QEasingCurve, QTimer, QSize

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
        self.tab_other = QWidget()

        for page in (self.tab_basic, self.tab_workers, self.tab_crypto,
                     self.tab_items, self.tab_placed, self.tab_upgrade, self.tab_other):
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
        self.build_json_tab()  # 物品/放置/其他

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

    def on_nav_item_clicked(self, item):
        # 点击菜单最下面的折叠/展开行
        if self.nav_list.row(item) == self._fold_row:
            self.toggle_sidebar()

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

        self.upgrade_table = QTableWidget(0, 2)
        self.upgrade_table.setHorizontalHeaderLabels(["升级项", "等级 level"])
        self.upgrade_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.upgrade_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        lay.addWidget(self.upgrade_table)

        hint = QLabel("⚠️ 可在【等级】列直接修改数值，保存时写入存档。")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

    # ---------- 物品 / 放置物品 / 其他（JSON 编辑） ----------
    def build_json_tab(self):
        # 物品
        lay = QVBoxLayout(self.tab_items)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        self.items_text = QPlainTextEdit()
        self.items_text.setFont(QFont("Consolas", 10))
        lay.addWidget(self.items_text)
        h = QLabel("⚠️ 原始 JSON，仅当了解结构时修改。保存前会校验 JSON。")
        h.setObjectName("Hint")
        lay.addWidget(h)

        # 放置物品
        lay = QVBoxLayout(self.tab_placed)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        self.placed_text = QPlainTextEdit()
        self.placed_text.setFont(QFont("Consolas", 10))
        lay.addWidget(self.placed_text)
        h = QLabel("⚠️ 原始 JSON，仅当了解结构时修改。保存前会校验 JSON。")
        h.setObjectName("Hint")
        lay.addWidget(h)

        # 其他（只读）
        lay = QVBoxLayout(self.tab_other)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        self.other_text = QPlainTextEdit()
        self.other_text.setFont(QFont("Consolas", 10))
        self.other_text.setReadOnly(True)
        lay.addWidget(self.other_text)

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
        btn_reset.setObjectName("Ghost")
        btn_max.clicked.connect(self.max_all_workers)
        btn_reset.clicked.connect(self.reset_workers_status)

        self.count_lbl = QLabel("共 0 个工人")
        self.count_lbl.setObjectName("Muted")
        top.addWidget(self.search_entry, 1)
        top.addWidget(self.count_lbl)
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

        # 工人已实时写回 workers，无需再次写（但确保整段写回）
        if self.workers is not None:
            self.es3_set("Workers", self.workers)

    def merge_json_tabs(self):
        def try_parse(text):
            raw = text.toPlainText().strip()
            if not raw or raw.startswith("//"):
                return None
            return json.loads(raw)

        # 物品
        try:
            items = try_parse(self.items_text)
            if items is not None:
                self.es3_set("Items", items)
        except Exception:
            pass

        # 放置物品
        try:
            placed = try_parse(self.placed_text)
            if placed is not None:
                self.es3_set("PlaceItems", placed)
        except Exception:
            pass

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

        # JSON tabs（真实 value 段）
        def set_json(txt, val):
            txt.setPlainText(
                json.dumps(val, ensure_ascii=False, indent="\t") if val is not None else "// 无数据")

        set_json(self.items_text, self.es3_get("Items"))
        set_json(self.placed_text, self.es3_get("PlaceItems"))

        # 其他（整个结构，只读）
        self.other_text.setPlainText(
            json.dumps(self.data, ensure_ascii=False, indent="\t"))

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
            row = self.upgrade_table.rowCount()
            self.upgrade_table.insertRow(row)
            self.upgrade_table.setItem(row, 0, QTableWidgetItem(str(u.get("name", ""))))
            self.upgrade_table.setItem(row, 1, QTableWidgetItem(str(u.get("level", 0))))

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