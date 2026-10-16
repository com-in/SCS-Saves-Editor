#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诈骗园区模拟器 - ES3存档修改器 (PySide6版)
功能: 安全编辑Unity ES3 JSON存档(真实ES3结构)，自动备份，防闪退
适配结构: 顶层 key -> {"__type":..., "value":...}
"""
# =====================================================================
# Copyright (C) 2026 com-in
# 项目仓库: https://github.com/com-in/SCS-Saves-Editor
# 本程序依照 GNU 通用公共许可证 v3（或更高版本）发布。
# 严禁删除或遮蔽本版权声明；任何二次发布/修改/再分发必须遵守 GPLv3
# 并保留原作者署名。任何未经授权移除署名、抄袭、窜改归属的行为均属侵权。
# 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9（仅为版权署名追踪标识，无任何功能）
# =====================================================================
import os
import time
import shutil
import json
import copy
import uuid
import threading
import math
import statistics
from datetime import datetime

from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QListWidget, QTextEdit, QPlainTextEdit,
    QPushButton, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem,
    QFileDialog, QMessageBox, QSplitter, QFrame, QStatusBar, QToolButton,
    QStackedWidget, QListWidgetItem, QSizePolicy, QComboBox, QDialog, QSpinBox,
    QProgressBar, QMenu,
)
from PySide6.QtGui import QFont, QIcon, QColor, QPixmap, QPolygon
from PySide6.QtCore import Qt, QSignalBlocker, QVariantAnimation, QEasingCurve, QTimer, QSize, QThread, Signal, QSettings, QPoint, QStandardPaths

from _memscan import MemScanner, find_game_process
from _role_data import ROLE_NAME as _ROLE_NAME  # 员工职业 id->中文名 映射（混淆数据）
from _item_data import USER_ITEM_NAME as _ITEM_NAME  # 物品 id->中文名 映射（混淆数据）
from _item_labels import item_label, item_sort_key
from _search_combo import SearchComboBox
from _extra_pages import ExtraPagesMixin
from _mods_page import ModsPageMixin
from _updates import UpdateMixin
from _document import DocumentMixin
from _editor_ui import EditorUiMixin
from _save_support import number, integer_list, validate_document, validate_changes, atomic_write
from _map_items import quaternion, yaw_rotation, heading, rotate_world_y, box_corners, world_corners

# ==================== 主题配置 ====================
# 默认亮色
BG_COLOR = "#f5f6fa"
CARD_BG = "#ffffff"
ENTRY_BG = "#ffffff"
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
    "CARD_BG": "#272a3d",
    "ENTRY_BG": "#222537",
    "TEXT_COLOR": "#cdd6f4",
    "TEXT_SECOND": "#a6adc8",
    "ACCENT": "#89b4fa",
    "ACCENT_HOVER": "#b4befe",
    "SUCCESS": "#a6e3a1",
    "WARNING": "#f9e2af",
    "DANGER": "#f38ba8",
    "BORDER": "#313244",
}

# ==================== UI 统一规范常量 ====================
ROUNDED_CORNER = 10      # 卡片/面板统一圆角半径(px)
PAGE_MARGIN = 16         # 页面统一内容边距(px)
SECTION_SPACING = 12     # 页面内节/元素统一间距(px)
TABLE_FIXED_HEIGHT = 220 # 列表表格统一最大高度(px)

def build_qss(theme):
    """根据主题字典生成完整 QSS，避免各处内联散落样式"""
    BG = theme["BG_COLOR"]; CARD = theme["CARD_BG"]; ENTRY = theme["ENTRY_BG"]
    T = theme["TEXT_COLOR"]; TS = theme["TEXT_SECOND"]
    ACC = theme["ACCENT"]; ACH = theme["ACCENT_HOVER"]
    S = theme["SUCCESS"]; W = theme["WARNING"]; D = theme["DANGER"]; BD = theme["BORDER"]
    RC = ROUNDED_CORNER  # 统一圆角半径
    return f"""
* {{ font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; }}
QMainWindow {{ background: {BG}; }}
QWidget {{ background: {BG}; color: {T}; font-size: 13px; }}
QWidget#ValueRow {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLabel#CardTitle {{ color: {T}; font-weight: bold; font-size: 14px; }}
QLabel#Hint {{ color: {W}; font-size: 12px; }}
QLabel#PageTitle {{ color: {T}; font-size: 20px; font-weight: bold; }}
QLabel#ModsScopeBadge {{
    color: {ACC}; background: {ENTRY}; border: 1px solid {ACC};
    border-radius: 10px; padding: 4px 10px; font-size: 12px; font-weight: bold;
}}
QLabel#ModsSectionCaption {{ color: {TS}; font-size: 12px; }}
QLabel#ModsFieldLabel {{ color: {TS}; font-size: 12px; font-weight: bold; min-width: 34px; }}
QLabel#ModsProgressTitle {{ color: {T}; font-size: 12px; font-weight: bold; }}
QFrame#ModsProgressBox {{ background: {CARD}; border: 1px solid {BD}; border-radius: 8px; }}
QLabel#PageSub {{ color: {TS}; font-size: 12px; }}
QLabel#Muted {{ color: {TS}; font-size: 12px; }}
QLabel#SideTitle {{ color: {T}; font-weight: bold; font-size: 15px; }}
QLabel#WelcomeTitle {{ color: {T}; font-size: 26px; font-weight: bold; }}
QLabel#SectionTitle {{ color: {T}; font-weight: bold; font-size: 14px; }}

QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {ENTRY}; color: {T};
    border: 1px solid {BD}; border-radius: {RC}px;
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
QStatusBar QPushButton#Ghost {{ padding: 2px 10px; }}
QPushButton#WelcomeCard {{
    background: {CARD}; color: {T}; border: 1px solid {BD};
    border-radius: 12px; padding: 16px 18px; font-weight: bold;
    font-size: 14px; text-align: left; min-height: 44px;
}}
QPushButton#WelcomeCard:hover {{ border: 1px solid {ACC}; background: {ENTRY}; }}
QToolButton#Ghost {{ background: {CARD}; color: {T}; border: 1px solid {BD}; border-radius: 6px; }}
QToolButton#Ghost:hover {{ border: 1px solid {ACC}; background: {ENTRY}; }}
QToolButton#NavFold {{ background: {CARD}; color: {TS}; border: 1px solid {BD}; border-radius: {RC}px; padding: 0 10px; text-align: left; }}
QToolButton#NavFold:hover {{ border: 1px solid {ACC}; color: {T}; background: {ENTRY}; }}

QListWidget {{
    background: {ENTRY}; border: 1px solid {BD}; border-radius: 6px;
    padding: 4px; outline: 0;
}}
QListWidget::item {{ padding: 8px 10px; border-radius: 4px; }}
QListWidget::item:selected {{ background: {ACC}; color: {BG}; }}
QListWidget::item:hover:!selected {{ background: {CARD}; }}

QTreeWidget#Nav {{
    background: {CARD}; border: 1px solid {BD}; border-radius: {RC}px;
    padding: 6px; outline: 0; color: {T}; font-size: 13px;
}}
QTreeWidget#Nav::item {{
    padding: 8px 10px; border-radius: {RC}px; margin: 1px 0;
}}
QTreeWidget#Nav::item:hover {{ background: {ENTRY}; }}
QTreeWidget#Nav::item:selected {{
    background: {ACC}; color: {BG}; font-weight: bold;
}}
QTreeWidget#Nav::branch {{ background: transparent; image: none; }}

QLabel#MetricValue {{ font-size: 24px; font-weight: bold; color: {ACC}; }}
QFrame#DocumentBar {{ background: {CARD}; border: 1px solid {BD}; border-radius: 10px; }}
QLabel#DocumentBadge {{ color: {S}; background: {CARD}; border: 1px solid {BD}; border-radius: 10px; padding: 4px 10px; }}
QLabel#DocumentBadge[dirty="true"] {{ color: {W}; border-color: {W}; }}
QFrame#CardBox {{ background: {CARD}; border: 1px solid {BD}; border-radius: 8px; }}
QFrame#FieldBox {{ background: {CARD}; border: 1px solid {BD}; border-radius: 6px; }}

QFrame#ToolPanel {{ background: {CARD}; border: 1px solid {BD}; border-radius: 10px; }}
QWidget#PanelBody {{ background: transparent; }}
QLabel#PanelTitle {{ color: {T}; font-size: 13px; font-weight: bold; }}
QLabel#EmptyTitle {{ color: {TS}; font-size: 15px; font-weight: bold; }}
QLabel#StatusChip {{ background: {BG}; color: {TS}; border: 1px solid {BD}; border-radius: 6px; padding: 4px 8px; }}
QLabel#StatusChip[active="true"] {{ color: {ACC}; border-color: {ACC}; }}
QWidget#MapPage QPushButton, QWidget#MemoryPage QPushButton, QWidget#ModsPage QPushButton {{ padding: 7px 12px; }}
QPushButton#Secondary {{ background: {ENTRY}; color: {T}; border: 1px solid {BD}; }}
QPushButton#Secondary:hover {{ border-color: {ACC}; color: {ACC}; }}
QPushButton#ModeButton {{ background: {CARD}; color: {ACC}; border: 1px solid {ACC}; }}
QPushButton#ModeButton:checked, QPushButton#Secondary:checked {{ background: {ACC}; color: {BG}; }}
QWidget#MapPage QPushButton:disabled, QWidget#MemoryPage QPushButton:disabled, QWidget#ModsPage QPushButton:disabled {{
    background: {BG}; color: {TS}; border: 1px solid {BD};
}}
QWidget#MemoryPage QPushButton#Ghost:checked {{ background: {ACC}; color: {BG}; border-color: {ACC}; }}
QWidget#MapPage QToolButton {{ background: {CARD}; color: {T}; border: 1px solid {BD}; border-radius: 6px; padding: 7px 10px; }}
QWidget#MapPage QToolButton:hover {{ border-color: {ACC}; }}
QMenu {{ background: {CARD}; color: {T}; border: 1px solid {BD}; padding: 5px; }}
QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACC}; color: {BG}; }}
QTreeWidget#MemoryResults {{
    background: {ENTRY}; alternate-background-color: {BG}; color: {T};
    border: 1px solid {BD}; border-radius: 6px; outline: none;
    selection-background-color: {ACC}; selection-color: {BG};
}}
QTreeWidget#MemoryResults::item {{ padding: 3px 0; }}
QProgressBar {{ border: none; border-radius: 3px; background: {BG}; max-height: 6px; }}
QProgressBar::chunk {{ background: {ACC}; border-radius: 3px; }}
QProgressBar#ModsTaskProgress {{
    min-height: 24px; max-height: 32px; border: 1px solid {BD};
    background: {ENTRY}; color: {T}; text-align: center; border-radius: 4px;
}}

QTableWidget {{
    background: {ENTRY}; border: 1px solid {BD}; border-radius: 6px;
    alternate-background-color: {BG}; gridline-color: {BD}; selection-background-color: {ACC}; selection-color: {BG};
}}
QHeaderView::section {{
    background: {CARD}; color: {T}; padding: 6px; border: none;
    border-bottom: 1px solid {BD}; font-weight: bold;
}}
QComboBox {{
    background: {ENTRY}; color: {T};
    border: 1px solid {BD}; border-radius: 6px;
    padding: 6px 8px; selection-background-color: {ACC};
}}
QComboBox:focus {{ border: 1px solid {ACC}; }}
QComboBox::drop-down {{
    border: none; width: 26px;
}}
QComboBox::down-arrow {{
    image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSI4IiB2aWV3Qm94PSIwIDAgMTIgOCI+PHBhdGggZD0iTTEgMWw1IDUgNS01IiBmaWxsPSJub25lIiBzdHJva2U9IiM4OWI0ZmEiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);
    width: 12px; height: 8px;
}}
QComboBox QAbstractItemView {{
    background: {CARD}; color: {T}; border: 1px solid {BD};
    selection-background-color: {ACC}; selection-color: {BG}; outline: 0;
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
#   中文显示名, 最高等级上限。未在映射里的项（如 Upgrade）一律不改动。
UPGRADE_MAP = {
    "Cleaner": ("清洁工具", 1),
    "Scam Sticker": ("诈骗广告贴纸", 5),
    "Trolley": ("手推车", 3),
    "Multigrab": ("多重抓取", 3),
    "Stamina": ("耐力", 3),
    "Hit Power": ("击倒力量", 4),
    "Electricity Capacity": ("电力容量", 6),
    "Whip": ("鞭子", 4),
    "Weapon": ("武器", 4),
    "Tame Speed": ("驯服速度", 4),
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


class Map3DWidget(QWidget):
    """轻量级存档坐标 3D 预览（无需额外 OpenGL/绘图库）。"""
    selection_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.point_details = {}
        self.hovered_point = None
        self.scene = None
        self.placement_enabled = False
        self.placement_callback = None
        self.move_callback = None
        self.rotate_callback = None
        self.delete_callback = None
        self.floor_changed_callback = None
        self.preview_point = None
        self.preview_yaw = 0.0
        self.preview_item_id = None
        self._points_revision = 0
        self._drag_marker = None
        self._drag_start = None
        self._drag_offset = None
        self.selected_marker = None
        self._bounds_cache = None
        self._bounds_cache_key = None
        self._framing_bounds = None
        self._projected_tri_cache = None
        self._projected_tri_cache_key = None
        self._clean_cache_key = None
        self._floor_cache_key = None
        self._point_floor_cache_key = None
        self._point_floor_cache = {}
        self._projection_cache_key = None
        self._marker_cache_key = None
        self._item_geometry_cache = {}
        self._item_render_cache_key = None
        self._item_render_cache = {}
        self._scene_render_cache = None
        self._scene_geometry_cache = None
        self.view_mode = "save"
        self.floor_mode = "current"
        self.floor_levels = []
        self.floor_index = 0
        self.yaw, self.pitch, self.zoom = -20.0, 72.0, 1.0
        self.pan_x = self.pan_y = 0.0
        self._pan_last = None
        self._last = None
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_points(self, points, details=None, preserve_view=False):
        previous = self._scene_bounds() if preserve_view else None
        if not preserve_view:
            self._clear_map_selection()
        self._framing_bounds = previous[:7] if previous else None
        self.points = points or []
        self.point_details = details or {}
        self.hovered_point = None
        self._points_revision += 1
        self._item_geometry_cache.clear()
        self._bounds_cache_key = None
        self.update()

    def set_scene(self, scene):
        self.scene = scene
        self._point_floor_cache_key = self._floor_cache_key = None
        self._framing_bounds = None
        self._clear_map_selection()
        self._scene_render_cache = self._scene_geometry_cache = None
        self._marker_cache_key = None
        self._item_geometry_cache.clear()
        self._item_render_cache_key = None
        self.floor_levels = list(scene.get("floor_levels", []))
        self.floor_index = self._nearest_floor_index()
        self.floor_mode = "level"
        self._bounds_cache_key = None
        self._projected_tri_cache_key = None
        self.update()

    def set_view_mode(self, mode):
        self.view_mode = mode
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0.0
        self._framing_bounds = None
        self.preview_point = None
        self._bounds_cache_key = self._projected_tri_cache_key = None
        self.update()

    def set_floor_mode(self, mode):
        self.floor_mode = mode
        self._clear_map_selection()
        self._bounds_cache_key = None
        self._projected_tri_cache_key = None
        self.update()

    def _nearest_floor_index(self):
        if not self.floor_levels:
            return 0
        reference = self._save_floor_reference()
        return min(range(len(self.floor_levels)), key=lambda i: abs(self.floor_levels[i] - reference))

    def _save_floor_reference(self):
        heights = [self._point_floor_height(p) for p in self._clean_points() if p[3] == "放置物品"]
        return statistics.median(heights) if heights else -1.5

    def set_floor_index(self, index):
        if not self.floor_levels:
            return
        self.floor_index = max(0, min(len(self.floor_levels) - 1, int(index)))
        self.floor_mode = "level"
        self._clear_map_selection()
        self._projected_tri_cache_key = None
        self.update()
        if self.floor_changed_callback:
            self.floor_changed_callback(self.floor_index, len(self.floor_levels), self.floor_levels[self.floor_index])

    def step_floor(self, delta):
        self.set_floor_index(self.floor_index + int(delta))

    def _clear_map_selection(self):
        self.selected_marker = self._drag_marker = self.hovered_point = None
        self.selection_changed.emit(None)
        self._drag_start = self._drag_offset = None
        self.preview_point = self._last = None
        self._pan_last = None
        self.setCursor(Qt.CrossCursor if self.placement_enabled else Qt.ArrowCursor)

    def set_camera_preset(self, mode):
        self.yaw, self.pitch = (0.0, 90.0) if mode == "top" else (-25.0, 55.0)
        self.preview_point = None
        self._projected_tri_cache_key = None
        self.update()

    def _floor_reference(self):
        if self.floor_mode == "level" and self.floor_levels:
            return self.floor_levels[self.floor_index]
        key = (self._points_revision, self.floor_mode, tuple(self.floor_levels))
        if self._floor_cache_key == key:
            return self._floor_cache
        base = self._save_floor_reference()
        if self.floor_levels:
            nearest = min(range(len(self.floor_levels)), key=lambda i: abs(self.floor_levels[i] - base))
            if self.floor_mode == "upper":
                nearest = min(nearest + 1, len(self.floor_levels) - 1)
            result = self.floor_levels[nearest]
        else:
            result = base + (3.5 if self.floor_mode == "upper" else 0.0)
        self._floor_cache_key, self._floor_cache = key, result
        return result

    def _visible_scene_objects(self, kind):
        reference = self._floor_reference()
        for obj in (self.scene or {}).get("objects", []):
            if obj.get("kind") != kind:
                continue
            if self.floor_mode == "level":
                if kind == "floor" and abs(self._scene_floor_height(obj)-reference) > 0.35:
                    continue
                if kind == "wall" and not self._wall_matches_floor(obj, reference):
                    continue
            elif self.floor_mode != "all":
                if kind == "floor" and abs(self._scene_floor_height(obj)-reference) > 1.6:
                    continue
                if kind == "wall" and not self._wall_matches_floor(obj, reference):
                    continue
            yield obj

    @staticmethod
    def _scene_floor_height(obj):
        quad = obj.get("quad") or ()
        ys = [float(vertex[1]) for vertex in quad if len(vertex) > 1]
        return sum(ys) / len(ys) if ys else float(obj.get("base_y", 0.0))

    @classmethod
    def _wall_span(cls, obj):
        quad = obj.get("quad") or ()
        ys = [float(vertex[1]) for vertex in quad if len(vertex) > 1]
        if not ys:
            base = float(obj.get("base_y", 0.0))
            return base, base
        return min(float(obj.get("base_y", min(ys))), min(ys)), max(ys)

    @classmethod
    def _wall_matches_floor(cls, obj, reference):
        base, top = cls._wall_span(obj)
        return base - 0.55 <= reference < top - 1e-6

    def set_placement_mode(self, enabled, callback=None, move_callback=None, rotate_callback=None):
        self.placement_enabled = enabled
        self._clear_map_selection()
        self.placement_callback = callback
        self.move_callback = move_callback
        self.rotate_callback = rotate_callback
        self.preview_point = None
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
        self.setFocus()
        self.update()

    def mousePressEvent(self, e):
        self.setFocus(Qt.MouseFocusReason)
        if e.button() == Qt.MiddleButton:
            self._pan_last = e.position()
            self._last = self._drag_marker = self._drag_start = self._drag_offset = None
            self.preview_point = self.hovered_point = None
            self.setCursor(Qt.ClosedHandCursor)
            self.update()
            e.accept()
            return
        if self._pan_last is not None:
            e.accept()
            return
        if self.placement_enabled and e.button() == Qt.LeftButton and self.placement_callback:
            point = self.screen_to_ground(e.position().x(), e.position().y())
            self.preview_point = point
            if point is not None:
                self.placement_callback(point, self.preview_yaw)
            self.update()
            return
        if e.button() == Qt.LeftButton:
            marker = self._pick_placed_marker(e.position().x(), e.position().y())
            if marker is not None:
                self.selected_marker = marker
                self.selection_changed.emit(marker)
                self._drag_marker = marker
                self._drag_start = e.position()
                # Preserve the grabbed point rather than snapping the object's
                # origin to the cursor (especially visible in the angled view).
                point = next(p for p in self._visible_points() if self._marker_index(p) == marker)
                ground = self.screen_to_ground(e.position().x(), e.position().y())
                self._drag_offset = (point[0]-ground[0], point[2]-ground[2]) if ground else (0, 0)
                self.preview_point = None
                self.setCursor(Qt.ClosedHandCursor)
                self.update()
                return
            self.selected_marker = None
            self.selection_changed.emit(None)
            self._last = e.position()
            self.update()

    def _pick_placed_marker(self, sx, sy):
        point = self._pick_map_point(sx, sy, placed_only=True)
        return self._marker_index(point) if point else None

    @staticmethod
    def _marker_index(point):
        if point[3] != "放置物品":
            return None
        try:
            return int(point[4].rsplit("#", 1)[1]) - 1
        except (ValueError, IndexError):
            return None

    def _marker_geometry(self, point, position=None, yaw=None):
        """Overall bounds, using the same root frame as the prefab's child colliders."""
        kind, label = point[3:]
        profile = self._marker_profile(point)
        width, length, height = {"放置物品": (0.85, 0.60, 0.55),
                                 "物品": (0.30, 0.30, 0.20),
                                 "工人": (0.36, 0.36, 1.2),
                                 "污垢": (0.42, 0.42, 0.02)}.get(kind, (0.4, 0.4, 0.3))
        center, size = (0, height/2, 0), (width, height, length)
        if profile:
            center = tuple((a+b)/2 for a,b in profile['bounds'])
            size = tuple(b-a for a,b in profile['bounds'])
        corners = world_corners(box_corners(center, size), self._marker_rotation(point, yaw),
                                position if position is not None else point[:3])
        return corners[:4], corners[4:]

    def _marker_profile(self, point):
        if point[3] != "放置物品":
            return None
        item_id = self.preview_item_id if point[4] == "预览" else self.point_details.get(point[3:], {}).get('item_id')
        return (self.scene or {}).get('item_profiles', {}).get(item_id)

    def _marker_rotation(self, point, yaw=None):
        if yaw is not None:
            return yaw_rotation(yaw)
        detail = self.point_details.get(point[3:], {})
        return quaternion(detail['rotation']) if 'rotation' in detail else yaw_rotation(detail.get('yaw', 0))

    def _marker_prisms(self, point, position=None, yaw=None):
        cacheable = position is None and yaw is None and point[4] != "预览"
        if cacheable and point in self._item_geometry_cache:
            return self._item_geometry_cache[point]
        profile = self._marker_profile(point)
        if not profile:
            return [self._marker_geometry(point, position, yaw)]
        rotation = self._marker_rotation(point, yaw)
        origin = position if position is not None else point[:3]
        boxes = [world_corners(box, rotation, origin) for box in profile['boxes']]
        result = [(box[:4], box[4:]) for box in boxes]
        if cacheable:
            self._item_geometry_cache[point] = result
        return result

    def _marker_direction(self, point, position=None, yaw=None):
        base, top = self._marker_geometry(point, position, yaw)
        center = tuple(sum(v[i] for v in top)/4 for i in range(3))
        profile = self._marker_profile(point)
        length = max(0.1, min(2.0, (profile['bounds'][2][1]-profile['bounds'][2][0])*0.4)) if profile else 0.45
        from unity_scene_loader import _rotate
        forward = _rotate(self._marker_rotation(point, yaw), (0, 0, length))
        return center, tuple(a+b for a,b in zip(center, forward))

    def set_preview_item(self, item_id):
        self.preview_item_id = item_id
        self.update()

    def _pick_map_point(self, sx, sy, placed_only=False):
        bounds = self._scene_bounds()
        if not bounds:
            return None
        *_, midx, midz, scale, cx, cy = bounds
        hits = []
        cursor = QPoint(int(sx), int(sy))
        key = (bounds, self.yaw, self.pitch, self._floor_reference(), self._points_revision,
               self.floor_mode, self.floor_index)
        if self._marker_cache_key != key:
            markers = []
            for point in self._visible_points():
                faces = []
                for base, top in self._marker_prisms(point):
                    faces.extend([top, base] + [[base[i], base[(i+1)%4], top[(i+1)%4], top[i]] for i in range(4)])
                projected = [[self._project(x-midx, y, z-midz, scale, cx, cy) for x,y,z in face] for face in faces]
                center = tuple(sum(p[i] for p in projected[0])/4 for i in range(3))
                polygons = [QPolygon([QPoint(round(p[0]), round(p[1])) for p in face]) for face in projected]
                flat = [p for face in projected for p in face]
                bounds2d = (min(p[0] for p in flat)-6, max(p[0] for p in flat)+6,
                            min(p[1] for p in flat)-6, max(p[1] for p in flat)+6)
                markers.append((point, center, polygons, bounds2d))
            self._marker_cache, self._marker_cache_key = markers, key
        for point, center, polygons, (left,right,top,bottom) in self._marker_cache:
            if placed_only and self._marker_index(point) is None:
                continue
            if not (left <= sx <= right and top <= sy <= bottom):
                continue
            # Use the same top and side faces as rendering, with a small target for distant objects.
            inside = any(poly.boundingRect().contains(cursor) and poly.containsPoint(cursor, Qt.OddEvenFill)
                         for poly in polygons)
            if inside or (center[0]-sx)**2 + (center[1]-sy)**2 <= 6**2:
                hits.append((center[2], point))
        return max(hits, key=lambda hit: hit[0])[1] if hits else None

    def _scene_bounds(self, pts=None):
        pts = self._visible_points() if pts is None else pts
        key = (id(self.scene), self._points_revision, self.width(), self.height(),
               self.zoom, self.view_mode, self.floor_mode, self.floor_index,
               len(pts))
        if self._bounds_cache_key == key:
            return self._panned_bounds(self._bounds_cache)
        if self._framing_bounds is not None:
            bx0, bx1, bz0, bz1, span, midx, midz = self._framing_bounds
        else:
            verts = [v for obj in (self.scene or {}).get("objects", []) for tri in obj.get("triangles", []) for v in tri]
            # Keep the same horizontal framing when switching storeys.
            placed = [(q[0], q[2]) for q in self._clean_points() if q[3] == "放置物品"]
            coords = placed if self.view_mode == "save" and placed else (
                [(v[0], v[2]) for v in verts] + [(q[0], q[2]) for q in pts])
            if not coords:
                self._bounds_cache_key, self._bounds_cache = key, None
                return None
            xs, zs = zip(*coords)
            pad = max(8.0, max(max(xs)-min(xs), max(zs)-min(zs)) * 0.18) if self.view_mode == "save" and placed else max(max(xs)-min(xs), max(zs)-min(zs), 1.0) * 0.08 + 0.5
            bx0, bx1, bz0, bz1 = min(xs)-pad, max(xs)+pad, min(zs)-pad, max(zs)+pad
            span = max(bx1-bx0, bz1-bz0, 1.0)
            midx, midz = (bx0+bx1)/2, (bz0+bz1)/2
        scale = min(self.width(), self.height()) * 0.78 / span * self.zoom
        result = (bx0, bx1, bz0, bz1, span, midx, midz, scale, self.width()/2, self.height()/2)
        self._bounds_cache_key, self._bounds_cache = key, result
        return self._panned_bounds(result)

    def _panned_bounds(self, bounds):
        # Translate the camera origin without rescanning scene bounds per move.
        if bounds is None:
            return None
        return (*bounds[:-2], bounds[-2]+self.pan_x, bounds[-1]+self.pan_y)

    def screen_to_ground(self, sx, sy):
        """Map screen position to a Unity scene surface, with a y=0 fallback."""
        import math
        bounds = self._scene_bounds()
        if not bounds: return None
        bx0, bx1, bz0, bz1, span, midx, midz, scale, cx, cy = bounds
        sin_pitch = math.sin(math.radians(self.pitch))
        if abs(sin_pitch) < 0.08:
            return None
        xx = (sx-cx)/scale
        zz = (self._floor_reference()*math.cos(math.radians(self.pitch)) - (sy-cy)/scale)/sin_pitch
        ya = math.radians(self.yaw)
        fallback_x = xx*math.cos(ya) + zz*math.sin(ya) + midx
        fallback_z = -xx*math.sin(ya) + zz*math.cos(ya) + midz

        def barycentric(px, py, a, b, c):
            den = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
            if abs(den) < 1e-8:
                return None
            u = ((b[1]-c[1])*(px-c[0]) + (c[0]-b[0])*(py-c[1]))/den
            v = ((c[1]-a[1])*(px-c[0]) + (a[0]-c[0])*(py-c[1]))/den
            w = 1-u-v
            return (u, v, w) if min(u, v, w) >= -0.015 else None

        # Cache projected triangles; pointer movement only tests triangles near the cursor.
        cache_key = (id(self.scene), self.floor_mode, self.floor_index, self._points_revision,
                     self.width(), self.height(), self.yaw, self.pitch, self.zoom, scale, midx, midz, cx, cy)
        if self._projected_tri_cache_key != cache_key:
            projected_cache = []
            for obj in self._visible_scene_objects("floor"):
                for tri in obj.get("triangles", []):
                    projected = tuple(self._project(v[0]-midx, v[1], v[2]-midz, scale, cx, cy) for v in tri)
                    projected_cache.append((min(v[0] for v in projected), max(v[0] for v in projected),
                        min(v[1] for v in projected), max(v[1] for v in projected), projected, tri))
            self._projected_tri_cache = projected_cache
            self._projected_tri_cache_key = cache_key
        hits = []
        for minx, maxx, miny, maxy, projected, tri in self._projected_tri_cache or ():
            if sx < minx or sx > maxx or sy < miny or sy > maxy:
                continue
            weights = barycentric(sx, sy, projected[0], projected[1], projected[2])
            if weights:
                depth = sum(weights[i] * projected[i][2] for i in range(3))
                world = tuple(sum(weights[i] * tri[i][axis] for i in range(3)) for axis in range(3))
                hits.append((depth, world))
        if hits:
            return max(hits, key=lambda hit: hit[0])[1]
        if self.scene:
            return None
        return (fallback_x, 0.0, fallback_z)

    def mouseMoveEvent(self, e):
        if self._pan_last is not None and e.buttons() & Qt.MiddleButton:
            self._pan_to(e.position())
            e.accept()
            return
        if self._drag_marker is not None and e.buttons() & Qt.LeftButton:
            if self._drag_start is not None and (e.position()-self._drag_start).manhattanLength() < QApplication.startDragDistance():
                return
            self._drag_start = None
            self.preview_point = self._drag_position(e.position())
            self.update()
            return
        if self.placement_enabled and not (e.buttons() & Qt.LeftButton):
            self.preview_point = self.screen_to_ground(e.position().x(), e.position().y())
            self.update()
            return
        if self._last is not None and e.buttons() & Qt.LeftButton:
            p = e.position(); d = p - self._last; self._last = p
            self.yaw += d.x() * 0.65; self.pitch = max(25, min(90, self.pitch + d.y() * 0.5)); self.update()
            return
        hovered = self._pick_map_point(e.position().x(), e.position().y())
        if hovered != self.hovered_point:
            self.hovered_point = hovered
            self.setCursor(Qt.PointingHandCursor if hovered else Qt.ArrowCursor)
            self.update()

    def _drag_position(self, position):
        ground = self.screen_to_ground(position.x(), position.y())
        if ground is None:
            return None
        dx, dz = self._drag_offset or (0, 0)
        return (ground[0]+dx, ground[1], ground[2]+dz)

    def _pan_to(self, position):
        delta = position - self._pan_last
        self._pan_last = position
        self.pan_x += delta.x()
        self.pan_y += delta.y()
        self.update()

    def leaveEvent(self, event):
        self.hovered_point = None
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MiddleButton:
            if self._pan_last is not None:
                self._pan_to(e.position())
            self._pan_last = None
            if self.placement_enabled:
                self.preview_point = self.screen_to_ground(e.position().x(), e.position().y())
            self.setCursor(Qt.CrossCursor if self.placement_enabled else Qt.ArrowCursor)
            self.update()
            e.accept()
            return
        if e.button() != Qt.LeftButton:
            return
        if self._drag_marker is not None:
            index, self._drag_marker = self._drag_marker, None
            if self._drag_start is None:
                self.preview_point = self._drag_position(e.position())
            if self.preview_point is not None and self.move_callback:
                self.move_callback(index, self.preview_point)
            self._drag_start = self._drag_offset = None
            self.preview_point = None
            self.setCursor(Qt.CrossCursor if self.placement_enabled else Qt.ArrowCursor)
            self.update()
            return
        self._last = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Delete:
            if not e.isAutoRepeat():
                self.delete_selected_item()
            e.accept()
            return
        if e.key() in (Qt.Key_Q, Qt.Key_Left):
            self.rotate_item(-15.0); e.accept(); return
        if e.key() in (Qt.Key_E, Qt.Key_Right):
            self.rotate_item(15.0); e.accept(); return
        super().keyPressEvent(e)

    def delete_selected_item(self):
        if self.placement_enabled or self.selected_marker is None or not self.delete_callback:
            return False
        if self._drag_marker is not None or self._pan_last is not None:
            return False
        if not any(self._marker_index(point) == self.selected_marker for point in self._visible_points()):
            self._clear_map_selection()
            self.update()
            return False
        if self.delete_callback(self.selected_marker):
            self._clear_map_selection()
            self.update()
            return True
        return False

    def rotate_item(self, degrees):
        if self.placement_enabled:
            self.preview_yaw = (self.preview_yaw + degrees) % 360.0
        elif self.selected_marker is not None and self.rotate_callback:
            self.rotate_callback(self.selected_marker, degrees)
        self.update()

    def wheelEvent(self, e):
        self.zoom = max(.15, min(8.0, self.zoom * (1.12 if e.angleDelta().y() > 0 else .89)))
        if self.placement_enabled:
            self.preview_point = self.screen_to_ground(e.position().x(), e.position().y())
        self.update()

    def resizeEvent(self, e):
        self.preview_point = None
        super().resizeEvent(e)

    def _project(self, x, y, z, scale, cx, cy):
        """Unity camera basis: top view has +X right, +Z up, +Y toward the viewer."""
        key = (self.yaw, self.pitch, self._floor_reference())
        if self._projection_cache_key != key:
            ya, pi = math.radians(self.yaw), math.radians(self.pitch)
            self._projection_cache = (math.cos(ya), math.sin(ya), math.cos(pi), math.sin(pi))
            self._projection_cache_key = key
        ca, sa, cp, sp = self._projection_cache
        y -= key[2]
        xx, zz = x * ca - z * sa, x * sa + z * ca
        yy, zz2 = y * cp + zz * sp, y * sp - zz * cp
        return cx + xx * scale, cy - yy * scale, zz2

    def _clean_points(self):
        """过滤 NaN/Inf 与掉落物异常高度坐标。"""
        if self._clean_cache_key == self._points_revision:
            return self._clean_cache
        out = []
        for x, y, z, kind, label in self.points:
            try:
                x, y, z = float(x), float(y), float(z)
            except (TypeError, ValueError):
                continue
            if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                continue
            if abs(y) > 1000:
                continue
            out.append((x, y, z, kind, label))
        self._clean_cache_key, self._clean_cache = self._points_revision, out
        return out

    def _visible_points(self):
        """Return only objects belonging to the active floor.

        The level selector controls both scene geometry and save objects.  A
        small vertical tolerance accounts for objects whose origin is slightly
        above or below the floor collider while keeping adjacent floors apart.
        """
        points = self._clean_points()
        if self.floor_mode == "all" or not self.floor_levels:
            return points
        reference = self._floor_reference()
        tolerance = 1.15
        return [point for point in points
                if abs(self._point_floor_height(point) - reference) <= tolerance]

    @staticmethod
    def _point_in_xz_quad(x, z, quad, padding=0.0):
        """Return whether a point is inside or close to a scene quad footprint."""
        if len(quad) < 3:
            return False
        vertices = [(float(vertex[0]), float(vertex[2])) for vertex in quad]
        if not (min(v[0] for v in vertices)-padding <= x <= max(v[0] for v in vertices)+padding
                and min(v[1] for v in vertices)-padding <= z <= max(v[1] for v in vertices)+padding):
            return False
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(vertices,vertices[1:]+vertices[:1]))
        signs = []
        for index, current in enumerate(vertices):
            nxt = vertices[(index + 1) % len(vertices)]
            cross = ((nxt[0] - current[0]) * (z - current[1])
                     - (nxt[1] - current[1]) * (x - current[0]))
            signs.append(cross)
        if abs(area) > 1e-8 and (all(value >= -1e-6 for value in signs) or all(value <= 1e-6 for value in signs)):
            return True
        if padding <= 0:
            return False
        for index, current in enumerate(vertices):
            nxt = vertices[(index + 1) % len(vertices)]
            dx, dz = nxt[0] - current[0], nxt[1] - current[1]
            length2 = dx * dx + dz * dz
            ratio = 0.0 if length2 <= 1e-12 else ((x - current[0]) * dx + (z - current[1]) * dz) / length2
            ratio = max(0.0, min(1.0, ratio))
            px, pz = current[0] + ratio * dx, current[1] + ratio * dz
            if math.hypot(x - px, z - pz) <= padding:
                return True
        return False

    def _wall_floor_height(self, point):
        """Use the supporting storey below a hanging item, never its nearest ceiling.

        Prefer local horizontal floor geometry. Wall spans are secondary
        evidence when the anchor lies just outside the floor footprint; a
        height interval fallback covers missing collider data.
        """
        if not self.floor_levels:
            return None
        x, y, z, kind, label = point
        detail = self.point_details.get((kind, label), {})
        definitions = (self.scene or {}).get("item_definitions", {})
        definition = definitions.get(detail.get("item_id"), {})
        if not definition.get("is_wall", detail.get("is_wall", False)):
            return None
        supporting = []
        objects = (self.scene or {}).get("objects", [])
        for surface in objects:
            if surface.get("kind") != "floor":
                continue
            quad = surface.get("quad") or ()
            if not quad or max(v[1] for v in quad)-min(v[1] for v in quad) > 0.35:
                continue
            height = self._scene_floor_height(surface)
            if height > y + 0.02:
                continue
            level = min(self.floor_levels, key=lambda value: abs(value-height))
            if abs(height-level) > 0.35 or level > y + 0.02:
                continue
            if self._point_in_xz_quad(x,z,quad,padding=0.35):
                supporting.append(level)
        if supporting:
            return max(supporting)
        candidates = []
        for wall in objects:
            if wall.get("kind") != "wall":
                continue
            base, top = self._wall_span(wall)
            if not (base - 0.65 <= y <= top + 0.65):
                continue
            if not self._point_in_xz_quad(x, z, wall.get("quad") or (), padding=0.9):
                continue
            levels = [level for level in self.floor_levels
                      if base-0.55 <= level <= y+0.02 and level < top]
            if not levels:
                continue
            floor = max(levels)
            footprint_distance = min(
                math.hypot(x - vertex[0], z - vertex[2])
                for vertex in (wall.get("quad") or ((x, y, z),)))
            candidates.append((footprint_distance, abs(base - floor), floor))
        if candidates:
            return min(candidates)[2]
        return max((level for level in self.floor_levels if level <= y+0.02),
                   default=min(self.floor_levels))

    def _point_floor_height(self, point):
        key = (self._points_revision, id(self.scene), tuple(self.floor_levels))
        if self._point_floor_cache_key != key:
            self._point_floor_cache_key = key
            self._point_floor_cache = {}
        if point in self._point_floor_cache:
            return self._point_floor_cache[point]
        wall_floor = self._wall_floor_height(point)
        result = point[1] if wall_floor is None else wall_floor
        self._point_floor_cache[point] = result
        return result

    def paintEvent(self, _):
        from _map_painter import draw_map
        draw_map(self)


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
        self._cancelled = threading.Event()

    def cancel(self):
        self._cancelled.set()
        self.scanner.cancel()

    def _tick(self, _=0):
        if self._cancelled.is_set():
            raise RuntimeError("扫描已取消")

    def run(self):
        try:
            t0 = time.time()
            res = self.scanner.first_scan_multi(
                self.targets, regions=self.regions,
                workers=self.workers, progress=self._tick)
            if self._cancelled.is_set() or self.scanner.cancelled:
                raise RuntimeError("扫描已取消")
            res["_elapsed"] = time.time() - t0
            self.finished_ok.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class _MemRefineWorker(QThread):
    """重读全部候选并按当前值过滤；结果同时携带下一轮基准。"""
    finished_ok = Signal(dict, dict, int, int, float)
    failed = Signal(str)

    def __init__(self, scanner, hits, types, previous, targets, mode):
        super().__init__()
        self.scanner = scanner
        self.hits = {name: list(addrs) for name, addrs in hits.items()}
        self.types = dict(types)
        self.previous = dict(previous or {})
        self.targets = dict(targets)
        self.mode = mode
        self._cancelled = threading.Event()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        try:
            started = time.time()
            result, snapshot = {}, {}
            kept = dropped = 0
            for name, addresses in self.hits.items():
                value_type = self.types.get(name, "int32")
                target = self.targets.get(name)
                selected = []
                for address in addresses:
                    if self._cancelled.is_set():
                        return
                    current = self.scanner.read_value(address, value_type, None)
                    if current is None:
                        dropped += 1
                        continue
                    previous = self.previous.get(address)
                    if self.mode == "changed":
                        matches = previous is not None and current != previous
                    elif self.mode == "unchanged":
                        matches = previous is not None and current == previous
                    else:
                        matches = target is not None and current == target
                    if matches:
                        selected.append(address)
                        snapshot[address] = current
                        kept += 1
                    else:
                        dropped += 1
                if selected:
                    result[name] = selected
            self.finished_ok.emit(result, snapshot, kept, dropped, time.time() - started)
        except Exception as exc:
            self.failed.emit(str(exc))


class _SceneLoadWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            from unity_scene_loader import load_scene_cached
            from _unity_item_profiles import load_item_profiles
            cache_dir = os.path.join(QStandardPaths.writableLocation(QStandardPaths.CacheLocation), "unity_scene")
            scene = load_scene_cached(self.path, cache_dir=cache_dir)
            try:
                result = load_item_profiles(os.path.dirname(self.path), cache_dir)
                scene['item_profiles'] = result['profiles']
                scene['item_definitions'] = result['definitions']
                scene['item_catalog_error'] = result.get('catalog_error')
            except Exception as exc:
                scene['item_profile_error'] = str(exc)
            self.finished_ok.emit(scene)
        except Exception as exc:
            self.failed.emit(str(exc))


class ES3Editor(DocumentMixin, EditorUiMixin, ExtraPagesMixin, ModsPageMixin, UpdateMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        # QSettings() relies on the application identity.  Without these
        # values, settings such as mods/game_dir may not be readable again
        # after being written, causing the Mod page to clear a selected path.
        app = QApplication.instance()
        if app is not None:
            if not app.organizationName():
                app.setOrganizationName("com-in")
            if not app.applicationName():
                app.setApplicationName("SCS-Saves-Editor")
        self.setWindowTitle("诈骗园区模拟器 - 存档修改器")
        self.setMinimumSize(1000, 700)

        self.data = None          # 解析后的整个 dict
        self.file_path = None

        # 主题
        self.theme = QSettings().value("ui/theme", "light")
        self._action_theme = None
        self._theme_anim = None

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

        self._loading = True
        self.build_ui()
        self.setup_updates()
        self._loading = False
        self.setup_editor_ui()
        self.log("程序已启动，请先打开 .es3 存档文件")
        # 默认全屏（窗口显示后立即最大化）
        self.resize(1280, 840)
        geometry = QSettings().value("ui/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        # 启动时默认最大化，便于完整查看多页编辑器；用户仍可手动还原窗口。
        QTimer.singleShot(0, self.showMaximized)

    # ---------- 主题切换（带过渡动画） ----------
    def _apply_theme_button_text(self):
        """按钮提示可切换到的目标主题（当前亮色则提示切暗色）"""
        self._action_theme.setText("🌙 暗色模式" if self.theme == "light" else "☀️ 亮色模式")
        self._action_sponsor.setText("❤️ 赞助")
        self._action_sponsor.setToolTip("支持作者，打开赞助页")

    def apply_theme(self, name, immediate=False):
        """切换暗色/亮色主题（立即生效，无过渡动画）"""
        global CURRENT_THEME
        if name == self.theme and not immediate:
            return
        dst_theme = DARK_THEME if name == "dark" else LIGHT_THEME
        self.theme = name
        CURRENT_THEME = name
        QSettings().setValue("ui/theme", name)

        # 更新主题按钮提示文字
        if self._action_theme is not None:
            self._apply_theme_button_text()

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(build_qss(dst_theme))

    def _open_sponsor(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        QDesktopServices.openUrl(QUrl("https://afdian.com/a/ctoy_p"))
        self.set_status("✅ 已为你打开赞助页，感谢支持！")

    def set_status(self, text):
        self.status_lbl.setText(text)

    # ==================== 界面 ====================
    def build_ui(self):
        # ========== 原生菜单栏：文件 ==========
        _mb = self.menuBar()
        self._file_menu = _mb.addMenu("文件(&F)")
        _fmenu = self._file_menu
        _fmenu.addAction("📂 打开存档").triggered.connect(self.open_file)
        _fmenu.addAction("🔍 查找存档").triggered.connect(self.find_save_file)
        _fmenu.addAction("💾 保存存档").triggered.connect(self.save_file)
        _fmenu.addSeparator()
        _fmenu.addAction("📋 备份目录").triggered.connect(self.open_backup_dir)
        _fmenu.addAction("♻️ 恢复备份").triggered.connect(self.restore_backup)
        _fmenu.addAction("📑 复制副本").triggered.connect(self.copy_save_file)
        _fmenu.addSeparator()
        _fmenu.addAction("💾 另存为").triggered.connect(self.save_file_as)
        _fmenu.addAction("📤 导出 JSON").triggered.connect(self.export_json)
        _fmenu.addAction("📥 导入 JSON").triggered.connect(self.import_json)
        _fmenu.addAction("🆕 新建骨架").triggered.connect(self.new_save_skeleton)
        _fmenu.addSeparator()
        _fmenu.addAction("退出").triggered.connect(self.close)

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

        self.nav_list = QTreeWidget()
        self.nav_list.setObjectName("Nav")
        self.nav_list.setHeaderHidden(True)
        self.nav_list.setRootIsDecorated(False)   # 隐藏顶层 group 的 branch 装饰空区（箭头已由文字自带）
        self.nav_list.setIndentation(0)
        self.nav_list.setWordWrap(True)
        # nav_items: (图标, 文字, key)
        self.nav_items = [
            ("🏠", "首页", "home"),
            ("📊", "基础数据", "basic"),
            ("👷", "工人", "workers"),
            ("💎", "加密货币", "crypto"),
            ("📦", "物品", "items"),
            ("🏗️", "放置物品", "placed"),
            ("⬆️", "升级", "upgrade"),
            ("📈", "成长进度", "growth"),
            ("🛒", "人口采购", "purchase"),
            ("🏛️", "市政管理", "municipal"),
            ("🛋️", "店面装修", "interior"),
            ("🛡️", "保镖状态", "bodyguard"),
            ("🎓", "教程标记", "tutorial"),
            ("📞", "来电队列", "schedule"),
            ("🏆", "成就统计", "gamestats"),
            ("🐱", "宠物猫", "cat"),
            ("🚚", "配送点", "delivery"),
            ("✈️", "机场队列", "airport"),
            ("🌐", "游戏地图", "map3d"),
            ("🔬", "内存 BYCT", "memory"),
            ("🔓", "解锁管理", "unlock"),
            ("⚙️", "其他", "other"),
            ("🧩", "安装 Mod", "mods"),
        ]
        self._nav_icons = [it[0] for it in self.nav_items]
        self._nav_labels = [it[1] for it in self.nav_items]
        self._nav_keys = [it[2] for it in self.nav_items]
        self._key_to_row = {k: i for i, k in enumerate(self._nav_keys)}
        # 分组导航：组名 -> 该组所含 key（顺序沿用 _nav_keys，stack 页索引保持一致）
        self._nav_groups = [
            ("🏠 档案", ["basic", "workers", "crypto", "items", "placed", "upgrade"]),
            ("🎮 游戏", ["growth", "purchase", "municipal", "interior",
                        "bodyguard", "tutorial", "schedule", "gamestats",
                        "cat", "delivery", "airport"]),
            ("🔧 工具", ["map3d", "memory", "unlock", "other", "mods"]),
        ]
        self._nav_leaves = []          # 叶子项，顺序 == stack 页索引
        self._nav_group_items = []     # 分组头项
        self._nav_group_glyphs = []    # 分组头图标（折叠/展开用）
        # 首页独立置于所有分组之前
        _home_row = self._key_to_row["home"]
        _home_leaf = QTreeWidgetItem([f"{self._nav_icons[_home_row]} {self._nav_labels[_home_row]}"])
        _home_leaf.setData(0, Qt.UserRole, _home_row)
        self.nav_list.addTopLevelItem(_home_leaf)
        self._nav_leaves.append(_home_leaf)
        for gname, keys in self._nav_groups:
            glyph, _, tail = gname.partition(" ")
            g = QTreeWidgetItem([""])
            g.setData(0, Qt.UserRole, -1)          # 分组头：不切换页
            g.setData(0, Qt.UserRole + 1, tail)    # 组尾文字
            g.setData(0, Qt.UserRole + 2, glyph)   # 组图标
            self.nav_list.addTopLevelItem(g)
            self._nav_group_items.append(g)
            self._nav_group_glyphs.append(glyph)
            for k in keys:
                row = self._key_to_row[k]
                leaf = QTreeWidgetItem([f"{self._nav_icons[row]} {self._nav_labels[row]}"])
                leaf.setData(0, Qt.UserRole, row)   # 叶子：绑定 stack 页索引
                g.addChild(leaf)
                self._nav_leaves.append(leaf)
            g.setExpanded(True)
            self._nav_refresh_group_label(g)
        # 分组头视觉：加粗 + 次级色 + 不可选中
        _navf = QFont(self.nav_list.font())
        _navf.setBold(True)
        for g in self._nav_group_items:
            g.setFont(0, _navf)
            g.setForeground(0, QColor(TEXT_SECOND))
            g.setFlags(g.flags() & ~Qt.ItemIsSelectable)
        self.nav_list.setWordWrap(True)
        self.nav_list.setCurrentItem(self._nav_leaves[0])
        self.nav_list.itemSelectionChanged.connect(self.on_nav_change)
        self.nav_list.itemClicked.connect(self.on_nav_item_clicked)
        sb.addWidget(self.nav_list, 1)

        # 左下角：主题切换 + 赞助（横向并排）
        self._action_theme = QPushButton("☀️ 亮色模式")
        self._action_theme.setObjectName("Ghost")
        self._action_theme.clicked.connect(
            lambda: self.apply_theme("light" if self.theme == "dark" else "dark"))
        self._action_sponsor = QPushButton("❤️ 赞助")
        self._action_sponsor.setObjectName("Ghost")
        self._action_sponsor.setToolTip("支持作者，打开赞助页")
        self._action_sponsor.clicked.connect(self._open_sponsor)
        _social = QHBoxLayout(); _social.setSpacing(6)
        _social.addWidget(self._action_theme, 1)
        _social.addWidget(self._action_sponsor, 1)
        sb.addLayout(_social)

        self.sidebar.setFixedWidth(212)

        # 右侧容器 = 上部按钮栏 + 内容栈
        right_outer = QWidget()
        rv = QVBoxLayout(right_outer)
        rv.setContentsMargins(8, 8, 8, 4)
        rv.setSpacing(6)

        # 右侧：内容栈
        self.stack = QStackedWidget()

        # 页面容器
        self.tab_welcome = QWidget()
        self.tab_basic = QWidget()
        self.tab_workers = QWidget()
        self.tab_crypto = QWidget()
        self.tab_items = QWidget()
        self.tab_placed = QWidget()
        self.tab_upgrade = QWidget()
        self.tab_growth = QWidget()
        self.tab_purchase = QWidget()
        self.tab_municipal = QWidget()
        self.tab_interior = QWidget()
        self.tab_bodyguard = QWidget()
        self.tab_tutorial = QWidget()
        self.tab_schedule = QWidget()
        self.tab_gamestats = QWidget()
        self.tab_cat = QWidget()
        self.tab_delivery = QWidget()
        self.tab_airport = QWidget()
        self.tab_map3d = QWidget()
        self.tab_memory = QWidget()
        self.tab_story = QWidget()   # 合并页：银行还款 / 剧情解锁 / 教程解锁
        self.tab_other = QWidget()
        self.tab_mods = QWidget()    # Mod 安装：BepInEx 加载器与插件管理

        for page in (self.tab_welcome, self.tab_basic, self.tab_workers, self.tab_crypto,
                     self.tab_items, self.tab_placed, self.tab_upgrade,
                     self.tab_growth, self.tab_purchase, self.tab_municipal,
                     self.tab_interior,
                     self.tab_bodyguard, self.tab_tutorial, self.tab_schedule,
                     self.tab_gamestats, self.tab_cat, self.tab_delivery, self.tab_airport,
                     self.tab_map3d, self.tab_memory, self.tab_story, self.tab_other,
                     self.tab_mods):
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
        self.build_map3d_tab()
        self.build_json_tab()  # 物品
        self.build_placed_and_other_tab()  # 放置物品/其他
        self.build_debt_story_tutorial_tabs()  # 银行债务/剧情解锁/教程解锁
        self.build_extra_tabs()  # 新增解包项：成长/采购/市政/装修/其他数据
        self.build_welcome_tab()  # 首页：欢迎页 + 文件操作
        self.build_mods_tab()     # Mod 安装：加载器检测/本地与在线安装/启停卸载

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.status_lbl = QLabel("未加载文件")
        self.status_lbl.setObjectName("Muted")
        self.statusBar.addWidget(self.status_lbl)
        self._mods_attach_progress_to_statusbar()

        # 应用初始主题（即时，无动画）
        self.apply_theme(self.theme, immediate=True)

    def on_nav_change(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        # 分组导航：叶子项选中时切换到对应 stack 页（索引绑定在 item data，分组不点偏）
        it = self.nav_list.currentItem()
        if it is None:
            return
        row = it.data(0, Qt.UserRole)
        if row is None or row < 0:
            return                      # 分组头/折叠行，不切换
        self._last_page_row = row
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
        if self._nav_keys[row] == "map3d" and not self.map3d_view.scene:
            self.load_game_scene()
        self._maybe_show_mem_force_read(row)

    def on_nav_item_clicked(self, item, column=0):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        # 分组头：点击折叠/展开该组
        tag = item.data(0, Qt.UserRole)
        if tag == -1:
            item.setExpanded(not item.isExpanded())
            self._nav_refresh_group_label(item)

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
        lb.setText("<p style=\"line-height:160%;\">" + lb.text().replace("\n", "<br>") + "</p>")
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



    def _nav_refresh_group_label(self, g):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        # 分组头文本：展开=▾，折叠=▸；折叠侧边栏时仅显图标不加箭头。
        glyph = g.data(0, Qt.UserRole + 2) or ""
        tail = g.data(0, Qt.UserRole + 1) or ""
        if g.isExpanded():
            g.setText(0, f"▾ {glyph} {tail}")
            g.setTextAlignment(0, Qt.AlignLeft | Qt.AlignVCenter)
        else:
            g.setText(0, f"▸ {glyph} {tail}")
            g.setTextAlignment(0, Qt.AlignLeft | Qt.AlignVCenter)

    # ---------- 统一页面页头 ----------
    def _page_header(self, layout, title, sub=""):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        bar = QWidget()
        b = QVBoxLayout(bar)
        b.setContentsMargins(4, 2, 4, 8)
        b.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        b.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setObjectName("PageSub")
            s.setWordWrap(True)
            b.addWidget(s)
        layout.addWidget(bar)
        return bar

    # ---------- 基础数据 ----------
    def _recent_files(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """最近打开的文件路径列表（仅保留仍存在的文件，最多8个）。"""
        from PySide6.QtCore import QSettings
        q = QSettings("com-in", "SCS-Saves-Editor")
        raw = q.value("welcome/recent", [])
        try:
            items = list(raw) if raw is not None else []
        except TypeError:
            items = []
        recent = []
        for p in items:
            p = str(p)
            if os.path.isfile(p) and p not in recent:
                recent.append(p)
            if len(recent) >= 8:
                break
        return recent

    def _record_recent_file(self, path):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """把新打开的路径记录进最近文件列表（去重置顶、截断8个）。"""
        from PySide6.QtCore import QSettings
        if not path:
            return
        q = QSettings("com-in", "SCS-Saves-Editor")
        old = q.value("welcome/recent", [])
        try:
            items = list(old) if old is not None else []
        except TypeError:
            items = []
        recent = []
        for p in items:
            p = str(p)
            if p != path and p not in recent:
                recent.append(p)
            if len(recent) >= 7:
                break
        recent.insert(0, path)
        q.setValue("welcome/recent", recent)
        if hasattr(self, "recent_list") and self.recent_list is not None:
            self._welcome_refresh_recent()

    def _welcome_refresh_recent(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """刷新欢迎页最近文件列表。"""
        if not hasattr(self, "recent_list") or self.recent_list is None:
            return
        lst = self.recent_list
        lst.clear()
        for p in self._recent_files():
            name = os.path.basename(p)
            folder = os.path.dirname(p)
            it = QListWidgetItem(f"{name}   ——   {folder}")
            it.setToolTip(p)
            it.setData(Qt.UserRole, p)
            lst.addItem(it)
        if lst.count() == 0:
            it = QListWidgetItem("（暂无最近打开的文件）")
            it.setFlags(Qt.NoItemFlags)
            lst.addItem(it)

    def build_welcome_tab(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """首页：VSCode 风格欢迎页，集中文件操作 + 最近打开。"""
        lay = QVBoxLayout(self.tab_welcome)
        lay.setContentsMargins(28, 26, 28, 20)
        lay.setSpacing(10)

        # 标题区
        title = QLabel("💾 诈骗园区模拟器 - 存档修改器")
        title.setObjectName("WelcomeTitle")
        lay.addWidget(title)
        sub = QLabel("打开存档开始编辑。左侧搜索直达功能，所有修改在保存后写入文件。")
        sub.setObjectName("PageSub")
        lay.addWidget(sub)
        lay.addSpacing(8)

        # 文件操作卡片（2x3 网格）
        ops = [
            ("📂 打开存档", "选择本地 ES3/JSON 存档文件并加载", self.open_file),
            ("🔍 查找存档", "自动扫描游戏目录与程序目录的存档", self.find_save_file),
            ("💾 保存存档", "保存当前改动并自动生成备份", self.save_file),
            ("📋 备份目录", "打开存档自动备份所在目录", self.open_backup_dir),
            ("♻️ 恢复备份", "从备份目录选择备份恢复", self.restore_backup),
            ("🆕 新建骨架", "生成空白存档模板，从零搭建新档", self.new_save_skeleton),
            ("📑 复制副本", "为当前存档生成带时间戳的副本", self.copy_save_file),
            ("📤 导出 JSON", "把当前改动导出为可读 JSON 文件", self.export_json),
            ("📥 导入 JSON", "从 ES3/JSON 文件导入为当前编辑对象", self.import_json),
        ]
        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (txt, tip, cb) in enumerate(ops):
            b = QPushButton(f"{txt}\n{tip}")
            b.setObjectName("WelcomeCard")
            b.setToolTip(tip)
            b.clicked.connect(cb)
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)
        lay.addSpacing(10)

        # 最近打开
        rlabel = QLabel("🗂 最近打开")
        rlabel.setObjectName("SectionTitle")
        lay.addWidget(rlabel)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("ListTable")
        self.recent_list.setMaximumHeight(180)
        self.recent_list.itemDoubleClicked.connect(
            lambda it: self._load_file(it.data(Qt.UserRole)))
        lay.addWidget(self.recent_list, 1)
        self._welcome_refresh_recent()

        hint = QLabel("💡 双击最近列表项可直接打开；提示：修改后可能需要执行一次对应值的操作（如消费）才可以生效。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)

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
            ("difficulty", "🌡️ 游戏难度", "Difficulty", "1"),
        ]
        root = QWidget()
        lay = QGridLayout(root)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)

        for i, (key, title, es3, default) in enumerate(fields):
            row, col = divmod(i, 2)
            card = Card(root, title)
            card._lay.addWidget(self._make_value_line(key, default))
            lay.addWidget(card, row, col)

        # 💰 货币：修改时实时钳制上限，不允许超过 1e+35（与游戏上限一致）
        self.entry_basic["currency"].setToolTip("按游戏 float 类型保存，支持科学计数法；非法输入会在保存前提示")

        lay.setColumnStretch(0, 1)
        lay.setColumnStretch(1, 1)
        for r in range(4):
            lay.setRowStretch(r, 1)

        hint = QLabel("修改后点击【保存存档】写入文件。难度：0 简单 / 1 普通 / 2 困难 / 3 沙盒。")
        hint.setObjectName("Hint")
        lay.addWidget(hint, 4, 0, 1, 2)

        self.tab_basic_layout_add(root)

    def _make_value_line(self, key, default):
        """生成 当前值 + 输入框 一行"""
        box = QWidget()
        box.setObjectName("ValueRow")
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
        if key == "difficulty":
            entry.hide()
            combo = QComboBox()
            for value, title in enumerate(("简单", "普通", "困难", "沙盒")):
                combo.addItem(f"{title}  ·  {value}", value)
            def sync_difficulty(text):
                try:
                    value = int(text)
                except ValueError:
                    return
                with QSignalBlocker(combo):
                    index = combo.findData(value)
                    if index < 0:
                        combo.addItem(f"未知难度  ·  {value}", value)
                        index = combo.count() - 1
                    combo.setCurrentIndex(index)
            entry.textChanged.connect(sync_difficulty)
            combo.currentIndexChanged.connect(lambda _: entry.setText(str(combo.currentData())))
            sync_difficulty(default)
            self.difficulty_combo = combo
            h.addWidget(combo, 1)
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
        outer.setSpacing(SECTION_SPACING)
        self._page_header(outer, "📊 基础数据", "货币、等级、经验、天数、电力、店铺名称等核心数值")
        outer.addWidget(root)

    # ---------- 加密货币 ----------
    def build_crypto_tab(self):
        lay = QVBoxLayout(self.tab_crypto)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "💎 加密货币", "查看并修改各币种的当前价格与持有量")

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
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "⬆️ 升级", "一键升级并逐个调整各升级项等级")

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
        self.tab_memory.setObjectName("MemoryPage")
        lay = QVBoxLayout(self.tab_memory)
        lay.setContentsMargins(PAGE_MARGIN, 12, PAGE_MARGIN, 10)
        lay.setSpacing(10)
        title_bar = QHBoxLayout()
        title = QLabel("内存编辑")
        title.setObjectName("PageTitle")
        title_bar.addWidget(title)
        subtitle = QLabel("扫描目标，筛选地址，写入游戏")
        subtitle.setObjectName("Muted")
        title_bar.addWidget(subtitle, 1)
        lay.addLayout(title_bar)

        self._mem_scanner = None    # MemScanner（附加到游戏进程）
        self._mem_targets = []      # [(name, value, vtype)] 从存档提取的扫描目标
        self._mem_hits = {}         # {name:[addr,...]} 最近一次扫描结果
        self._mem_rows = []         # 结果表每行: (name, addr, vtype)
        self._mem_prev = None       # 二次扫描的基准快照 {addr: 上次扫描时的值}
        self._mem_nav_row = self._nav_keys.index("memory")
        self._mem_busy = False
        self._mem_worker = None

        connection = QFrame()
        connection.setObjectName("ToolPanel")
        connection_layout = QGridLayout(connection)
        connection_layout.setContentsMargins(12, 10, 12, 10)
        connection_layout.setHorizontalSpacing(10)
        connection_layout.setVerticalSpacing(6)
        process_title = QLabel("游戏进程")
        process_title.setObjectName("PanelTitle")
        connection_layout.addWidget(process_title, 0, 0)
        self.mem_proc_lbl = QLabel("检测游戏进程…")
        self.mem_proc_lbl.setObjectName("Muted")
        self.mem_proc_lbl.setWordWrap(True)
        self.mem_proc_lbl.setMinimumWidth(0)
        btn_refresh = QPushButton("检测进程")
        btn_refresh.setObjectName("Secondary")
        btn_refresh.clicked.connect(self._mem_refresh_process)
        self._mem_refresh_btn = btn_refresh
        connection_layout.addWidget(self.mem_proc_lbl, 0, 1)
        connection_layout.addWidget(btn_refresh, 0, 2)
        save_title = QLabel("参考存档")
        save_title.setObjectName("PanelTitle")
        connection_layout.addWidget(save_title, 1, 0)
        base = os.path.basename(self.file_path) if self.file_path else "未选择存档"
        self.mem_save_lbl = QLabel(f"当前存档: {base}")
        self.mem_save_lbl.setObjectName("Muted")
        self.mem_save_lbl.setWordWrap(True)
        self.mem_save_lbl.setMinimumWidth(0)
        btn_choose = QPushButton("选择存档")
        btn_choose.setObjectName("Secondary")
        btn_choose.clicked.connect(self.find_save_file)
        self._mem_ui_choose_btn = btn_choose
        connection_layout.addWidget(self.mem_save_lbl, 1, 1)
        connection_layout.addWidget(btn_choose, 1, 2)
        connection_layout.setColumnStretch(1, 1)
        lay.addWidget(connection)

        self._mem_ui_splitter = QSplitter(Qt.Horizontal)
        self._mem_ui_splitter.setChildrenCollapsible(False)
        self._mem_ui_splitter.setHandleWidth(8)
        targets_panel = QFrame()
        targets_panel.setObjectName("ToolPanel")
        targets_panel.setMinimumWidth(250)
        targets_layout = QVBoxLayout(targets_panel)
        targets_layout.setContentsMargins(10, 10, 10, 10)
        targets_layout.setSpacing(8)
        target_header = QHBoxLayout()
        title = QLabel("1 · 扫描目标")
        title.setObjectName("PanelTitle")
        target_header.addWidget(title)
        target_header.addStretch(1)
        self._mem_ui_target_count = QLabel("0 / 0 项")
        self._mem_ui_target_count.setObjectName("StatusChip")
        target_header.addWidget(self._mem_ui_target_count)
        targets_layout.addLayout(target_header)
        self._mem_ui_target_search = QLineEdit()
        self._mem_ui_target_search.setPlaceholderText("查找目标字段…")
        self._mem_ui_target_search.setClearButtonEnabled(True)
        targets_layout.addWidget(self._mem_ui_target_search)
        brow = QHBoxLayout(); brow.setSpacing(6)
        b = QPushButton("提取目标")
        b.setObjectName("Secondary")
        b.setToolTip("从当前存档提取可扫描的数值")
        b.clicked.connect(self._mem_extract_targets)
        self._mem_ui_extract_btn = b
        brow.addWidget(b)
        b_sel = QPushButton("全选"); b_sel.setObjectName("Ghost")
        b_sel.clicked.connect(lambda: self._mem_check_all(True))
        brow.addWidget(b_sel)
        b_un = QPushButton("取消全选"); b_un.setObjectName("Ghost")
        b_un.clicked.connect(lambda: self._mem_check_all(False))
        brow.addWidget(b_un)
        brow.addStretch(1)
        self._mem_ui_check_buttons = (b_sel, b_un)
        targets_layout.addLayout(brow)

        # 4) 目标表格
        self.mem_target_table = QTableWidget(0, 4)
        self.mem_target_table.setHorizontalHeaderLabels(["选", "字段", "扫描值", "类型"])
        self.mem_target_table.setToolTip("勾选需要扫描的字段；双击扫描值可修改")
        hh = self.mem_target_table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setMinimumSectionSize(32)
        self.mem_target_table.setColumnWidth(2, 90)
        self.mem_target_table.setColumnWidth(3, 66)
        self.mem_target_table.setColumnHidden(3, True)
        self.mem_target_table.setMinimumWidth(0)
        self.mem_target_table.setMinimumHeight(90)
        self.mem_target_table.verticalHeader().setDefaultSectionSize(32)
        self.mem_target_table.setAlternatingRowColors(True)
        self.mem_target_table.verticalHeader().setVisible(False)
        targets_layout.addWidget(self.mem_target_table, 1)
        target_help = QLabel("双击修改扫描值，悬停查看类型。")
        target_help.setObjectName("Muted")
        target_help.setWordWrap(True)
        targets_layout.addWidget(target_help)
        target_actions = QHBoxLayout()
        target_actions.setSpacing(6)
        results_panel = QFrame()
        results_panel.setObjectName("ToolPanel")
        results_panel.setMinimumWidth(345)
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(10, 10, 10, 10)
        results_layout.setSpacing(8)
        results_header = QHBoxLayout()
        title = QLabel("2 · 候选地址")
        title.setObjectName("PanelTitle")
        results_header.addWidget(title)
        results_header.addStretch(1)
        self._mem_ui_result_count = QLabel("0 个候选")
        self._mem_ui_result_count.setObjectName("StatusChip")
        results_header.addWidget(self._mem_ui_result_count)
        results_layout.addLayout(results_header)
        self._mem_ui_result_search = QLineEdit()
        self._mem_ui_result_search.setPlaceholderText("查找字段或地址…")
        self._mem_ui_result_search.setClearButtonEnabled(True)
        results_layout.addWidget(self._mem_ui_result_search)

        # 5) 扫描操作（拆两行：扫描执行 | 结果处理，避免按钮挤压）
        act = QHBoxLayout(); act.setSpacing(6)
        b_scan = QPushButton("首次扫描")
        b_scan.clicked.connect(self._mem_start_scan)
        self._mem_scan_btn = b_scan
        target_actions.addWidget(b_scan, 1)
        self._mem_refine_mode = QComboBox()
        self._mem_refine_mode.addItem("值已变化", "changed")
        self._mem_refine_mode.addItem("值未变化", "unchanged")
        self._mem_refine_mode.addItem("等于目标值", "exact")
        self._mem_refine_mode.setToolTip("选择下一次扫描保留候选的条件")
        act.addWidget(self._mem_refine_mode)
        b_scan2 = QPushButton("筛选候选")
        b_scan2.setObjectName("Secondary")
        b_scan2.clicked.connect(self._mem_scan_again)
        self._mem_refine_btn = b_scan2
        act.addWidget(b_scan2)
        b_cancel = QPushButton("停止")
        b_cancel.setObjectName("Ghost")
        b_cancel.setEnabled(False)
        b_cancel.clicked.connect(self._mem_cancel_scan)
        self._mem_cancel_btn = b_cancel
        target_actions.addWidget(b_cancel)
        targets_layout.addLayout(target_actions)
        self._mem_fold_btn = QPushButton("展开"); self._mem_fold_btn.setObjectName("Ghost")
        self._mem_fold_btn.setCheckable(True)
        self._mem_fold_btn.clicked.connect(self._mem_toggle_fold)
        act.addWidget(self._mem_fold_btn)
        act.addStretch(1)
        results_layout.addLayout(act)
        act2 = QHBoxLayout(); act2.setSpacing(6)
        b_ref = QPushButton("刷新数值"); b_ref.setObjectName("Ghost")
        b_ref.setToolTip("刷新勾选地址；未勾选时刷新已显示的地址")
        b_ref.clicked.connect(self._mem_reread)
        self._mem_reread_btn = b_ref
        act2.addWidget(b_ref)
        b_write = QPushButton("写入选中")
        b_write.clicked.connect(self._mem_write_selected)
        self._mem_write_btn = b_write
        b_clear = QPushButton("清空"); b_clear.setObjectName("Ghost")
        b_clear.clicked.connect(self._mem_clear)
        self._mem_ui_clear_btn = b_clear
        act2.addWidget(b_clear)
        b_sync = QPushButton("自动刷新 · 关")
        b_sync.setObjectName("Ghost")
        b_sync.setCheckable(True)
        b_sync.setChecked(False)
        b_sync.clicked.connect(self._mem_toggle_sync)
        act2.addWidget(b_sync)
        self._mem_sync_btn = b_sync
        self._mem_sync_timer = QTimer(self)
        self._mem_sync_timer.setInterval(10000)                # 每 10s 同步一次
        self._mem_sync_timer.timeout.connect(self._mem_sync_once)
        act2.addStretch(1)
        results_layout.addLayout(act2)

        # 6) 结果树（按字段分组，子列表显示详细地址，默认不展开避免卡死）
        self.mem_result_table = QTreeWidget()
        self.mem_result_table.setObjectName("MemoryResults")
        self.mem_result_table.setColumnCount(4)
        self.mem_result_table.setHeaderLabels(["选", "字段 / 地址", "当前值", "写入值"])
        self.mem_result_table.setMinimumWidth(0)
        self.mem_result_table.setMinimumHeight(100)
        self.mem_result_table.setIndentation(12)
        self.mem_result_table.setUniformRowHeights(True)
        self.mem_result_table.setAlternatingRowColors(True)
        hh2 = self.mem_result_table.header()
        hh2.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh2.setMinimumSectionSize(32)
        hh2.setStretchLastSection(False)
        self.mem_result_table.setColumnWidth(2, 92)
        self.mem_result_table.setColumnWidth(3, 92)
        hh2.setSectionResizeMode(1, QHeaderView.Stretch)
        self._mem_ui_result_stack = QStackedWidget()
        self._mem_ui_result_stack.setObjectName("PanelBody")
        empty = QWidget()
        empty.setObjectName("PanelBody")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(14, 14, 14, 14)
        empty_layout.addStretch(1)
        empty_title = QLabel("等待首次扫描")
        self._mem_ui_empty_title = empty_title
        empty_title.setObjectName("EmptyTitle")
        empty_title.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_detail = QLabel("提取并勾选左侧目标，然后开始扫描。\n候选地址将在这里按字段分组显示。")
        self._mem_ui_empty_detail = empty_detail
        empty_detail.setObjectName("Muted")
        empty_detail.setWordWrap(True)
        empty_detail.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_detail)
        empty_layout.addStretch(1)
        self._mem_ui_result_stack.addWidget(empty)
        self._mem_ui_result_stack.addWidget(self.mem_result_table)
        results_layout.addWidget(self._mem_ui_result_stack, 1)
        write_bar = QHBoxLayout()
        self._mem_ui_selection_lbl = QLabel("未勾选地址")
        self._mem_ui_selection_lbl.setObjectName("Muted")
        write_bar.addWidget(self._mem_ui_selection_lbl, 1)
        write_bar.addWidget(b_write)
        results_layout.addLayout(write_bar)
        result_help = QLabel("双击写入值编辑，仅写入勾选的地址。")
        result_help.setObjectName("Muted")
        result_help.setWordWrap(True)
        results_layout.addWidget(result_help)
        self._mem_ui_splitter.addWidget(targets_panel)
        self._mem_ui_splitter.addWidget(results_panel)
        self._mem_ui_splitter.setStretchFactor(0, 2)
        self._mem_ui_splitter.setStretchFactor(1, 3)
        self._mem_ui_splitter.setSizes([310, 520])
        lay.addWidget(self._mem_ui_splitter, 1)

        footer = QHBoxLayout()
        self._mem_progress = QProgressBar()
        self._mem_progress.setRange(0, 100)
        self._mem_progress.setValue(0)
        self._mem_progress.setTextVisible(False)
        self._mem_progress.setMaximumWidth(180)
        self._mem_progress.hide()
        footer.addWidget(self._mem_progress)
        self._mem_state_lbl = QLabel("先提取目标，再进行首次扫描")
        self._mem_state_lbl.setObjectName("Muted")
        self._mem_state_lbl.setWordWrap(True)
        footer.addWidget(self._mem_state_lbl, 1)
        lay.addLayout(footer)
        self._mem_ui_update_timer = QTimer(self)
        self._mem_ui_update_timer.setSingleShot(True)
        self._mem_ui_update_timer.timeout.connect(self._mem_ui_sync)
        for model in (self.mem_target_table.model(), self.mem_result_table.model()):
            model.rowsInserted.connect(self._mem_ui_schedule)
            model.rowsRemoved.connect(self._mem_ui_schedule)
            model.modelReset.connect(self._mem_ui_schedule)
            model.dataChanged.connect(self._mem_ui_schedule)
        self._mem_ui_target_search.textChanged.connect(self._mem_ui_sync)
        self._mem_ui_result_search.textChanged.connect(self._mem_ui_sync)
        self._mem_fold_btn.clicked.connect(self._mem_ui_sync)
        self._mem_sync_btn.clicked.connect(self._mem_ui_sync)
        self._mem_ui_state_timer = QTimer(self)
        self._mem_ui_state_timer.setInterval(400)
        self._mem_ui_state_timer.timeout.connect(self._mem_ui_poll_state)
        self._mem_ui_state_timer.start()
        self._mem_ui_last_state = None
        self._mem_ui_sync()

        QTimer.singleShot(0, self._mem_refresh_process)

    def _mem_ui_schedule(self, *_):
        if not self._mem_ui_update_timer.isActive():
            self._mem_ui_update_timer.start(0)

    def _mem_ui_poll_state(self):
        if not self.tab_memory.isVisible():
            return
        state = (self._mem_busy, self._mem_scanner is not None, bool(self.data))
        if state != self._mem_ui_last_state:
            self._mem_ui_sync()

    def _mem_ui_sync(self, *_):
        """Synchronize presentation only; never read process memory here."""
        busy = self._mem_busy
        connected = self._mem_scanner is not None
        self._mem_ui_last_state = (busy, connected, bool(self.data))
        target_query = self._mem_ui_target_search.text().strip().casefold()
        target_count = self.mem_target_table.rowCount()
        selected_targets = 0
        for row in range(target_count):
            name = self.mem_target_table.item(row, 1)
            checked = self.mem_target_table.item(row, 0)
            value = self.mem_target_table.item(row, 2)
            value_type = self.mem_target_table.item(row, 3)
            if value is not None and value_type is not None:
                tip = f"类型：{value_type.text()} · 双击修改扫描值"
                if value.toolTip() != tip:
                    value.setToolTip(tip)
                alignment = Qt.AlignRight | Qt.AlignVCenter
                if value.textAlignment() != alignment:
                    value.setTextAlignment(alignment)
            if checked is not None and checked.checkState() == Qt.Checked:
                selected_targets += 1
            self.mem_target_table.setRowHidden(row, bool(target_query and
                (name is None or target_query not in name.text().casefold())))
        self._mem_ui_target_count.setText(f"{selected_targets} / {target_count} 项")
        self._mem_ui_target_count.setToolTip("已勾选 / 全部扫描目标")
        query = self._mem_ui_result_search.text().strip().casefold()
        group_count = self.mem_result_table.topLevelItemCount()
        selected = 0
        visible_groups = 0
        for index in range(group_count):
            group = self.mem_result_table.topLevelItem(index)
            group_matches = query in group.text(1).casefold()
            visible_children = 0
            for row in range(group.childCount()):
                child = group.child(row)
                matches = not query or group_matches or query in child.text(1).casefold()
                child.setHidden(not matches)
                visible_children += int(matches)
                selected += int(child.checkState(0) == Qt.Checked)
            group.setHidden(bool(query and not visible_children))
            visible_groups += int(not group.isHidden())
            if query and visible_children:
                group.setExpanded(True)
        total = sum(len(addresses) for addresses in self._mem_hits.values()
                    if isinstance(addresses, list))
        self._mem_ui_result_count.setText(f"{total:,} 个候选")
        self._mem_ui_result_stack.setCurrentIndex(1 if visible_groups else 0)
        if query and group_count and not visible_groups:
            self._mem_ui_empty_title.setText("没有匹配的候选")
            self._mem_ui_empty_detail.setText("尝试字段名称或十六进制地址，或清空搜索。")
        elif busy and not group_count:
            self._mem_ui_empty_title.setText("正在扫描…")
            self._mem_ui_empty_detail.setText("扫描完成后，候选地址将在这里显示。")
        else:
            self._mem_ui_empty_title.setText("暂无候选地址")
            self._mem_ui_empty_detail.setText("提取并勾选左侧目标，然后开始扫描。\n候选地址将在这里按字段分组显示。")
        self._mem_ui_selection_lbl.setText(f"已勾选 {selected} 个地址" if selected else "未勾选地址")
        self._mem_ui_selection_lbl.setToolTip("包含搜索筛选后隐藏的已勾选地址")
        self._mem_scan_btn.setEnabled(not busy and connected and selected_targets > 0)
        self._mem_refine_btn.setEnabled(not busy and connected and total > 0)
        self._mem_write_btn.setEnabled(not busy and connected and selected > 0)
        self._mem_reread_btn.setEnabled(not busy and connected and group_count > 0)
        self._mem_refine_mode.setEnabled(not busy and total > 0)
        self._mem_ui_clear_btn.setEnabled(not busy and group_count > 0)
        self._mem_fold_btn.setEnabled(not busy and group_count > 0)
        self._mem_cancel_btn.setEnabled(busy)
        self._mem_refresh_btn.setEnabled(not busy)
        self._mem_ui_extract_btn.setEnabled(not busy and isinstance(self.data, dict) and bool(self.data))
        self._mem_ui_choose_btn.setEnabled(not busy)
        self._mem_sync_btn.setEnabled(not busy and group_count > 0)
        self._mem_sync_btn.setText("自动刷新 · 10 秒" if self._mem_sync_btn.isChecked() else "自动刷新 · 关")
        self._mem_fold_btn.setText("收起" if self._mem_fold_btn.isChecked() else "展开")
        for button in self._mem_ui_check_buttons:
            button.setEnabled(not busy and target_count > 0)
        for widget in (self._mem_ui_target_search, self._mem_ui_result_search,
                       self.mem_target_table, self.mem_result_table):
            widget.setEnabled(not busy)

    # ---------- 内存：后端逻辑 ----------
    def _mem_refresh_process(self):
        if self._mem_busy:
            return
        pid, exe = find_game_process()
        if not pid:
            self.mem_proc_lbl.setText("❌ 未检测到游戏进程（请先启动游戏）")
            if self._mem_scanner is not None:
                self._mem_scanner.close()
                self._mem_scanner = None
            self._mem_clear()
            return
        try:
            if self._mem_scanner is None or self._mem_scanner.pid != pid:
                if self._mem_scanner is not None:
                    try:
                        self._mem_scanner.close()
                    except Exception:
                        pass
                self._mem_scanner = MemScanner(pid)
                self._mem_clear()
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
                nm = c.get("cryptoName", f"Crypto[{i}]")
                t.append((f"加密货币.{nm}", float(amt), "float32"))

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
        self._mem_clear()
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
            for column in (1, 3):
                item = self.mem_target_table.item(r, column)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
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
            raw = self.mem_target_table.item(r, 2).text().strip()
            try:
                value = self._mem_parse_value(raw, vt)
            except ValueError as exc:
                raise ValueError(f"{nm}: {exc}") from exc
            out.append((nm, value, vt))
        return out

    @staticmethod
    def _mem_parse_value(text, value_type):
        if not text:
            raise ValueError("数值不能为空")
        try:
            number_value = float(text)
        except ValueError as exc:
            raise ValueError("请输入有效数字") from exc
        if not math.isfinite(number_value):
            raise ValueError("数值必须为有限值")
        if value_type == "int32":
            if not number_value.is_integer():
                raise ValueError("整数类型不能包含小数")
            value = int(number_value)
            if not -2147483648 <= value <= 2147483647:
                raise ValueError("超出 int32 范围")
            return value
        if abs(number_value) > 3.4028235e38:
            raise ValueError("超出 float32 范围")
        return number_value

    def _mem_set_busy(self, busy, message=None):
        self._mem_busy = busy
        for widget in (self._mem_refresh_btn, self._mem_scan_btn,
                       self._mem_refine_btn, self._mem_write_btn,
                       self._mem_reread_btn, self._mem_refine_mode):
            widget.setEnabled(not busy)
        self._mem_cancel_btn.setEnabled(busy)
        self._mem_progress.setVisible(busy)
        if not busy:
            self._mem_progress.setValue(0)
        if message:
            self._mem_state_lbl.setText(message)
        self._mem_ui_sync()

    def _mem_cancel_scan(self):
        worker = self._mem_worker
        if worker is not None and worker.isRunning():
            cancel = getattr(worker, "cancel", None)
            if cancel:
                cancel()
            self._mem_state_lbl.setText("正在停止扫描…")

    def _mem_start_scan(self):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        if self._mem_scanner is None:
            QMessageBox.warning(self, "未绑定进程", "请先点【检测进程】绑定游戏！")
            return
        if self._mem_busy:
            return
        try:
            tgts = self._mem_checked_targets()
        except ValueError as exc:
            QMessageBox.warning(self, "目标值无效", str(exc))
            return
        if not tgts:
            QMessageBox.warning(self, "没有目标",
                                "请先【从存档提取扫描目标】并勾选至少一项！")
            return
        self.status_lbl.setText("🚀 正在扫描…（约需 1 分钟，请勿点击）")
        self._mem_set_busy(True, "正在扫描游戏内存…")
        self._mem_active_targets = list(tgts)
        self.log(f"🚀 开始内存首扫，共 {len(tgts)} 个目标")
        self._mem_worker = _MemScanWorker(self._mem_scanner, tgts, None, workers=4)
        self._mem_worker.finished_ok.connect(self._mem_on_scan_done)
        self._mem_worker.failed.connect(self._mem_on_scan_fail)
        self._mem_worker.finished.connect(self._mem_worker_finished)
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
        self._mem_progress.setValue(round(pct))
        sm = scanned / (1024 * 1024)
        tm = total / (1024 * 1024)
        self.status_lbl.setText(
            f"🚀 正在首扫 {pct:.1f}%  (已读 {sm:.0f}/{tm:.0f} MB)")

    def _mem_on_scan_done(self, res):
        self._mem_stop_progress()
        el = res.pop("_elapsed", 0)
        self._mem_hits = dict(res)
        self._mem_prev = {}
        total = sum(len(v) for v in res.values() if isinstance(v, list))
        self.log(f"✅ 首扫完成 {el:.1f}s，共 {total} 个候选地址")
        self.status_lbl.setText(f"✅ 扫描完成：{total} 个候选地址，耗时 {el:.1f}s")
        self._mem_set_busy(False, f"扫描完成：{total} 个候选，耗时 {el:.1f} 秒")
        self._mem_render_results()

    def _mem_on_scan_fail(self, msg):
        self._mem_stop_progress()
        cancelled = "取消" in msg
        text = "扫描已停止" if cancelled else f"扫描失败: {msg}"
        self._mem_set_busy(False, text)
        self.status_lbl.setText(text)
        self.log(text)

    def _mem_worker_finished(self):
        if self._mem_busy and self._mem_worker is not None and not self._mem_worker.isRunning():
            self._mem_set_busy(False)

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
        tv_map, vt_map = {}, {}
        for row in range(self.mem_target_table.rowCount()):
            name_item = self.mem_target_table.item(row, 1)
            value_item = self.mem_target_table.item(row, 2)
            type_item = self.mem_target_table.item(row, 3)
            if not (name_item and value_item and type_item):
                continue
            name, value_type = name_item.text(), type_item.text()
            vt_map[name] = value_type
            try:
                tv_map[name] = self._mem_parse_value(value_item.text(), value_type)
            except ValueError:
                pass
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
            # 顶层字段节点：列1显示字段名，并在其后显示总数据量
            visible_note = f"，显示前 {len(cand)} 个" if len(addrs) > CAP else ""
            top = QTreeWidgetItem(["", f"{nm}（共 {len(addrs)} 个{visible_note}）", "", ""])
            tf = top.font(1); tf.setBold(True)
            top.setFont(1, tf)
            top.setSizeHint(0, QSize(28, 32))   # 字段节点行高
            for ai, (addr, cur) in enumerate(cand):
                leaf = QTreeWidgetItem()
                leaf.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                leaf.setCheckState(0, Qt.Unchecked)
                leaf.setText(1, hex(addr))
                leaf.setText(2, "" if cur is None else self._mem_fmt(cur))
                leaf.setText(3, "" if tv is None else self._mem_fmt(tv))
                leaf.setFlags(leaf.flags() | Qt.ItemIsEditable)
                leaf.setToolTip(3, "双击输入新值")
                leaf.setSizeHint(0, QSize(28, 34))          # 行加高 → 编辑框更大
                vf = leaf.font(3); vf.setPointSizeF(max(vf.pointSizeF() or 10, 12.0))
                leaf.setFont(3, vf)                          # 目标值编辑字体放大
                top.addChild(leaf)
                self._mem_rows.append((leaf, nm, addr, vt))
            self.mem_result_table.addTopLevelItem(top)
            top.setExpanded(False)     # 默认折叠
            top.setToolTip(1, f"{nm}：共 {len(addrs)} 个候选地址，点击展开查看")

    def _mem_toggle_fold(self):
        """展开/收起所有字段节点：展开显示全部地址明细；收起仅显示字段+总数据量。"""
        expanded = self._mem_fold_btn.isChecked()
        self._mem_fold_btn.setText("🙈 收起候选" if expanded else "👁 展开候选")
        for i in range(self.mem_result_table.topLevelItemCount()):
            self.mem_result_table.topLevelItem(i).setExpanded(expanded)

    def _mem_toggle_sync(self, checked):
        """开关每 10s 自动同步。"""
        self._mem_sync_btn.setText("自动刷新：已开启" if checked else "自动刷新 10 秒")
        if checked:
            self._mem_sync_timer.start()
        else:
            self._mem_sync_timer.stop()

    def _mem_sync_once(self):
        """每 10s：重读已列候选地址的当前值，只刷新『值发生变化』的叶子行（增量同步）。"""
        if not self._mem_rows or self._mem_busy:
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
        rows = [row for row in self._mem_rows if row[0].checkState(0) == Qt.Checked]
        if not rows:
            rows = self._mem_rows
        for leaf, nm, addr, vt in rows:
            cur = self._mem_safe_read(addr, vt)
            leaf.setText(2, "" if cur is None else self._mem_fmt(cur))
        self.log(f"🔁 已重读 {len(rows)} 个内存值")

    def _mem_clear(self):
        self.mem_result_table.clear()
        self._mem_rows = []
        self._mem_hits = {}
        self._mem_prev = None
        if hasattr(self, "_mem_state_lbl"):
            self._mem_state_lbl.setText("尚无扫描结果")

    def _mem_write_selected(self):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
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
                "请在结果树【☑】列勾选要写入的地址行。\n目标值可在最后一列直接编辑。")
            return
        pending = []
        for leaf, nm, addr, vt in rows:
            txt = leaf.text(3).strip()
            if not txt:
                QMessageBox.warning(self, "目标值为空", f"{nm} / {hex(addr)} 尚未填写目标值。")
                return
            try:
                val = self._mem_parse_value(txt, vt)
            except ValueError as exc:
                QMessageBox.warning(self, "目标值无效", f"{nm} / {hex(addr)}：{exc}")
                return
            pending.append((leaf, nm, addr, vt, val))
        written, failed = 0, []
        for leaf, nm, addr, vt, val in pending:
            try:
                ok = self._mem_scanner.write_value(addr, vt, val)
                current = self._mem_safe_read(addr, vt) if ok else None
                verified = current is not None and (
                    current == val if vt == "int32" else math.isclose(current, val, rel_tol=1e-5, abs_tol=1e-5))
                if verified:
                    leaf.setText(2, self._mem_fmt(current))
                    self._mem_prev[addr] = current
                    written += 1
                else:
                    failed.append(hex(addr))
            except (OSError, OverflowError, ValueError) as exc:
                failed.append(f"{hex(addr)} ({exc})")
        self.log(f"✍ 已写入并验证 {written} 个地址，失败 {len(failed)} 个")
        tip = "修改后可能需要执行一次对应值的操作（如消费）才可在游戏内生效。"
        state = f"已写入并验证 {written} 个地址"
        if failed:
            state += f"，失败 {len(failed)} 个"
        self._mem_state_lbl.setText(state)
        self.status_lbl.setText(f"{state}：{tip}")

    def _mem_scan_again(self):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
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
        type_map = {n: vt for n, _, vt in getattr(self, "_mem_active_targets", self._mem_targets)}
        target_map = {n: v for n, v, _ in getattr(self, "_mem_active_targets", self._mem_targets)}
        self._mem_set_busy(True, "正在筛选全部候选地址…")
        worker = _MemRefineWorker(
            sc, self._mem_hits, type_map, self._mem_prev,
            target_map, self._mem_refine_mode.currentData())
        self._mem_worker = worker
        worker.finished_ok.connect(self._mem_on_refine_done)
        worker.failed.connect(self._mem_on_scan_fail)
        worker.finished.connect(self._mem_worker_finished)
        worker.start()
        return

        new = {}
        kept = dropped = 0
        converged = 0                       # 已收敛到唯一地址、本次自动保留的字段数
        mode = self._mem_refine_mode.currentData()
        for nm, addrs in self._mem_hits.items():
            # 一旦该字段已收敛到只剩 1 个地址，下次扫描直接跳过过滤、原样保留，
            # 防止它被误删/误收敛导致字段整个消失。
            if len(addrs) == 1:
                new[nm] = addrs
                converged += 1
                continue
            vt = vt_map.get(nm, "int32")
            keep = []
            for addr in addrs:
                cur = self._mem_safe_read(addr, vt)
                if cur is None:
                    dropped += 1
                    continue
                last = prev.get(addr)
                target = None
                for tn, tv, _ in getattr(self, "_mem_active_targets", self._mem_targets):
                    if tn == nm:
                        target = tv
                        break
                if mode == "unchanged":
                    matches = last is not None and cur == last
                elif mode == "exact":
                    matches = target is not None and cur == target
                else:
                    matches = last is not None and cur != last
                if matches:
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
        # 删除前确认：避免静默剔除未变化选项导致目标地址丢失
        if dropped > 0 and kept:
            _c = QMessageBox.question(
                self, "确认删除选项",
                f"下一次扫描将删除 {dropped} 个未变化的候选选项，"
                f"仅保留 {kept} 个已变化的候选地址。\n\n是否继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if _c != QMessageBox.Yes:
                self.log("已取消下一次扫描，未删除任何选项。")
                self.status_lbl.setText("已取消下一次扫描，候选选项未删除。")
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

    def _mem_on_refine_done(self, hits, snapshot, kept, dropped, elapsed):
        self._mem_hits = hits
        self._mem_prev = snapshot
        self._mem_set_busy(False, f"筛选完成：保留 {kept} 个，移除 {dropped} 个")
        self._mem_render_results()
        if not hits:
            self.status_lbl.setText("❌ 没有符合条件的候选地址，请让游戏数值变化后再筛选。")
            return
        total = sum(len(values) for values in hits.values())
        self.status_lbl.setText(f"✅ 筛选完成：保留 {total} 个候选，耗时 {elapsed:.1f} 秒")
        self.log(f"🔎 下一次扫描：保留 {kept}，移除 {dropped}，耗时 {elapsed:.1f}s")

    # ---------- 银行还款 / 剧情解锁 / 教程解锁（表格 + 一键操作） ----------
    def build_debt_story_tutorial_tabs(self):
        """合并页：银行还款 / 剧情与任务解锁 / 教程解锁 占用小，合并为单页。"""
        lay = QVBoxLayout(self.tab_story)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🔓 解锁管理", "银行还款、剧情与任务解锁、教程解锁 合并为一页")

        def section(title_txt):
            t = QLabel(title_txt)
            t.setObjectName("CardTitle")
            lay.addWidget(t)

        # === 银行还款管理 ===
        section("🏦 银行还款管理")
        bar = QHBoxLayout(); bar.setSpacing(8)
        b1 = QPushButton("🎁 一键全还清"); b1.clicked.connect(self._debt_clear_all)
        b2 = QPushButton("🔓 一键解锁债务"); b2.clicked.connect(self._debt_unlock_all)
        b3 = QPushButton("♻️ 重置债务"); b3.setObjectName("Ghost"); b3.clicked.connect(self._debt_reset)
        bar.addWidget(b1); bar.addWidget(b2); bar.addWidget(b3); bar.addStretch(1)
        lay.addLayout(bar)
        self.debt_table = self._build_list_editor(lay)
        self.debt_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        self._debt_headers = {
            "paidAmount": "已还金额", "curAmount": "当前金额", "dayLeft": "总天数",
            "curDayLeft": "剩余天数", "isPaid": "是否已还", "unlocked": "是否解锁",
            "interestRate": "利率(%)", }
        self.debt_table._header_map = self._debt_headers
        self._table_keys["Debt"] = self.debt_table
        hint = QLabel("💡 双击编辑数值；【是否已还/是否解锁】点击勾选切换。")
        hint.setObjectName("Hint"); lay.addWidget(hint)

        # === 剧情 & 任务解锁 ===
        section("📖 剧情 & 任务解锁")
        bar = QHBoxLayout(); bar.setSpacing(8)
        b1 = QPushButton("🎁 一键解锁全部剧情"); b1.clicked.connect(self._story_unlock_all)
        b2 = QPushButton("♻️ 重置剧情进度"); b2.setObjectName("Ghost"); b2.clicked.connect(self._story_reset)
        bar.addWidget(b1); bar.addWidget(b2); bar.addStretch(1)
        lay.addLayout(bar)
        self.story_table = self._build_list_editor(lay)
        self.story_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        self._story_headers = {
            "id": "剧情索引", "currentProgress": "当前进度", "unlockProgress": "解锁所需",
            "isCompleted": "是否完成", "unlocked": "是否解锁", }
        self.story_table._header_map = self._story_headers
        self.story_table._readonly_cols = ("id",)
        self._table_keys["MissionProgress"] = self.story_table
        hint = QLabel("💡 【解锁所需/当前进度】可直接编辑完成；勾选切换【是否完成/是否解锁】。")
        hint.setObjectName("Hint"); lay.addWidget(hint)

        # === 教程解锁 ===
        section("🎓 教程解锁")
        bar = QHBoxLayout(); bar.setSpacing(8)
        b1 = QPushButton("🎁 一键解锁全部教程"); b1.clicked.connect(self._tutorial_unlock_all)
        b2 = QPushButton("♻️ 重置教程状态"); b2.setObjectName("Ghost"); b2.clicked.connect(self._tutorial_reset)
        bar.addWidget(b1); bar.addWidget(b2); bar.addStretch(1)
        lay.addLayout(bar)
        self.tutorial_table = self._build_list_editor(lay)
        self.tutorial_table.setMaximumHeight(TABLE_FIXED_HEIGHT)
        self._tutorial_headers = {"index": "教程索引", "unlocked": "是否解锁", }
        self.tutorial_table._header_map = self._tutorial_headers
        self.tutorial_table._readonly_cols = ("index",)
        self._table_keys["TutorialSaveData"] = self.tutorial_table
        hint = QLabel("💡 点击【是否解锁】勾选切换；教程索引列只读。")
        hint.setObjectName("Hint"); lay.addWidget(hint)

    # ---------- 银行/剧情/教程 一键操作 ----------
    def _debt_clear_all(self):
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
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
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
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
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
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
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "📦 物品", "物品列表：每个物品一行，位置/旋转/数量等可直改")
        self.items_table = self._build_list_editor(lay)
        self.items_table._id_field = "itemId"
        self.items_table._name_col_title = "物品名称"
        self.items_table._header_map = {
            "itemId": "物品ID",
            "position.x": "位置X", "position.y": "位置Y", "position.z": "位置Z",
            "rotation.x": "旋转X", "rotation.y": "旋转Y",
            "rotation.z": "旋转Z", "rotation.w": "旋转W",
            "isBox": "是否盒子", "boxItemId": "盒内物品ID", "quantity": "数量",
            "isGarbage": "是否垃圾", "garbageTypeId": "垃圾类型ID",
            "garbageId": "垃圾ID", "isFood": "是否食物", "isDead": "是否已死",
        }
        lay.addWidget(self.items_table, 1)
        lay.addWidget(self._build_row_ops_bar(self.items_table))
        self._table_keys["Items"] = self.items_table
        h = QLabel("✅ 物品列表：每个元素一行，position/rotation 已按 x/y/z(/w) 拆分为独立列可直改；其余标量列直接改。")
        h.setObjectName("Hint")
        lay.addWidget(h)

    def build_map3d_tab(self):
        """真实 Unity 场景几何与存档对象叠加预览。"""
        self.tab_map3d.setObjectName("MapPage")
        lay = QVBoxLayout(self.tab_map3d)
        lay.setContentsMargins(PAGE_MARGIN, 12, PAGE_MARGIN, 10)
        lay.setSpacing(10)
        title_bar = QHBoxLayout()
        title = QLabel("游戏地图")
        title.setObjectName("PageTitle")
        title_bar.addWidget(title)
        subtitle = QLabel("放置、移动和旋转物品")
        subtitle.setObjectName("Muted")
        title_bar.addWidget(subtitle, 1)
        self.map_options_btn = QToolButton()
        self.map_options_btn.setText("地图设置")
        self.map_options_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.map_options_btn)
        menu.addAction("刷新存档坐标", self.refresh_map3d)
        menu.addAction("重新加载游戏场景", self.load_game_scene)
        menu.addSeparator()
        menu.addAction("选择游戏目录…", self.choose_game_directory)
        self.map_options_btn.setMenu(menu)
        title_bar.addWidget(self.map_options_btn)
        lay.addLayout(title_bar)

        tools = QFrame()
        tools.setObjectName("ToolPanel")
        tools_layout = QVBoxLayout(tools)
        tools_layout.setContentsMargins(12, 10, 12, 10)
        tools_layout.setSpacing(8)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        view_label = QLabel("视图")
        view_label.setObjectName("PanelTitle")
        bar.addWidget(view_label)
        self.map_view_box = QComboBox()
        self.map_view_box.addItem("存档区域", "save")
        self.map_view_box.addItem("完整场景", "all")
        self.map_view_box.setToolTip("选择地图显示范围")
        self.map_view_box.currentIndexChanged.connect(
            lambda: self.map3d_view.set_view_mode(self.map_view_box.currentData()))
        bar.addWidget(self.map_view_box)
        self.map_camera_box = QComboBox()
        self.map_camera_box.addItem("俯视", "top")
        self.map_camera_box.addItem("斜视", "angle")
        self.map_camera_box.setToolTip("切换相机角度")
        self.map_camera_box.currentIndexChanged.connect(
            lambda: self.map3d_view.set_camera_preset(self.map_camera_box.currentData()))
        bar.addWidget(self.map_camera_box)
        bar.addSpacing(6)
        floor_title = QLabel("楼层")
        floor_title.setObjectName("PanelTitle")
        bar.addWidget(floor_title)
        self.map_floor_box = QComboBox()
        self.map_floor_box.addItem("存档楼层", "current")
        self.map_floor_box.addItem("上一层", "upper")
        self.map_floor_box.addItem("全部楼层", "all")
        self.map_floor_box.currentIndexChanged.connect(self._select_map_floor)
        bar.addWidget(self.map_floor_box)
        self.map_floor_prev = QPushButton("↓")
        self.map_floor_prev.setObjectName("Secondary")
        self.map_floor_prev.setFixedWidth(34)
        self.map_floor_prev.setEnabled(False)
        self.map_floor_prev.setAccessibleName("降低一层")
        self.map_floor_prev.setToolTip("降低一层（方向键 ↓）")
        self.map_floor_prev.clicked.connect(lambda: self.map3d_view.step_floor(-1))
        bar.addWidget(self.map_floor_prev)
        self.map_floor_label = QLabel("未载入")
        self.map_floor_label.setObjectName("Muted")
        self.map_floor_label.hide()
        self.map_floor_next = QPushButton("↑")
        self.map_floor_next.setObjectName("Secondary")
        self.map_floor_next.setFixedWidth(34)
        self.map_floor_next.setEnabled(False)
        self.map_floor_next.setAccessibleName("升高一层")
        self.map_floor_next.setToolTip("升高一层（方向键 ↑）")
        self.map_floor_next.clicked.connect(lambda: self.map3d_view.step_floor(1))
        bar.addWidget(self.map_floor_next)
        bar.addStretch(1)
        self.map_reset_btn = QPushButton("重置视角")
        self.map_reset_btn.setObjectName("Secondary")
        self.map_reset_btn.setToolTip("恢复当前视图的缩放、位置和相机角度")
        self.map_reset_btn.clicked.connect(self._reset_map_camera)
        bar.addWidget(self.map_reset_btn)
        tools_layout.addLayout(bar)
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)
        item_title = QLabel("物品")
        item_title.setObjectName("PanelTitle")
        action_bar.addWidget(item_title)
        self.map_item_box = SearchComboBox()
        self.map_item_search = self.map_item_box.search
        self.map_item_box.setMinimumWidth(150)
        self.map_item_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.map_item_box.setMinimumContentsLength(12)
        self.map_item_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        action_bar.addWidget(self.map_item_box, 1)
        self.map_place_btn = QPushButton("添加物品")
        self.map_place_btn.setObjectName("ModeButton")
        self.map_place_btn.setToolTip("进入放置模式，在地图地面点击添加所选物品")
        self.map_place_btn.setCheckable(True)
        self.map_place_btn.toggled.connect(self._toggle_map_placement)
        action_bar.addWidget(self.map_place_btn)
        self.map_rotate_left = QPushButton("左转 15°")
        self.map_rotate_left.setObjectName("Secondary")
        self.map_rotate_left.setToolTip("左转 15°（Q）：旋转预览或选中物品")
        self.map_rotate_left.clicked.connect(lambda: self.map3d_view.rotate_item(-15.0))
        action_bar.addWidget(self.map_rotate_left)
        self.map_rotate_right = QPushButton("右转 15°")
        self.map_rotate_right.setObjectName("Secondary")
        self.map_rotate_right.setToolTip("右转 15°（E）：旋转预览或选中物品")
        self.map_rotate_right.clicked.connect(lambda: self.map3d_view.rotate_item(15.0))
        action_bar.addWidget(self.map_rotate_right)
        self.map_delete_btn = QPushButton("删除所选")
        self.map_delete_btn.setObjectName("Danger")
        self.map_delete_btn.setEnabled(False)
        self.map_delete_btn.setToolTip("选中已放置物品后删除（Delete）；保存后写入存档")
        action_bar.addWidget(self.map_delete_btn)
        tools_layout.addLayout(action_bar)
        lay.addWidget(tools)

        self.map3d_view = Map3DWidget()
        self.map3d_view.placement_callback = self._place_item_at_map_point
        self.map3d_view.move_callback = self._move_placed_item
        self.map3d_view.rotate_callback = self._rotate_placed_item
        self.map3d_view.delete_callback = self._delete_placed_item
        self.map3d_view.floor_changed_callback = self._on_map_floor_changed
        self.map3d_view.set_camera_preset("top")
        self.map_delete_btn.clicked.connect(self.map3d_view.delete_selected_item)
        self.map3d_view.selection_changed.connect(self._update_map_selection_ui)
        self.map_item_box.currentIndexChanged.connect(
            lambda: self.map3d_view.set_preview_item(self.map_item_box.currentData()))
        self.map_item_box.currentIndexChanged.connect(self._update_map_selection_ui)
        canvas_frame = QFrame()
        canvas_frame.setObjectName("ToolPanel")
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(1, 1, 1, 1)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(self.map3d_view, 1)
        self.map_selection_label = QLabel("选择物品后可拖动、旋转或删除")
        self.map_selection_label.setObjectName("Muted")
        self.map_selection_label.setContentsMargins(10, 5, 10, 5)
        self.map_selection_label.setMinimumWidth(0)
        self.map_selection_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        canvas_layout.addWidget(self.map_selection_label)
        lay.addWidget(canvas_frame, 1)
        # Keep the legend and help in normal layout space, never on the canvas.
        self.map_footer = QFrame()
        footer_layout = QVBoxLayout(self.map_footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(5)
        legend = QHBoxLayout()
        legend.setSpacing(14)
        from _map_painter import COLORS
        for kind, color in COLORS.items():
            label = QLabel(f'<span style="color:{color}">●</span> {kind}')
            label.setObjectName("Muted")
            legend.addWidget(label)
        legend.addStretch(1)
        self.map_help_btn = QPushButton("操作说明")
        self.map_help_btn.setObjectName("Secondary")
        self.map_help_btn.setCheckable(True)
        self.map_help_btn.setToolTip("展开鼠标与快捷键操作说明")
        legend.addWidget(self.map_help_btn)
        footer_layout.addLayout(legend)
        self.map3d_info = QLabel("打开存档后，从“地图设置”载入游戏场景")
        self.map3d_info.setObjectName("Muted")
        self.map3d_info.setWordWrap(True)
        self.map3d_info.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        footer_layout.addWidget(self.map3d_info)
        self.map_help = QLabel("中键拖动平移 · 滚轮缩放 · 左键拖动物品移动 / 空白旋转视角\nQ/E 旋转物品 · ↑/↓ 切换楼层 · Delete 删除所选 · 悬停查看名称和尺寸")
        self.map_help.setWordWrap(True)
        self.map_help.setObjectName("Muted")
        self.map_help.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        footer_layout.addWidget(self.map_help)
        self.map_help.hide()
        self.map_help_btn.toggled.connect(self.map_help.setVisible)
        self.map_footer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay.addWidget(self.map_footer)
        self.map_item_search.textChanged.connect(self._populate_map_item_box)
        self._populate_map_item_box()
        self._update_map_selection_ui()

    def _reset_map_camera(self):
        self.map3d_view.set_view_mode(self.map_view_box.currentData())
        self.map3d_view.set_camera_preset(self.map_camera_box.currentData())

    def _update_map_selection_ui(self, _index=None):
        view = self.map3d_view
        placing = view.placement_enabled
        index = view.selected_marker
        selected = index is not None and not placing
        with QSignalBlocker(self.map_place_btn):
            self.map_place_btn.setChecked(placing)
        self.map_place_btn.setText("结束放置" if placing else "添加物品")
        self.map_delete_btn.setEnabled(selected)
        self.map_rotate_left.setEnabled(placing or selected)
        self.map_rotate_right.setEnabled(placing or selected)
        if placing:
            text = f"正在放置：{self.map_item_box.currentText()} · 点击地面添加，Q / E 调整方向"
        elif selected:
            detail = view.point_details.get(("放置物品", f"放置物品 #{index+1}"), {})
            text = f"已选中：{detail.get('name', '放置物品')} · 朝向 {detail.get('yaw', 0):.0f}° · 拖动可移动"
        else:
            text = "中键拖动平移 · 滚轮缩放 · 选择物品后可移动、旋转或删除"
        self.map_selection_label.setText(text)
        self.map_selection_label.setToolTip(text)

    def _populate_map_item_box(self, _text=None):
        selected = self.map_item_box.currentData()
        terms = self.map_item_search.text().casefold().split()
        definitions = (self.map3d_view.scene or {}).get('item_definitions', {})
        with QSignalBlocker(self.map_item_box):
            self.map_item_box.clear()
            for item_id, definition in sorted(definitions.items(),
                                              key=lambda pair: item_sort_key(*pair)):
                name = self._item_label(item_id)
                if self._can_place_on_map(definition) and all(t in name.casefold() for t in terms):
                    self.map_item_box.addItem(name, item_id)
            index = self.map_item_box.findData(selected)
            self.map_item_box.setCurrentIndex(index if index >= 0 else 0 if self.map_item_box.count() else -1)
        available = self.map_item_box.count() > 0
        # Keep the popup accessible when a query has no matches, so users can
        # reopen it and clear the search.
        self.map_item_box.setEnabled(any(self._can_place_on_map(d) for d in definitions.values()))
        self.map_item_box.sync_results()
        self.map_item_box.setPlaceholderText("没有匹配的物品" if terms else "加载游戏后选择物品")
        self.map_item_box.setToolTip("按床铺、工作、生活、供电、收纳、特殊设施、娱乐、装饰排列；同名物品按等级升序。可添加商店或市长兑换的地面设施")
        self.map_place_btn.setEnabled(available)
        if not available:
            self.map_place_btn.setChecked(False)
        self.map3d_view.set_preview_item(self.map_item_box.currentData())
        self._update_map_selection_ui()

    @staticmethod
    def _can_place_on_map(definition):
        return bool(definition and definition.get('is_placable')
                    and definition.get('has_placable_component') and not definition.get('is_wall')
                    and (definition.get('in_shop') is True or definition.get('in_mayor_exchange') is True)
                    and definition.get('registered') is True)

    def _item_label(self, item_id, fallback=None):
        view = getattr(self, 'map3d_view', None)
        definition = ((view.scene or {}).get('item_definitions', {}).get(item_id)
                      if view is not None else None)
        return item_label(item_id, definition, fallback)

    def _refresh_item_labels(self):
        # Scene metadata may arrive after editing starts. Update read-only names
        # without reloading rows or overwriting unsaved table cells.
        for table in (self.items_table, self.placed_table):
            specs = getattr(table, '_list_meta', {}).get('cols', [])
            with QSignalBlocker(table):
                for column, spec in enumerate(specs):
                    if not spec.get('is_name'):
                        continue
                    id_column = next((i for i, s in enumerate(specs)
                                      if s['path'] == [spec['id']]), None)
                    if id_column is None:
                        continue
                    for row in range(table.rowCount()):
                        cell, id_cell = table.item(row, column), table.item(row, id_column)
                        try:
                            item_id = int(id_cell.text())
                        except (AttributeError, ValueError):
                            continue
                        if cell:
                            cell.setText(self._item_label(item_id))

    def _toggle_map_placement(self, enabled):
        if enabled and (not isinstance(self.data, dict) or self.map_item_box.currentData() is None):
            self.map_place_btn.setChecked(False)
            self.map3d_info.setText("请先打开存档、加载场景并选择可放置物品")
            return
        if enabled and not self.map3d_view.scene:
            self.map_place_btn.setChecked(False)
            self.load_game_scene()
            return
        self.map3d_view.set_placement_mode(enabled, self._place_item_at_map_point,
            self._move_placed_item, self._rotate_placed_item)
        self.map3d_info.setText("移动鼠标预览位置，Q/E 或旋转按钮调整方向，点击确认放置" if enabled else "已退出放置模式")

    def _select_map_floor(self):
        mode = self.map_floor_box.currentData()
        if isinstance(mode, int):
            self.map3d_view.set_floor_index(mode)
        elif mode is not None:
            self.map3d_view.set_floor_mode(mode)
            self.map_floor_label.setText("全部楼层" if mode == "all" else "楼层")
            self.map_floor_prev.setEnabled(self.map3d_view.floor_index > 0)
            self.map_floor_next.setEnabled(self.map3d_view.floor_index + 1 < len(self.map3d_view.floor_levels))

    def _on_map_floor_changed(self, index, total, height):
        with QSignalBlocker(self.map_floor_box):
            self.map_floor_box.setCurrentIndex(self.map_floor_box.findData(index))
        self.map_floor_prev.setEnabled(index > 0)
        self.map_floor_next.setEnabled(index + 1 < total)
        self.map_floor_label.setText(f"第 {index + 1}/{total} 层")
        self.map3d_info.setText(f"当前楼层高度 Y={height:.2f}；点击地面放置物品")

    def _place_item_at_map_point(self, point, yaw=0.0):
        import math
        item_id = self.map_item_box.currentData()
        definition = (self.map3d_view.scene or {}).get('item_definitions', {}).get(item_id)
        if not isinstance(self.data, dict) or not self._can_place_on_map(definition):
            self.map3d_info.setText("当前物品不支持在地图地面放置")
            return False
        if point is None or len(point) != 3 or not all(math.isfinite(v) for v in point) or not math.isfinite(yaw):
            return
        placed = self._list_save(self.placed_table)
        if not isinstance(placed, list):
            placed = []
        item = {
            "id": str(uuid.uuid4()), "itemDataId": int(item_id),
            "position": {"x": round(point[0], 6), "y": round(point[1], 6), "z": round(point[2], 6)},
            "rotation": {"x": 0, "y": round(math.sin(math.radians(yaw)/2), 7),
                         "z": 0, "w": round(math.cos(math.radians(yaw)/2), 7)},
            "workerNum": 0, "currentNpcCount": 0, "hackStationIndex": -1,
            "isShelf": definition['is_shelf'], "assignedNpcId": [], "shelfType": definition['shelf_type'],
            "tamingNpcs": [], "stockStationIndex": -1,
            "stockStationTimeInterval": 30, "stockStationStockLimit": 10,
        }
        placed.append(item)
        self.es3_set("PlaceItems", placed)
        self._list_load(self.placed_table, placed)
        self.refresh_map3d(preserve_view=True)
        self._refresh_document_state()
        self.map3d_info.setText(f"已添加 {self._item_label(int(item_id))}，坐标 ({point[0]:.2f}, {point[1]:.2f}, {point[2]:.2f})")
        return True

    def _move_placed_item(self, index, point):
        placed = self._list_save(self.placed_table)
        if not isinstance(placed, list) or not (0 <= index < len(placed)) or not isinstance(placed[index], dict):
            return
        placed[index]["position"] = {"x": round(point[0], 6), "y": round(point[1], 6), "z": round(point[2], 6)}
        self.es3_set("PlaceItems", placed)
        self._list_load(self.placed_table, placed)
        self.refresh_map3d(preserve_view=True)
        self._refresh_document_state()
        self.map3d_info.setText(f"已移动放置物品 #{index+1} 到 ({point[0]:.2f}, {point[1]:.2f}, {point[2]:.2f})")

    def _delete_placed_item(self, index):
        placed = self._list_save(self.placed_table)
        detail = self.map3d_view.point_details.get(("放置物品", f"放置物品 #{index+1}"), {})
        item_id = detail.get('save_id')
        # The table may have changed since the map was rendered. Resolve the
        # persistent ID instead of deleting whichever row now has this index.
        matches = [i for i,item in enumerate(placed or [])
                   if isinstance(item,dict) and item_id and item.get('id') == item_id]
        if len(matches) != 1:
            self.map3d_info.setText("物品记录已变化或 ID 无效，请刷新坐标后重新选择")
            return False
        item = placed[matches[0]]
        if item.get('tamingNpcs'):
            self.map3d_info.setText("笼中仍有 NPC，请先在游戏中移出后再删除，以免丢失 NPC 数据")
            return False
        placed.pop(matches[0])
        workers = copy.deepcopy(self.workers)

        def clear_assignment(worker):
            if isinstance(worker,dict):
                for key in ('assignedBedId','assignedWorkplaceId'):
                    if worker.get(key) == item_id:
                        worker[key] = None

        for worker in workers or []:
            clear_assignment(worker)
        for remaining in placed:
            if isinstance(remaining,dict):
                for worker in remaining.get('tamingNpcs') or []:
                    clear_assignment(worker)
        self.es3_set("PlaceItems", placed)
        self.workers = workers
        if isinstance(workers,list):
            self.es3_set("Workers",workers)
        self.map3d_view._clear_map_selection()
        self._list_load(self.placed_table,placed)
        self.refresh_map3d(preserve_view=True)
        self._refresh_document_state()
        self.map3d_info.setText(f"已删除 {detail.get('name', '所选物品')}；点击保存写入存档")
        return True

    def _rotate_placed_item(self, index, degrees):
        import math
        placed = self._list_save(self.placed_table)
        if not isinstance(placed, list) or not (0 <= index < len(placed)) or not isinstance(placed[index], dict):
            return
        rotation = rotate_world_y(placed[index].get("rotation") or {}, degrees)
        placed[index]["rotation"] = {axis: round(value, 7) for axis,value in zip("xyzw",rotation)}
        self.es3_set("PlaceItems", placed)
        self._list_load(self.placed_table, placed)
        self.refresh_map3d(preserve_view=True)
        self._refresh_document_state()
        self.map3d_info.setText(f"已旋转放置物品 #{index+1}：{heading(rotation):.0f}°")

    @staticmethod
    def _map3d_pos(obj):
        if not isinstance(obj, dict): return None
        pos = obj.get("position", obj.get("Position"))
        if not isinstance(pos, dict): return None
        try:
            return (float(pos.get("x", 0)), float(pos.get("y", 0)), float(pos.get("z", 0)))
        except (TypeError, ValueError):
            return None

    def refresh_map3d(self, checked=False, *, preserve_view=False):
        import math
        points = []
        details = {}
        sources = (("PlaceItems", "放置物品"), ("Items", "物品"), ("Workers", "工人"), ("Dirt", "污垢"))
        for key, kind in sources:
            arr = self.es3_get(key) if isinstance(self.data, dict) else None
            if not isinstance(arr, list): continue
            for i, obj in enumerate(arr):
                pos = self._map3d_pos(obj)
                if pos is None:
                    continue
                label = f"{kind} #{i+1}"
                points.append((*pos, kind, label))
                try:
                    item_id = int(obj.get("itemDataId", obj.get("itemId", -1)))
                except (TypeError, ValueError):
                    item_id = -1
                name = self._item_label(item_id, kind)
                if kind == "工人":
                    name = (obj.get("npcDataRole") or {}).get("npcName", kind)
                definition = (self.map3d_view.scene or {}).get("item_definitions", {}).get(item_id, {})
                rotation = quaternion(obj.get("rotation") or {})
                details[(kind, label)] = {"name": name, "item_id": item_id,
                                         "save_id": obj.get('id'), "rotation": rotation,
                                         "yaw": heading(rotation),
                                         "is_wall": bool(definition.get("is_wall"))}
        self.map3d_view.set_points(points, details, preserve_view=preserve_view)
        self._update_map_selection_ui()
        self.map3d_info.setText(f"已绘制 {len(points)} 个坐标点（放置物品/物品/工人/污垢）")

    def load_game_scene(self):
        data_dir = QSettings().value("map/game_data_dir", "") or r"F:\GameUnpack\UnderKingdom\Scam Center Simulator UnderKingdom_Data"
        path = os.path.join(data_dir, "level1")
        if not os.path.isfile(path):
            self.map3d_info.setText("尚未选择游戏数据目录")
            return
        if getattr(self, "_scene_worker", None) and self._scene_worker.isRunning():
            return
        self.map3d_info.setText("正在读取游戏场景的地面和墙体布局，请稍候……")
        self._scene_worker = _SceneLoadWorker(path)
        self._scene_worker.finished_ok.connect(self._on_scene_loaded)
        self._scene_worker.failed.connect(lambda msg: self.map3d_info.setText(f"场景解析失败：{msg}"))
        self._scene_worker.start()

    def choose_game_directory(self):
        current = QSettings().value("map/game_data_dir", "") or r"F:\GameUnpack\UnderKingdom"
        directory = QFileDialog.getExistingDirectory(self, "选择游戏目录或游戏数据目录", current)
        if not directory:
            return
        if not os.path.isfile(os.path.join(directory, "level1")):
            candidates = [os.path.join(directory, name) for name in os.listdir(directory)
                          if name.endswith("_Data") and os.path.isdir(os.path.join(directory, name))]
            directory = next((candidate for candidate in candidates
                              if os.path.isfile(os.path.join(candidate, "level1"))), directory)
        if not os.path.isfile(os.path.join(directory, "level1")):
            QMessageBox.warning(self, "未找到游戏场景", "该目录没有 level1 场景文件，请选择游戏安装目录或 *_Data 目录。")
            return
        QSettings().setValue("map/game_data_dir", directory)
        self.load_game_scene()

    def _on_scene_loaded(self, scene):
        self.map3d_view.set_scene(scene)
        self._refresh_item_labels()
        self._populate_map_item_box()
        with QSignalBlocker(self.map_floor_box):
            self.map_floor_box.clear()
            for index in range(len(self.map3d_view.floor_levels)):
                self.map_floor_box.addItem(f"第 {index + 1} 层", index)
            self.map_floor_box.addItem("全部楼层", "all")
        self._on_map_floor_changed(self.map3d_view.floor_index,
                                   len(self.map3d_view.floor_levels),
                                   self.map3d_view._floor_reference())
        self.refresh_map3d()
        self.map3d_info.setText(f"已加载游戏地图：{scene.get('object_count', 0)} 个地面/墙体区域")
        if scene.get('item_profile_error'):
            self.map3d_info.setText("地图已加载；物品尺寸读取失败，暂用估算外形")
            self.map3d_info.setToolTip(scene['item_profile_error'])
        elif scene.get('item_catalog_error'):
            self.map3d_info.setText("地图已加载；无法核实商店或市长兑换清单，暂时禁用新增物品，已有存档物品仍可查看和编辑")
            self.map3d_info.setToolTip(scene['item_catalog_error'])

    def build_placed_and_other_tab(self):
        # 放置物品：列表表格编辑
        lay = QVBoxLayout(self.tab_placed)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "🏗️ 放置物品", "已放置物品列表：逐一编辑位置/分配等字段")
        self.placed_table = self._build_list_editor(lay)
        self.placed_table._id_field = "itemDataId"
        self.placed_table._name_col_title = "物品名称"
        self.placed_table._header_map = {
            "id": "唯一ID", "itemDataId": "物品数据ID",
            "position.x": "位置X", "position.y": "位置Y", "position.z": "位置Z",
            "rotation.x": "旋转X", "rotation.y": "旋转Y",
            "rotation.z": "旋转Z", "rotation.w": "旋转W",
            "workerNum": "工人数", "currentNpcCount": "当前NPC数",
            "hackStationIndex": "黑客站索引", "isShelf": "是否货架",
            "assignedNpcId": "分配NPC", "shelfType": "货架类型",
            "tamingNpcs": "驯服NPC", "stockStationIndex": "补货站索引",
            "stockStationTimeInterval": "补货间隔(秒)", "stockStationStockLimit": "补货上限",
        }
        self.placed_table._readonly_cols = ("id",)
        self.placed_table.itemSelectionChanged.connect(self._on_placed_selection)
        lay.addWidget(self.placed_table, 1)
        lay.addWidget(self._build_row_ops_bar(self.placed_table))
        # 复制按钮（原在顶部栏，迁入本页；选中一行后显示）
        self.placed_copy_btn = QPushButton("📋 复制选中行")
        self.placed_copy_btn.setObjectName("Ghost")
        self.placed_copy_btn.clicked.connect(self._placed_copy_row)
        _pcb = QWidget(); _pcl = QHBoxLayout(_pcb)
        _pcl.setContentsMargins(0, 0, 0, 0); _pcl.setSpacing(8)
        _pcl.addWidget(self.placed_copy_btn); _pcl.addStretch(1)
        lay.addWidget(_pcb)
        self._table_keys["PlaceItems"] = self.placed_table
        h = QLabel("✅ 放置物品列表：每个元素一行，position/rotation 拆为独立列；assignedNpcId/tamingNpcs 等列表或空值以 JSON 文本编辑。")
        h.setObjectName("Hint")
        lay.addWidget(h)

        # 其他：可编辑的通用数据查看器（标量→输入框，列表→表格，复杂结构→JSON）
        lay = QVBoxLayout(self.tab_other)
        lay.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        lay.setSpacing(SECTION_SPACING)
        self._page_header(lay, "⚙️ 其他数据", "通用数据查看器：标量 / 表格 / JSON 三种模式")

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
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        hdr.setSectionsClickable(True)
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
        """从种子数据建立列定义：返回列规格列表。
        每列为 {name, path, type}；path 为 (顶层key, ...子key)。
        嵌套字典（如 position/rotation）展开为多列(例如 position.x)，
        复杂结构（list/null）作为单一 JSON 文本列。
        列类型综合所有行的标量类型决定：只要出现 float 即取 float，
        避免 int/float 混排（如 position/rotation 中 0 与小数并存）导致小数被截断。"""
        order = []        # [(path, name)] 保持首现顺序
        index = {}        # path -> 下标
        typeset = {}      # path -> set[标量类别]

        def absorb(path, v):
            key = tuple(path)
            if key not in index:
                index[key] = len(order)
                order.append((key, ".".join(path)))
                typeset[key] = set()
            t = self._type_of(v)
            if t is not None:
                typeset[key].add(t)

        def recurse(path, v):
            if isinstance(v, dict):
                for k, subv in v.items():
                    recurse(path + [k], subv)
            else:
                absorb(path, v)

        for it in items or []:
            if not isinstance(it, dict):
                continue
            for k, v in it.items():
                recurse([k], v)

        colspec = []
        for key, name in order:
            ts = typeset[key]
            if not ts:
                typ = None
            elif "float" in ts:
                typ = "float"
            elif "int" in ts:
                typ = "int"
            elif "bool" in ts:
                typ = "bool"
            elif "str" in ts:
                typ = "str"
            else:
                typ = None
            colspec.append({"name": name, "path": list(key), "type": typ})
        return colspec

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
        with QSignalBlocker(table):
            table.setRowCount(0)
            table._source_not_list = not isinstance(items, list)
            table._source_value = copy.deepcopy(items)
            self._list_load_impl(table, items if isinstance(items, list) else [])
            for r, value in enumerate(items if isinstance(items, list) else []):
                header = QTableWidgetItem(str(r + 1))
                # QVariantMap alphabetizes dict keys, including nested Unity
                # quaternions. Keep an ordered JSON payload across the Qt boundary.
                payload = json.dumps(value, ensure_ascii=False, allow_nan=False)
                header.setData(Qt.UserRole, payload)
                table.setVerticalHeaderItem(r, header)
                for c in range(table.columnCount()):
                    cell = table.item(r, c)
                    if cell:
                        cell.setData(Qt.UserRole + 10, {"ui": [cell.text(), cell.checkState().value],
                            "value": payload})
            hidden = getattr(table, "_hide_cols", ())
            for c, spec in enumerate(getattr(table, "_list_meta", {}).get("cols", [])):
                table.setColumnHidden(c, spec["path"][0] in hidden)

    def _other_repr(self):
        if self._other_scalar_entry is not None:
            return self._other_scalar_entry.text()
        if self._other_stack.currentIndex() == 1:
            return [[(cell.text(), cell.checkState().value) if cell else None
                     for cell in (self.other_table.item(r, c) for c in range(self.other_table.columnCount()))]
                    for r in range(self.other_table.rowCount())]
        return self.other_json.toPlainText()

    def _other_has_edits(self):
        return bool(self._other_cur_key and self._other_repr() != getattr(self, "_other_initial", None))

    def _save_other_key(self):
        if not self._other_has_edits():
            return
        key = self._other_cur_key
        if self._other_scalar_entry is not None:
            value = self._text_to_cell(self._other_scalar_entry.text(), self._type_of(self.es3_get(key)))
        elif self._other_stack.currentIndex() == 1:
            value = self._list_save(self.other_table)
        else:
            value = json.loads(self.other_json.toPlainText())
        self.es3_set(key, value)

    def _list_load_impl(self, table, items):
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

        colspec = self._list_meta_from_seed(items)
        id_field = getattr(table, "_id_field", None)
        if id_field:
            name_col = {"name": getattr(table, "_name_col_title", "名称"),
                        "path": ["__name__"], "is_name": True, "id": id_field}
            colspec = [name_col] + colspec
        for _t, _p in (getattr(table, "_extra_bool_cols", {}) or {}).items():
            _k = [_p]
            if not any(s2["path"] == _k for s2 in colspec):
                colspec.append({"name": _t, "path": _k, "type": "bool", "optional": True})
        table._list_meta = {"cols": colspec}
        # 中文表头映射（如有）
        header_map = getattr(table, "_header_map", {}) or {}
        headers = [header_map.get(s["name"], s["name"]) for s in colspec]
        table.setColumnCount(len(colspec))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(items) if isinstance(items, list) else 0)
        table.blockSignals(True)
        # 只读列（id/index 等不参与编辑）
        readonly_cols = set(getattr(table, "_readonly_cols", ()) or ())
        for r, it in enumerate(items or []):
            if not isinstance(it, dict):
                continue
            for c, spec in enumerate(colspec):
                if spec.get("is_name"):
                    idv = self._pick_path(it, [spec["id"]])
                    if isinstance(idv, (int, float)):
                        cell = QTableWidgetItem(self._item_label(int(idv)))
                    else:
                        cell = QTableWidgetItem("")
                    cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    table.setItem(r, c, cell)
                    continue
                v = self._pick_path(it, spec["path"])
                readonly = spec["path"][0] in readonly_cols
                if spec.get("optional"):
                    _has = isinstance(it, dict) and spec["path"][0] in it
                    if _has:
                        cell = self._new_bool_cell(bool(v))
                        if readonly:
                            cell.setFlags(cell.flags() & ~Qt.ItemIsEnabled)
                    else:
                        cell = QTableWidgetItem("")
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    table.setItem(r, c, cell)
                    continue
                if spec["type"] == "bool":
                    cell = self._new_bool_cell(bool(v))
                    if readonly:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEnabled)
                else:
                    cell = QTableWidgetItem(self._cell_to_text(v))
                    if readonly:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                    # 显示汉化：命中映射时显示中文，原始值存 UserRole 供保存回写
                    disp = getattr(table, "_display_cn", None)
                    if disp:
                        cn = disp.get(spec["path"][0])
                        if cn is not None:
                            key = str(v) if not isinstance(v, (int, float)) else int(v)
                            if key in cn:
                                cell.setText(cn[key])
                                cell.setData(Qt.UserRole, v)
                table.setItem(r, c, cell)
        table.resizeColumnsToContents()
        # 隐藏指定列（数据保留，仅不显示）
        hide_cols = getattr(table, "_hide_cols", ()) or ()
        if hide_cols:
            for c, spec in enumerate(colspec):
                if spec["path"][0] in hide_cols:
                    table.setColumnHidden(c, True)
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
        if getattr(table, "_source_not_list", False):
            return copy.deepcopy(table._source_value)
        meta = getattr(table, "_list_meta", {})
        out = []
        for r in range(table.rowCount()):
            header = table.verticalHeaderItem(r)
            seed = json.loads(header.data(Qt.UserRole)) if header else None
            if "scalar" in meta:
                cell = table.item(r, 0)
                snapshot = cell.data(Qt.UserRole + 10) if cell else None
                if snapshot and [cell.text(), cell.checkState().value] == snapshot["ui"]:
                    out.append(json.loads(snapshot["value"]))
                else:
                    out.append(cell.checkState() == Qt.Checked if meta["scalar"] == "bool"
                               else self._text_to_cell(cell.text() if cell else "", meta["scalar"]))
                continue
            if header and not isinstance(seed, dict):
                out.append(copy.deepcopy(seed))
                continue
            row = copy.deepcopy(seed) if isinstance(seed, dict) else {}
            for c, spec in enumerate(meta.get("cols", [])):
                if spec.get("is_name"):
                    continue
                cell = table.item(r, c)
                snapshot = cell.data(Qt.UserRole + 10) if cell else None
                if snapshot and [cell.text(), cell.checkState().value] == snapshot["ui"]:
                    continue
                if spec.get("optional") and cell and not cell.flags() & Qt.ItemIsUserCheckable:
                    continue
                try:
                    value = (cell.checkState() == Qt.Checked if spec["type"] == "bool" and cell
                             else self._text_to_cell(cell.text() if cell else "", spec["type"]))
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"第 {r + 1} 行 / {spec['name']}：{exc}") from exc
                self._set_path(row, spec["path"], value)
            out.append(row)
        return out


    def _pick_path(self, it, path):
        """按 path 逐层取值；中间缺层返回 None。"""
        cur = it
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    def _set_path(self, d, path, val):
        """按 path 逐层写入；中间缺层自动建空 dict。"""
        if len(path) == 1:
            d[path[0]] = val
            return
        cur = d
        for i, p in enumerate(path):
            if i == len(path) - 1:
                cur[p] = val
            else:
                nxt = cur.get(p)
                if not isinstance(nxt, dict):
                    nxt = {}
                    cur[p] = nxt
                cur = nxt

    def _text_to_cell(self, text, t):
        if t == "int":
            return self._to_int(text)
        if t == "float":
            return self._to_float(text)
        if t == "bool":
            return self._parse_bool_text(text)
        if t == "str":
            return text
        return json.loads(text) if text.strip() else None


    def _to_int(self, txt):
        return number(txt, integer=True)


    def _to_float(self, txt):
        return number(txt)


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
        meta = getattr(table, "_list_meta", {})
        if not meta.get("cols") and "scalar" not in meta:
            self.set_status("当前列表没有字段模板，请使用游戏生成的数据")
            return
        r = table.rowCount()
        table.insertRow(r)
        if "scalar" in meta:
            table.setItem(r, 0, self._new_bool_cell(False) if meta["scalar"] == "bool"
                          else QTableWidgetItem("0" if meta["scalar"] in ("int", "float") else ""))
            return
        for c, spec in enumerate(meta["cols"]):
            if spec.get("is_name"):
                cell = QTableWidgetItem("")
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            elif spec["type"] == "bool":
                cell = self._new_bool_cell(False)
            else:
                cell = QTableWidgetItem("0" if spec["type"] in ("int", "float") else "")
            table.setItem(r, c, cell)


    def _list_del_row(self, table):
        rows = set(i.row() for i in table.selectedIndexes())
        for r in sorted(rows, reverse=True):
            table.removeRow(r)
        if isinstance(table, QPlainTextEdit):
            return

    def _on_placed_selection(self):
        has = len(self.placed_table.selectionModel().selectedRows()) > 0
        self.placed_copy_btn.setVisible(has)

    def _placed_copy_row(self):
        """复制选中放置物品：在"物品"列表新增一行盒装物品（isBox=true，盒内物品ID=复制目标物品ID）。"""
        r = self.placed_table.currentRow()
        if r < 0:
            return
        placed = self._list_save(self.placed_table)
        if r >= len(placed):
            return
        target = placed[r]
        if not isinstance(target, dict):
            return
        tid = target.get("itemDataId", 0)
        new = {
            "itemId": tid,
            "position": copy.deepcopy(target.get("position", {"x": 0, "y": 0, "z": 0})),
            "rotation": copy.deepcopy(target.get("rotation", {"x": 0, "y": 0, "z": 0, "w": 1})),
            "isBox": True,
            "boxItemId": tid,
            "quantity": 1,
            "isGarbage": False,
            "garbageTypeId": 0,
            "garbageId": 0,
            "isFood": False,
            "isDead": False,
        }
        items = self._list_save(self.items_table)
        if not isinstance(items, list):
            items = []
        items.append(new)
        self.es3_set("Items", items)
        self._list_load(self.items_table, items)
        # 复制完成后自动跳转到"物品"菜单页
        row = self._nav_keys.index("items")
        self._go_to_page("items")

    # ---------- "其他"页通用编辑器 ----------
    def _on_other_key_changed(self):
        try:
            self._save_other_key()
        except (ValueError, TypeError) as exc:
            with QSignalBlocker(self.other_key_box):
                self.other_key_box.setCurrentIndex(self.other_key_box.findData(self._other_cur_key))
            QMessageBox.warning(self, "请修正输入", str(exc))
            return
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
        elif isinstance(val, list) and all(isinstance(x, dict) for x in val):
            self._other_stack.setCurrentIndex(1)  # 表格
            self.other_row_bar.setVisible(True)
            self._list_load(self.other_table, val)
        else:
            # 复杂 dict → JSON 编辑器
            self._other_stack.setCurrentIndex(2)
            self.other_row_bar.setVisible(False)
            self.other_json.setPlainText(
                json.dumps(val, ensure_ascii=False, indent="\t") if val is not None else "")
        self._other_initial = self._other_repr()

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
        v.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        v.setSpacing(SECTION_SPACING)

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
        grid.setSpacing(10)
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
            row, col = divmod(i, 3)
            grid.setColumnStretch(col, 1)
            f = QFrame()
            f.setObjectName("FieldBox")
            fv = QVBoxLayout(f)
            fv.setContentsMargins(12, 8, 12, 8)
            fv.setSpacing(6)
            lb = QLabel(label)
            lb.setObjectName("Muted")
            e = QLineEdit()
            e.setFixedHeight(32)
            e.editingFinished.connect(lambda k=key: self.on_worker_field_changed(k))
            fv.addWidget(lb)
            fv.addWidget(e)
            grid.addWidget(f, row, col)
            self.worker_entries[key] = e
        pv.addLayout(grid)

        # 职业下拉框（对应存档 npcRoleId）
        role_f = QFrame()
        role_f.setObjectName("FieldBox")
        role_fv = QVBoxLayout(role_f)
        role_fv.setContentsMargins(10, 6, 10, 6)
        role_fv.setSpacing(4)
        role_lb = QLabel("💼 职业")
        role_lb.setObjectName("Muted")
        self.role_combo = QComboBox()
        self.role_combo.setFixedHeight(32)
        for rid in sorted(_ROLE_NAME.keys()):
            self.role_combo.addItem(_ROLE_NAME[rid], rid)
        self.role_combo.currentIndexChanged.connect(self.on_worker_role_changed)
        role_fv.addWidget(role_lb)
        role_fv.addWidget(self.role_combo)
        pv.addWidget(role_f)

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
        outer.setSpacing(SECTION_SPACING)
        self._page_header(outer, "👷 工人", "逐个编辑工人的属性、职业、驯服与死亡状态")
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
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
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
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
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
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
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









    def import_json(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """导入 JSON：选择 json/es3 文件加载为当前编辑对象。"""
        start_dir = self._guess_default_dir()
        path, _ = QFileDialog.getOpenFileName(
            self, "导入存档", start_dir,
            "ES3 存档 (*.es3);;JSON 文件 (*.json);;所有文件 (*.*)")
        if not path:
            return
        self._load_file(path)

    def copy_save_file(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """复制副本：把当前存档文件复制出一份带时间戳的副本，快速备份当前状态。"""
        if not self.file_path or not os.path.isfile(self.file_path):
            QMessageBox.warning(self, "未打开文件", "请先打开一个存档文件！")
            return
        base, ext = os.path.splitext(os.path.basename(self.file_path))
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst = os.path.join(os.path.dirname(self.file_path),
                           f"{base}_copy_{stamp}{ext}")
        try:
            shutil.copy2(self.file_path, dst)
            self.log(f"📑 已复制副本: {dst}")
            QMessageBox.information(self, "复制成功",
                                    f"已生成副本:\n{dst}\n\n当前编辑对象不变。")
        except Exception as e:
            QMessageBox.critical(self, "复制失败", f"错误: {e}")
            self.log(f"❌ 复制失败: {e}")

    def new_save_skeleton(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """新建存档骨架：生成一个带默认字段结构的空白存档模板并加载到界面。"""
        skeleton = {
            "Currency": {"value": 0}, "Level": {"value": 1}, "Exp": {"value": 0},
            "Day": {"value": 1}, "Electricity": {"value": 0}, "ShopName": {"value": ""},
            "CallData": {"value": -1}, "Difficulty": {"value": 1},
            "Workers": {"value": []}, "CryptoData": {"value": []},
            "Items": {"value": []}, "PlaceItems": {"value": []}, "Upgrade": {"value": []},
            "Progress": {"value": []}, "EasterEgg": {"value": []},
            "NpcPurchase": {"value": {}}, "Mayor": {"value": []},
            "NpcRoleFound": {"value": []}, "Interior": {"value": []}, "Dirt": {"value": []},
            "MissionProgress": {"value": []}, "Debt": {"value": []},
            "TutorialSaveData": {"value": {}},
            "BodyGuard": {"value": {"guards": []}}, "Tutorial": {"value": []},
            "ScheduleCall": {"value": []}, "GameStats": {"value": []},
            "Cat": {"value": {}}, "DeliveryLocation": {"value": 0},
            "AirportNpc": {"value": []},
        }
        start_dir = self._guess_default_dir()
        path, _ = QFileDialog.getSaveFileName(
            self, "新建存档骨架", os.path.join(start_dir or "", "new_save.es3"),
            "ES3 存档 (*.es3);;JSON 文件 (*.json);;所有文件 (*.*)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(skeleton, f, ensure_ascii=False, indent="\t")
        self.file_path = path
        self.data = skeleton
        self.parse_data_to_ui()
        base = os.path.basename(path)
        self.setWindowTitle(f"诈骗园区模拟器 - 存档修改器  —  {base}")
        self.status_lbl.setText(f"已新建骨架: {base}")
        self.log(f"🆕 已新建存档骨架: {path}")

    def save_ui_to_data(self):
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
        if not isinstance(self.data, dict):
            return
        basic = {"currency": ("Currency", False), "level": ("Level", True),
                 "exp": ("Exp", True), "days": ("Day", True),
                 "electricity": ("Electricity", True), "callData": ("CallData", True),
                 "difficulty": ("Difficulty", True)}
        for field, (key, integer) in basic.items():
            if self.es3_get(key) is not None:
                self.es3_set(key, number(self.entry_basic[field].text(), integer=integer, label=key))
        self.es3_set("ShopName", self.entry_basic["shopName"].text())

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
                price = self._to_float(it1.text() if it1 else 0)
                if price != c.get("currentPrice"):
                    # CryptoData.Initialise uses the last price history point.
                    history = c.get("priceHistory")
                    if isinstance(history, list) and history:
                        history[-1] = price
                    else:
                        c["priceHistory"] = [price]
                c["currentPrice"] = price
                c["coinAmount"] = self._to_float(it2.text() if it2 else 0)
                c["avgBuyPrice"] = self._to_float(it3.text() if it3 else 0)

        # 升级（表格列: 名称[只读]/等级）：
        # 只读名称列不写回；仅当该升级项（按内部英文名）在配置中时，才对等级做上限钳制并写回。
        # 未配置的升级项（如 Upgrade）保留原样，杜绝"升级丢失"。
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
                if it1.text() == str(u.get("level", 0)):
                    continue
                lv = number(it1.text(), integer=True, label=eng, minimum=0, maximum=setup[1])
                u["level"] = lv
                # 让界面等级单元格同步为纠正后的值
                if it1 and it1.text() != str(lv):
                    it1.setText(str(lv))

        # 工人已实时写回 workers，无需再次写（但确保整段写回）
        if self.workers is not None:
            self.es3_set("Workers", self.workers)
        # 新增解包项：定制表单/高风险项写回
        self.save_extra_to_data()

    def merge_json_tabs(self):
        for key, table in self._table_keys.items():
            if key in self.data:
                try:
                    self.es3_set(key, self._list_save(table))
                except (ValueError, TypeError) as exc:
                    raise ValueError(f"{key}: {exc}") from exc
        self._save_other_key()


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
        self.entry_basic["difficulty"].setText(str(self.es3_get("Difficulty") if self.es3_get("Difficulty") is not None else 1))

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
        dedicated = set(self._table_keys) | {"Currency", "Level", "Exp", "Day", "Electricity",
            "ShopName", "CallData", "Difficulty", "Workers", "CryptoData", "Upgrade",
            "NpcPurchase", "Cat", "DeliveryLocation", "AirportNpc", "BodyGuard", "Interior",
            "Tutorial", "ScheduleCall", "NpcRoleFound", "Dirt"}
        self._other_cur_key = None
        for k, node in self.data.items():
            if k not in dedicated and isinstance(node, dict) and "value" in node:
                self.other_key_box.addItem(k, k)
        self.other_key_box.blockSignals(False)
        if self.other_key_box.count():
            self.other_key_box.setCurrentIndex(0)
        self._render_other_key()

        # 工人
        self.load_extra_ui()
        self.load_workers()
        if hasattr(self, "map3d_view"):
            self.refresh_map3d()

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
            name_cell = QTableWidgetItem(str(c.get("cryptoName", "")))
            name_cell.setFlags(name_cell.flags() & ~Qt.ItemIsEditable)
            self.crypto_table.setItem(row, 0, name_cell)
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
            if eng == "Upgrade":  # 存档里名为 Upgrade 的特殊项已废弃，不显示不修改
                continue
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
        # 版权水印 MD5: d41db6cc96c89ea4078521a41ab373b5
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
        selected = self.current_worker
        self.worker_list.blockSignals(True)
        self.worker_list.clear()
        query = self.search_entry.text().strip().casefold()
        selected_row = -1
        for i, worker in enumerate(self.workers):
            text = self.worker_display(worker, i)
            role_data = worker.get("npcDataRole") if isinstance(worker, dict) else None
            role = role_data.get("npcRoleId") if isinstance(role_data, dict) else None
            if not query or query in (text + " " + _ROLE_NAME.get(role, str(role))).casefold():
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, i)
                self.worker_list.addItem(item)
                if i == selected:
                    selected_row = self.worker_list.count() - 1
        self.worker_list.setCurrentRow(selected_row)
        self.worker_list.blockSignals(False)
        self.current_worker = selected if selected_row >= 0 else None
        self.worker_panel.setEnabled(self.current_worker is not None)
        self.count_lbl.setText(f"显示 {self.worker_list.count()} / {len(self.workers)} 个工人")


    def filter_workers(self):
        self.refresh_worker_list()

    def on_worker_select(self, row):
        item = self.worker_list.item(row) if row >= 0 else None
        self.current_worker = item.data(Qt.UserRole) if item else None
        self.worker_panel.setEnabled(self.current_worker is not None)
        if self.current_worker is not None:
            self.load_worker_to_ui(self.workers[self.current_worker])


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

        # 职业
        role_id = npc.get("npcRoleId", 0)
        role_id = int(role_id) if role_id not in (None, "") else 0
        idx = self.role_combo.findData(role_id)
        self.role_combo.blockSignals(True)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)
        else:
            # 未解锁/未收录职业：复用同一“未知职业”条目，避免反复累积
            label = f"未知职业({role_id})"
            u = self.role_combo.findText(label)
            if u < 0:
                self.role_combo.addItem(label, role_id)
                u = self.role_combo.count() - 1
            self.role_combo.setCurrentIndex(u)
        self.role_combo.blockSignals(False)

        # 复选框
        self.cb_tamed.blockSignals(True)
        self.cb_dead.blockSignals(True)
        self.cb_tamed.setChecked(safe_bool(worker.get("isTamed", False)))
        self.cb_dead.setChecked(safe_bool(worker.get("isDead", False)))
        self.cb_tamed.blockSignals(False)
        self.cb_dead.blockSignals(False)

    def on_worker_role_changed(self):
        """职业下拉框变更：将选中职业 id 写入当前工人的 npcRoleId。"""
        w = self.current_worker_dict()
        if w is None:
            return
        rid = self.role_combo.currentData()
        npc = w.setdefault("npcDataRole", {})
        if not isinstance(npc, dict):
            npc = w["npcDataRole"] = {}
        npc["npcRoleId"] = int(rid)

    def current_worker_dict(self):
        if self.current_worker is None or self.current_worker >= len(self.workers):
            return None
        return self.workers[self.current_worker]

    def on_worker_field_changed(self, key):
        w = self.current_worker_dict()
        if w is None or self.worker_entries.get(key) is None:
            return
        try:
            number(self.worker_entries[key].text(), label=key)
        except ValueError as exc:
            QMessageBox.warning(self, "输入无效", str(exc))
            self.load_worker_to_ui(w)
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
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
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
                w["sanityValue"] = 0  # 理智值 0=理智满；>=sanityDuration(约40~60)才会发疯，原999会必疯
                w["tameProgress"] = 100
                w["isTamed"] = True
                w["isDead"] = False
            self.log("✅ 已全部加满所有工人属性")
            if self.current_worker is not None:
                self.load_worker_to_ui(self.workers[self.current_worker])
        except Exception as e:
            self.log(f"❌ 批量修改失败: {e}")

    def reset_workers_status(self):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
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
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """复制当前选中的员工。新员工 ID 统一随机生成，
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
        # 新员工 ID 固定随机生成（不冲突），仅此一种方式
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
            cp["id"] = str(uuid.uuid4())   # 新员工 ID 随机生成
            # 新员工未放置/未生成，避免直接卡在原本位置
            cp["isSpawned"] = False
            self.workers.append(cp)
            added += 1

        self.refresh_worker_list()
        self.worker_list.setCurrentRow(len(self.workers) - 1)   # 选中最前端一个副本
        self.count_lbl.setText(f"共 {len(self.workers)} 个工人")
        self.log(f"📋 已复制 {added} 个员工（随机ID）。"
                 "记得点【保存】写盘生效。")
        self.status_lbl.setText(f"已复制 {added} 个员工，记得点【保存】写盘生效。")

    # ==================== 恢复备份 ====================
    def restore_backup(self):
        if 1 != 1:
            print("作者：com-in Github：github.com/com-in/SCS-Saves-Editor")
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        """一键恢复：从 ES3_Backups 中选择一个备份覆盖当前存档并重新加载。"""
        if not self.file_path:
            QMessageBox.information(self, "恢复备份", "请先打开一个存档，再恢复其备份。")
            return
        backup_dir = os.path.join(os.path.dirname(self.file_path), "ES3_Backups")
        if not os.path.isdir(backup_dir):
            QMessageBox.information(self, "恢复备份", "未找到备份目录\n" + backup_dir)
            return
        base = os.path.basename(self.file_path)
        prefixes = (base + ".backup_", base + ".backup_save_")
        try:
            backups = [f for f in os.listdir(backup_dir)
                       if f.startswith(prefixes)
                       and os.path.isfile(os.path.join(backup_dir, f))]
            backups.sort(key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
                         reverse=True)
        except Exception as e:
            QMessageBox.critical(self, "读取备份失败", f"错误: {e}")
            return
        if not backups:
            QMessageBox.information(self, "恢复备份",
                                    f"未找到 {base} 的备份文件。\n"
                                    f"打开/保存存档时会自动生成备份。")
            return
        picked = self._pick_backup_dialog(backups, backup_dir)
        if not picked:
            return
        src = os.path.join(backup_dir, picked)
        ans = QMessageBox.question(
            self, "确认恢复",
            f"将使用备份\n{picked}\n\n"
            f"覆盖当前存档并重新加载。\n当前存档若有未保存改动将丢失，是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if ans != QMessageBox.Yes:
            return
        try:
            shutil.copy2(src, self.file_path)
            with open(self.file_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
            self.parse_data_to_ui()
            self.setWindowTitle(f"诈骗园区模拟器 - 存档修改器  —  {base}")
            self.status_lbl.setText(f"♻️ 已恢复备份: {base}")
            self.log(f"✅ 已从备份恢复: {picked}")
            QMessageBox.information(self, "恢复完成",
                                    f"已从备份恢复：\n{picked}")
        except Exception as e:
            QMessageBox.critical(self, "恢复失败", f"错误: {e}")
            self.log(f"❌ 恢复失败: {e}")

    def _pick_backup_dialog(self, backups, backup_dir):
        """列出备份文件，返回用户选中的文件名；取消返回 None。"""
        from PySide6.QtWidgets import QDialog
        import datetime as _dt
        dlg = QDialog(self)
        dlg.setWindowTitle(f"选择备份（共 {len(backups)} 个）")
        dlg.resize(640, 440)
        lay = QVBoxLayout(dlg)
        hint = QLabel("按生成时间倒序。双击或选中后点【恢复】执行：")
        hint.setObjectName("Hint")
        lay.addWidget(hint)

        listw = QListWidget()
        for f in backups:
            p = os.path.join(backup_dir, f)
            mtime = _dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")
            it = QListWidgetItem(f"{f}   ——   {mtime}")
            it.setToolTip(p)
            it.setData(Qt.UserRole, f)
            listw.addItem(it)
        listw.setCurrentRow(0)
        listw.itemDoubleClicked.connect(lambda _: dlg.accept())
        lay.addWidget(listw, 1)

        btn_ok = QPushButton("恢复")
        btn_cancel = QPushButton("取消"); btn_cancel.setObjectName("Ghost")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        h = QHBoxLayout(); h.addStretch(1)
        h.addWidget(btn_cancel); h.addWidget(btn_ok)
        lay.addLayout(h)

        if dlg.exec() and listw.currentItem():
            return listw.currentItem().data(Qt.UserRole)
        return None

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
    app.setOrganizationName("com-in")
    app.setApplicationName("SCS-Saves-Editor")
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
    QTimer.singleShot(2000, win.check_updates)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
