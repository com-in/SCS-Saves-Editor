# -*- coding: utf-8 -*-
# =====================================================================
# Copyright (C) 2026 com-in
# 项目仓库: https://github.com/com-in/SCS-Saves-Editor
# 本程序依照 GNU 通用公共许可证 v3（或更高版本）发布。
# 严禁删除或遮蔽本版权声明；任何二次发布/修改/再分发必须遵守 GPLv3
# 并保留原作者署名。任何未经授权移除署名、抄袭、窜改归属的行为均属侵权。
# 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9（仅为版权署名追踪标识，无任何功能）
# =====================================================================
# Mod install page: BepInEx detection / installation, local mod import,
# online manifest install, and enable / disable / uninstall.
# All writes stay inside <game root>/BepInEx; nothing touches the save file.
import os
import io
import re
import ssl
import json
import ctypes
import shutil
import zipfile
import threading
import tempfile
import urllib.request
from urllib.parse import unquote, urlparse

try:                                     # Windows-only: Steam registry lookup
    import winreg
except ImportError:                      # pragma: no cover - non-Windows hosts
    winreg = None

from ctypes import wintypes

from PySide6.QtCore import Qt, Signal, QThread, QSettings, QUrl, QSignalBlocker
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QFileDialog, QMessageBox, QFrame,
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QProgressBar, QInputDialog,
)

from _memscan import find_game_process

# BepInEx release source: official GitHub repository only.
BEPINEX_API = "https://api.github.com/repos/BepInEx/BepInEx/releases/latest"
# Known-good fallback so installation still works when the API is rate-limited.
BEPINEX_FALLBACK_URL = (
    "https://github.com/BepInEx/BepInEx/releases/download/"
    "v5.4.23.5/BepInEx_win_x64_5.4.23.5.zip"
)
BEPINEX_ASSET_PREFIX = "BepInEx_win_x64"
HTTP_USER_AGENT = "SCS-Saves-Editor"
DEFAULT_MANIFEST_NAME = os.path.join("docs", "mods_index.json")
DOWNLOAD_CHUNK = 65536

PAGE_MARGIN = 16
SECTION_SPACING = 10
TABLE_MIN_HEIGHT = 180


# ============================ helpers ============================


def _http_json(url, timeout=20):
    # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
    """GET a URL and decode it as JSON."""
    request = urllib.request.Request(
        url, headers={"User-Agent": HTTP_USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _direct_mod_url_info(url):
    """Validate a direct mod URL and return (url, filename, suffix)."""
    url = str(url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError("直链必须是有效的 HTTP/HTTPS 地址。")
    filename = unquote(os.path.basename(parsed.path))
    suffix = os.path.splitext(filename.lower())[1]
    if suffix not in (".zip", ".dll"):
        raise ValueError("直链文件必须是 .zip 或 .dll（可带查询参数）。")
    return url, filename, suffix


def _bepinex_uninstall_targets(root):
    """Resolve only loader-owned paths immediately inside a Unity root."""
    if not _is_probably_root(root):
        raise RuntimeError("游戏目录无效，请重新选择。")
    root = os.path.abspath(root)
    targets = []
    config = os.path.join(root, "doorstop_config.ini")
    owns_config = False
    if os.path.isfile(config):
        with open(config, "rb") as handle:
            owns_config = b"bepinex" in handle.read().lower()
    for name in ("winhttp.dll", "version.dll"):
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as handle:
            is_doorstop = b"doorstop" in handle.read().lower()
        if is_doorstop or (name == "winhttp.dll" and owns_config):
            targets.append(path)
    if owns_config:
        targets.append(config)
        marker = os.path.join(root, ".doorstop_version")
        if os.path.isfile(marker):
            targets.append(marker)
    bepinex = os.path.join(root, "BepInEx")
    if os.path.lexists(bepinex):
        targets.append(bepinex)
    for path in targets:
        if (os.path.dirname(path) != root or os.path.islink(path)
                or os.path.normcase(os.path.realpath(path)) != os.path.normcase(path)):
            raise RuntimeError("卸载目标包含链接或重定向目录，已停止：" + path)
    return targets


GAME_NAME_HINTS = ("underkingdom", "scam center", "scamcenter", "scam_center")
MAX_PARENT_STEPS = 5


def _coerce_game_root(directory):
    """Turn a picked folder into the install root.

    Accepts the root itself, the *_Data folder, or any folder nested below the
    game data folder; walks up a few levels looking for the *_Data marker.
    """
    if not directory:
        return ""
    if _is_probably_root(directory):
        return directory
    try:
        entries = [os.path.join(directory, name) for name in os.listdir(directory)]
    except OSError:
        entries = []
    for candidate in entries:
        if os.path.isdir(candidate) and _is_probably_root(candidate):
            return candidate
    current = os.path.abspath(directory)
    for _step in range(MAX_PARENT_STEPS):
        parent = os.path.dirname(current)
        if not parent or parent == current:
            break
        current = parent
        if _is_probably_root(current):
            return current
    return ""


def _matches_game_name(text):
    """True when a folder or exe name looks like this game."""
    low = str(text or "").lower()
    return any(hint in low for hint in GAME_NAME_HINTS)


def _data_dir_name(root_dir):
    """Name of the first *_Data folder inside a directory, or ''."""
    try:
        names = os.listdir(root_dir)
    except OSError:
        return ""
    return next((n for n in names
                 if n.endswith("_Data") and os.path.isdir(os.path.join(root_dir, n))), "")


def _looks_like_game_root(path):
    """Strong match: the folder name or its *_Data folder mentions the game."""
    if not _is_probably_root(path):
        return False
    return _matches_game_name(os.path.basename(path)) or _matches_game_name(_data_dir_name(path))


def _process_image_path(pid):
    # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
    """Full path of a running process exe, or '' when unavailable."""
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            k32.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE, wintypes.DWORD, ctypes.c_wchar_p,
                ctypes.POINTER(wintypes.DWORD)]
            k32.QueryFullProcessImageNameW.restype = wintypes.BOOL
            buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            ok = k32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
            return buffer.value if ok else ""
        finally:
            k32.CloseHandle(handle)
    except Exception:                                               # noqa: BLE001
        return ""


def _parse_vdf_paths(vdf_path):
    """Extract library folders from a Steam libraryfolders.vdf (old and new)."""
    if not os.path.isfile(vdf_path):
        return []
    try:
        with io.open(vdf_path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return []
    raw = re.findall(r'"path"\s+"([^"]+)"', text) or re.findall(r'^\s*"\d+"\s+"([^"]+)"',
                                                                text, re.MULTILINE)
    return [p.replace("\\\\", "\\") for p in raw if p]


def _steam_library_roots():
    """Every SteamLibrary\\steamapps\\common folder we can discover."""
    if winreg is None:
        return []
    steam = ""
    for hive, path in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                       (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Valve\Steam"),
                       (winreg.HKEY_LOCAL_MACHINE, r"Software\Valve\Steam")):
        try:
            with winreg.OpenKey(hive, path) as key:
                steam = winreg.QueryValueEx(key, "InstallPath")[0]
                if steam:
                    break
        except OSError:
            continue
    if not steam:
        return []
    roots = [os.path.join(steam, "steamapps", "common")]
    for library in _parse_vdf_paths(os.path.join(steam, "steamapps", "libraryfolders.vdf")):
        roots.append(os.path.join(library, "steamapps", "common"))
    return roots


def _default_game_roots():
    """Epic Games and a few usual install locations."""
    roots = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "SystemDrive"):
        base = os.environ.get(variable, "")
        if not base:
            continue
        if variable == "SystemDrive":
            base = base + os.sep
        epic = os.path.join(base, "Epic Games")
        if os.path.isdir(epic):
            roots.append(epic)
    for drive in ("C", "D", "E", "F", "G"):
        for name in ("SteamLibrary", "Steam", "Games", "Game"):
            candidate = f"{drive}:\\{name}\\steamapps\\common"
            if os.path.isdir(candidate):
                roots.append(candidate)
    return roots


def _detect_game_roots():
    """Best-effort scan for the game install root.

    Order: running game process, then Steam libraries, then Epic / usual spots.
    Returns a list of candidate roots, strongest match first.
    """
    found, seen = [], set()

    def _add(path):
        if not path:
            return
        path = os.path.abspath(path)
        key = path.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(path)

    # 1) A running game gives the exact folder immediately.
    pid = None
    try:
        pid, _name = find_game_process()
    except Exception:                                               # noqa: BLE001
        pid = None
    if pid:
        exe = _process_image_path(pid)
        if exe:
            root = os.path.dirname(exe)
            if _looks_like_game_root(root) or _is_probably_root(root):
                _add(root)

    # 2) Scan Steam libraries and usual install folders.
    for parent in _steam_library_roots() + _default_game_roots():
        if not os.path.isdir(parent):
            continue
        try:
            entries = os.listdir(parent)
        except OSError:
            continue
        for name in entries:
            path = os.path.join(parent, name)
            if os.path.isdir(path) and _looks_like_game_root(path):
                _add(path)
            # Steam sometimes nests the game one level deeper.
            if os.path.isdir(path) and not _looks_like_game_root(path):
                try:
                    children = os.listdir(path)
                except OSError:
                    continue
                for child in children:
                    child_path = os.path.join(path, child)
                    if os.path.isdir(child_path) and _looks_like_game_root(child_path):
                        _add(child_path)
    return found


def _resolve_bepinex_asset():
    # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
    """Pick the Windows x64 BepInEx asset from the latest official release."""
    data = _http_json(BEPINEX_API)
    assets = data.get("assets") or []
    for asset in assets:
        name = str(asset.get("name") or "")
        if name.startswith(BEPINEX_ASSET_PREFIX) and name.lower().endswith(".zip"):
            return str(asset.get("browser_download_url"))
    raise RuntimeError("latest release has no Windows x64 asset")


def _safe_join(root_dir, relative):
    """Join a path and reject anything escaping root_dir (zip-slip guard)."""
    root_dir = os.path.abspath(root_dir)
    target = os.path.abspath(os.path.join(root_dir, relative))
    if target == root_dir or target.startswith(root_dir + os.sep):
        return target
    return None


def _is_probably_root(directory):
    """True when the directory looks like a Unity game install root."""
    if not directory or not os.path.isdir(directory):
        return False
    try:
        names = os.listdir(directory)
    except OSError:
        return False
    return any(name.endswith("_Data") and os.path.isdir(os.path.join(directory, name))
               for name in names)


def _unity_backend(root_dir):
    """Return 'mono' / 'il2cpp' / 'unknown' for a Unity install root."""
    data_dirs = [os.path.join(root_dir, name) for name in os.listdir(root_dir)
                 if name.endswith("_Data") and os.path.isdir(os.path.join(root_dir, name))]
    for data_dir in data_dirs:
        managed = os.path.join(data_dir, "Managed")
        il2cpp = os.path.join(data_dir, "il2cpp")
        if os.path.isdir(il2cpp):
            return "il2cpp"
        if os.path.isdir(managed):
            return "mono"
    return "unknown"


def _entry_size(path):
    """Total byte size of a file or directory tree."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def _human_size(value):
    """Format a byte count in Chinese units."""
    step = 1024.0
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < step or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= step
    return f"{size:.1f} GB"


def _split_path(member):
    """Split an archive member into non-empty path parts."""
    return [p for p in member.replace("\\", "/").split("/") if p]


def _archive_files(names):
    """Drop directories and macOS metadata noise from an archive listing."""
    files = [n for n in names if not n.endswith("/")]
    return [n for n in files if "__MACOSX/" not in n
            and not os.path.basename(n).startswith(".")]


def _has_plugin_dll(names):
    """True when the archive carries at least one plugin dll."""
    return any(n.lower().endswith(".dll") for n in names)


def _is_bepinex_package(names):
    """True when archive members sit under a top-level BepInEx/ folder."""
    return any(_split_path(n)[:1] == ["BepInEx"] or _split_path(n)[:1] == ["bepinex"]
               for n in names)


def _plugin_names_in_archive(names):
    """Top-level entry names that land in the plugins folder, in first-seen order."""
    result = []
    for name in _archive_files(names):
        parts = _split_path(name)
        lowered = [p.lower() for p in parts]
        if "bepinex" in lowered and "plugins" in lowered:
            index = lowered.index("plugins", lowered.index("bepinex"))
            rel = parts[index + 1:]
        elif "plugins" in lowered:
            rel = parts[lowered.index("plugins") + 1:]
        else:
            continue
        if rel and rel[0] not in result:
            result.append(rel[0])
    return result


def _plan_entry_map(names):
    """Map archive members to destinations under the plugins folder.

    Used for archives that are not full BepInEx packages. Returns
    {member: relative_path} or None when nothing looks installable.
    Layouts understood:
      plugins/<X>/...   -> <X>/...   (partial package layout)
      Foo.dll           -> Foo.dll   (bare dll at archive root)
      <wrapper>/...     -> ...       (single wrapper folder holding a dll)
    """
    files = _archive_files(names)
    if not files:
        return None

    plans = {}
    for member in files:
        parts = _split_path(member)
        lowered = [p.lower() for p in parts]
        rel = None
        if "plugins" in lowered:
            rel = parts[lowered.index("plugins") + 1:]
        elif len(parts) == 1 and parts[0].lower().endswith(".dll"):
            rel = parts
        if rel:
            plans[member] = "/".join(rel)
    if plans:
        return plans

    # A single wrapper folder (very common in downloaded mod packs) is stripped,
    # but only when the archive really carries a dll - otherwise random zips of
    # notes or textures would be copied into the plugins folder.
    tops = {(_split_path(member) or [""])[0] for member in files}
    if len(tops) == 1 and _has_plugin_dll(files):
        return {member: "/".join(_split_path(member)[1:]) for member in files
                if len(_split_path(member)) > 1}
    return None


def _scan_plugin_entries(plugins_dir):
    """List plugin entries below a plugins folder: [(name, kind, enabled, path)]."""
    rows = []
    if not os.path.isdir(plugins_dir):
        return rows
    try:
        names = sorted(os.listdir(plugins_dir))
    except OSError:
        return rows
    for name in names:
        if name.lower() == "disabled":
            continue
        path = os.path.join(plugins_dir, name)
        if os.path.isfile(path):
            if not name.lower().endswith(".dll"):
                continue
            kind = "DLL"
        elif os.path.isdir(path):
            kind = "文件夹"
        else:
            continue
        rows.append((name, kind, True, path))
    return rows


# ============================ workers ============================


class _DownloadWorker(QThread):
    # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
    """Download a URL into a temporary file and report byte progress."""

    progress = Signal(int, int)        # received bytes, total bytes (0 = unknown)
    finished_ok = Signal(str)          # temp file path
    failed = Signal(str)

    def __init__(self, url, suffix=".zip", parent=None):
        super().__init__(parent)
        self.url = url
        self.suffix = suffix
        self._tmp = None
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def _cleanup(self):
        try:
            if self._tmp and os.path.isfile(self._tmp):
                os.remove(self._tmp)
        except OSError:
            pass

    def run(self):
        try:
            request = urllib.request.Request(self.url, headers={"User-Agent": HTTP_USER_AGENT})
            context = ssl.create_default_context()
            with urllib.request.urlopen(request, timeout=30, context=context) as response:
                total = int(response.headers.get("Content-Length") or 0)
                handle, self._tmp = tempfile.mkstemp(suffix=self.suffix, prefix="scs_")
                os.close(handle)
                received = 0
                with open(self._tmp, "wb") as output:
                    while True:
                        if self._cancel.is_set():
                            raise RuntimeError("download cancelled")
                        chunk = response.read(DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        output.write(chunk)
                        received += len(chunk)
                        self.progress.emit(received, total)
            if self._cancel.is_set():
                raise RuntimeError("download cancelled")
            self.finished_ok.emit(self._tmp)
        except Exception as exc:                                    # noqa: BLE001
            self._cleanup()
            self.failed.emit(str(exc))


class _CallWorker(QThread):
    # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
    """Run a plain callable off the GUI thread and emit its result."""

    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self.func = func
        self._cancel = threading.Event()

    def cancel(self):
        """Suppress the result when the caller cancels a non-interruptible call."""
        self._cancel.set()

    def run(self):
        try:
            result = self.func()
            if not self._cancel.is_set():
                self.finished_ok.emit(result)
        except Exception as exc:                                    # noqa: BLE001
            if not self._cancel.is_set():
                self.failed.emit(str(exc))


# ============================ page mixin ============================


class ModsPageMixin:
    """Mod installation utilities for the main editor window."""

    # ---------------- UI ----------------
    def build_mods_tab(self):
        # 版权水印 MD5: 46af17afd73a500c120d6c4f0611dac9
        self.tab_mods.setObjectName("ModsPage")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFocusPolicy(Qt.NoFocus)
        inner = QWidget()
        body = QVBoxLayout(inner)
        body.setContentsMargins(PAGE_MARGIN, 12, PAGE_MARGIN, 10)
        body.setSpacing(SECTION_SPACING)
        scroll.setWidget(inner)
        outer = QVBoxLayout(self.tab_mods)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

        title_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("安装 Mod")
        title.setObjectName("PageTitle")
        title_col.addWidget(title)
        sub = QLabel("为本机游戏安装 BepInEx 加载器与插件 Mod")
        sub.setObjectName("Muted")
        title_col.addWidget(sub)
        title_row.addLayout(title_col, 1)
        scope = QLabel("仅写入 BepInEx")
        scope.setObjectName("ModsScopeBadge")
        scope.setToolTip("安装、启用、禁用和卸载都只操作游戏目录下的 BepInEx 文件夹")
        title_row.addWidget(scope, 0, Qt.AlignTop)
        body.addLayout(title_row)

        hint = QLabel("安装前请退出游戏并确认 Mod 来源可信；本页不会读取或修改存档文件。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        body.addWidget(hint)

        body.addWidget(self._mods_build_dir_card())
        body.addWidget(self._mods_build_loader_card())
        body.addWidget(self._mods_build_local_card())
        body.addWidget(self._mods_build_online_card())
        body.addWidget(self._mods_build_installed_card())

        self.mods_progress = QProgressBar()
        self.mods_progress.setObjectName("ModsTaskProgress")
        self.mods_progress.setTextVisible(True)
        self.mods_progress.setRange(0, 100)
        self.mods_progress.setValue(0)
        self.mods_progress.setFixedWidth(190)
        self.mods_progress.setMinimumHeight(24)
        self.mods_cancel_btn = QPushButton("取消")
        self.mods_cancel_btn.setObjectName("Ghost")
        self.mods_cancel_btn.setMinimumHeight(24)
        self.mods_cancel_btn.setMinimumWidth(56)
        self.mods_cancel_btn.setEnabled(False)
        self.mods_cancel_btn.clicked.connect(self._mods_cancel_task)

        self.mods_status = QLabel("")
        self.mods_status.setObjectName("Muted")
        self.mods_status.setWordWrap(True)
        body.addWidget(self.mods_status)
        body.addStretch(1)

        self._mods_worker = None
        self._mods_online_rows = []
        self._mods_init_state()
        self._mods_refresh_loader()
        self._mods_refresh_installed()

    def _mods_attach_progress_to_statusbar(self):
        """Place task progress at the right side of the global status bar."""
        status_bar = getattr(self, "statusBar", None)
        if status_bar is None or getattr(self, "_mods_progress_attached", False):
            return
        status_bar.addPermanentWidget(self.mods_progress)
        status_bar.addPermanentWidget(self.mods_cancel_btn)
        self._mods_progress_attached = True

    def _mods_frame(self, title_text):
        """A titled card frame with an internal vertical layout."""
        frame = QFrame()
        frame.setObjectName("CardBox")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)
        return frame, lay

    def _mods_card_heading(self, lay, title_text, caption=""):
        """Add a compact section heading with optional supporting caption."""
        row = QHBoxLayout()
        row.setSpacing(8)
        head = QLabel(title_text)
        head.setObjectName("CardTitle")
        row.addWidget(head)
        if caption:
            caption_label = QLabel(caption)
            caption_label.setObjectName("ModsSectionCaption")
            row.addWidget(caption_label)
        row.addStretch(1)
        lay.addLayout(row)

    def _mods_build_dir_card(self):
        frame, lay = self._mods_frame("游戏目录")
        self._mods_card_heading(lay, "游戏目录", "安装目标")

        row = QHBoxLayout()
        path_label = QLabel("路径")
        path_label.setObjectName("ModsFieldLabel")
        row.addWidget(path_label)
        self.mods_dir_edit = QLineEdit()
        self.mods_dir_edit.setReadOnly(True)
        self.mods_dir_edit.setPlaceholderText("未选择，点击右侧按钮定位游戏安装目录")
        row.addWidget(self.mods_dir_edit, 1)
        auto = QPushButton("自动查找")
        auto.setToolTip("扫描 Steam 库、Epic 目录和正在运行的游戏进程，自动定位安装目录")
        auto.clicked.connect(self._mods_auto_detect)
        row.addWidget(auto)
        pick = QPushButton("选择…")
        pick.setObjectName("Secondary")
        pick.clicked.connect(self._mods_pick_game_dir)
        row.addWidget(pick)
        open_btn = QPushButton("打开目录")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(lambda: self._mods_open_dir("game"))
        row.addWidget(open_btn)
        lay.addLayout(row)

        note = QLabel("选择游戏根目录即可；选中 xxx_Data 或其子目录时会自动向上归位。")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        lay.addWidget(note)
        return frame

    def _mods_build_loader_card(self):
        frame, lay = self._mods_frame("BepInEx 加载器")
        self._mods_card_heading(lay, "BepInEx 加载器", "Mod 运行基础")

        status_row = QHBoxLayout()
        self.mods_loader_state = QLabel("未安装")
        self.mods_loader_state.setObjectName("StatusChip")
        status_row.addWidget(self.mods_loader_state)
        self.mods_backend_lbl = QLabel("")
        self.mods_backend_lbl.setObjectName("Muted")
        status_row.addWidget(self.mods_backend_lbl)
        status_row.addStretch(1)
        lay.addLayout(status_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.mods_install_loader_btn = QPushButton("安装加载器")
        self.mods_install_loader_btn.clicked.connect(self._mods_install_bepinex)
        actions.addWidget(self.mods_install_loader_btn)
        local_btn = QPushButton("本地加载器包…")
        local_btn.setObjectName("Secondary")
        local_btn.setToolTip("选择已下载好的 BepInEx_win_x64_*.zip 手动安装")
        local_btn.clicked.connect(self._mods_install_bepinex_local)
        actions.addWidget(local_btn)
        actions.addStretch(1)
        bep_btn = QPushButton("打开 BepInEx 目录")
        bep_btn.setObjectName("Ghost")
        bep_btn.clicked.connect(lambda: self._mods_open_dir("bepinex"))
        actions.addWidget(bep_btn)
        plug_btn = QPushButton("打开插件目录")
        plug_btn.setObjectName("Ghost")
        plug_btn.clicked.connect(lambda: self._mods_open_dir("plugins"))
        actions.addWidget(plug_btn)
        lay.addLayout(actions)

        uninstall_row = QHBoxLayout()
        uninstall = QPushButton("卸载 BepInEx 和全部 Mod…")
        uninstall.setObjectName("Danger")
        uninstall.clicked.connect(self._mods_uninstall_bepinex)
        uninstall_row.addWidget(uninstall)
        uninstall_row.addStretch(1)
        lay.addLayout(uninstall_row)

        note = QLabel(
            "加载器来自 BepInEx 官方 GitHub 发行包；安装时若游戏正在运行，请先退出游戏。")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        lay.addWidget(note)
        return frame

    def _mods_build_local_card(self):
        frame, lay = self._mods_frame("本地安装")
        self._mods_card_heading(lay, "本地安装", "导入文件或粘贴直链")

        row = QHBoxLayout()
        row.setSpacing(8)
        source_label = QLabel("文件")
        source_label.setObjectName("ModsFieldLabel")
        row.addWidget(source_label)
        self.mods_local_btn = QPushButton("选择 Mod 文件并安装…")
        self.mods_local_btn.clicked.connect(self._mods_install_local)
        row.addWidget(self.mods_local_btn)
        row.addStretch(1)
        lay.addLayout(row)

        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        link_label = QLabel("直链")
        link_label.setObjectName("ModsFieldLabel")
        link_row.addWidget(link_label)
        self.mods_direct_url_edit = QLineEdit()
        self.mods_direct_url_edit.setPlaceholderText("文件直链：https://.../mod.zip 或 mod.dll")
        self.mods_direct_url_edit.setToolTip("填写可直接下载文件的 HTTP/HTTPS 地址，支持 .zip/.dll 及查询参数")
        self.mods_direct_url_edit.returnPressed.connect(self._mods_install_direct_url)
        link_row.addWidget(self.mods_direct_url_edit, 1)
        direct_btn = QPushButton("下载并安装")
        direct_btn.setObjectName("Secondary")
        direct_btn.clicked.connect(self._mods_install_direct_url)
        link_row.addWidget(direct_btn)
        lay.addLayout(link_row)
        note = QLabel(
            "支持 .zip 压缩包（BepInEx 布局、plugins 布局或单个根目录包裹均可）与单个 .dll 文件，"
            "以及文件直链；程序会自动识别并放入 BepInEx\\plugins。")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        lay.addWidget(note)
        return frame

    def _mods_build_online_card(self):
        frame, lay = self._mods_frame("在线 Mod 清单")
        self._mods_card_heading(lay, "在线 Mod 清单", "从 JSON 清单批量安装")

        row = QHBoxLayout()
        row.setSpacing(8)
        source_label = QLabel("清单")
        source_label.setObjectName("ModsFieldLabel")
        row.addWidget(source_label)
        self.mods_manifest_edit = QLineEdit()
        self.mods_manifest_edit.setPlaceholderText("清单地址：https://.../mods_index.json 或本地 json 路径")
        self.mods_manifest_edit.setToolTip("清单为 JSON：{\"mods\": [{\"name\",\"version\",\"author\",\"description\",\"download\",\"homepage\"}]}")
        self.mods_manifest_edit.editingFinished.connect(self._mods_save_manifest_url)
        row.addWidget(self.mods_manifest_edit, 1)
        browse = QPushButton("本地清单…")
        browse.setObjectName("Secondary")
        browse.clicked.connect(self._mods_pick_manifest)
        row.addWidget(browse)
        refresh = QPushButton("刷新")
        refresh.setObjectName("Secondary")
        refresh.clicked.connect(self._mods_refresh_online)
        row.addWidget(refresh)
        lay.addLayout(row)

        self.mods_online_table = QTableWidget(0, 5)
        self.mods_online_table.setHorizontalHeaderLabels(["名称", "版本", "作者", "说明", "状态"])
        self.mods_online_table.verticalHeader().setVisible(False)
        self.mods_online_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mods_online_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mods_online_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.mods_online_table.setMinimumHeight(TABLE_MIN_HEIGHT)
        header = self.mods_online_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        lay.addWidget(self.mods_online_table)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        install = QPushButton("安装所选")
        install.clicked.connect(self._mods_install_online_selected)
        row2.addWidget(install)
        home = QPushButton("打开主页")
        home.setObjectName("Ghost")
        home.clicked.connect(self._mods_open_selected_homepage)
        row2.addWidget(home)
        row2.addStretch(1)
        lay.addLayout(row2)
        return frame

    def _mods_build_installed_card(self):
        frame, lay = self._mods_frame("已安装 Mod")
        self._mods_card_heading(lay, "已安装 Mod", "启用、禁用或卸载")

        self.mods_installed_summary = QLabel("正在读取插件目录…")
        self.mods_installed_summary.setObjectName("ModsSectionCaption")
        lay.addWidget(self.mods_installed_summary)

        self.mods_installed_table = QTableWidget(0, 5)
        self.mods_installed_table.setHorizontalHeaderLabels(["名称", "类型", "状态", "大小", "路径"])
        self.mods_installed_table.verticalHeader().setVisible(False)
        self.mods_installed_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.mods_installed_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.mods_installed_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.mods_installed_table.setMinimumHeight(TABLE_MIN_HEIGHT)
        header = self.mods_installed_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        lay.addWidget(self.mods_installed_table)

        row = QHBoxLayout()
        row.setSpacing(8)
        enable = QPushButton("启用")
        enable.setObjectName("Secondary")
        enable.clicked.connect(lambda: self._mods_toggle_selected(True))
        row.addWidget(enable)
        disable = QPushButton("禁用")
        disable.setObjectName("Secondary")
        disable.clicked.connect(lambda: self._mods_toggle_selected(False))
        row.addWidget(disable)
        remove = QPushButton("卸载")
        remove.setObjectName("Danger")
        remove.clicked.connect(self._mods_uninstall_selected)
        row.addWidget(remove)
        row.addStretch(1)
        ref = QPushButton("刷新")
        ref.setObjectName("Ghost")
        ref.clicked.connect(self._mods_refresh_installed)
        row.addWidget(ref)
        lay.addLayout(row)

        note = QLabel("禁用 = 移动到 BepInEx\\plugins\\disabled；卸载 = 从插件目录删除该文件/文件夹。")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        lay.addWidget(note)
        return frame

    # ---------------- state helpers ----------------
    def _mods_init_state(self):
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULT_MANIFEST_NAME)
        value = QSettings().value("mods/manifest_url", "") or ""
        if not value and os.path.isfile(local_path):
            value = local_path
        with QSignalBlocker(self.mods_manifest_edit):
            self.mods_manifest_edit.setText(value)

    def _mods_root(self):
        """Resolve the game install root, falling back to the map page setting."""
        settings = QSettings()
        stored = settings.value("mods/game_dir", "") or ""
        root = _coerce_game_root(stored)
        if root:
            root = os.path.normpath(os.path.abspath(root))
            # Repair old/relative settings and keep the UI tied to the actual
            # installation root instead of re-evaluating the original pick.
            if str(stored) != root:
                settings.setValue("mods/game_dir", root)
            return root
        data_dir = settings.value("map/game_data_dir", "") or ""
        root = _coerce_game_root(data_dir)
        if root:
            root = os.path.normpath(os.path.abspath(root))
            settings.setValue("mods/game_dir", root)
            return root
        return ""

    def _mods_plugins_dir(self, root=None):
        root = root or self._mods_root()
        if not root:
            return ""
        return os.path.join(root, "BepInEx", "plugins")

    def _mods_save_manifest_url(self):
        QSettings().setValue("mods/manifest_url", self.mods_manifest_edit.text().strip())

    def _mods_pick_game_dir(self):
        current = self._mods_root() or os.path.dirname(os.path.abspath(__file__))
        directory = QFileDialog.getExistingDirectory(self, "选择游戏安装目录", current)
        if not directory:
            return
        directory = _coerce_game_root(directory) or directory
        if not _is_probably_root(directory):
            QMessageBox.warning(
                self, "目录不正确",
                "在所选目录及其上级目录中都没有找到 *_Data 子目录。\n\n"
                "请选择游戏的安装根目录，也就是和 xxx_Data 同级、"
                "里面放着游戏 exe 的那一层；也可以直接选 xxx_Data 目录本身，"
                "或点“自动查找”让程序扫描。")
            return
        self._mods_accept_root(directory)

    def _mods_accept_root(self, root):
        """Persist a resolved game root and refresh the page."""
        root = _coerce_game_root(root)
        if not root:
            return False
        root = os.path.normpath(os.path.abspath(root))
        QSettings().setValue("mods/game_dir", root)
        self.mods_dir_edit.setText(root)
        self._mods_refresh_loader()
        self._mods_refresh_installed()
        return True

    def _mods_auto_detect(self):
        """Scan Steam / Epic / the running game for the install folder."""
        if self._mods_is_busy():
            QMessageBox.information(self, "任务进行中", "已有任务正在运行，请稍候。")
            return
        self._mods_cancel_requested = False
        self.mods_progress.setMaximum(0)
        self.mods_cancel_btn.setEnabled(True)
        self.mods_status.setText("正在查找游戏安装目录…")
        worker = _CallWorker(_detect_game_roots, parent=self)
        self._mods_worker = worker
        self._mods_mode = "detect"
        worker.finished_ok.connect(self._mods_on_detected)
        worker.failed.connect(self._mods_fail)
        worker.finished.connect(self._mods_clear_worker)
        worker.start()

    def _mods_on_detected(self, roots):
        self.mods_progress.setMaximum(100)
        if not roots:
            self._mods_fail(
                "没有自动找到游戏目录：只扫描了 Steam 库、Epic 目录和常见安装位置。"
                "请点“选择…”手动指定，或先启动游戏再点“自动查找”。")
            return
        if len(roots) == 1:
            self._mods_accept_root(roots[0])
            self._mods_ok(f"已定位游戏目录：{roots[0]}")
            return
        choice, accepted = QInputDialog.getItem(
            self, "选择游戏目录", f"找到 {len(roots)} 个候选，请选择要使用的安装目录：",
            roots, 0, False)
        if not accepted:
            self.mods_status.setText("已取消选择")
            return
        self._mods_accept_root(choice)
        self._mods_ok(f"已定位游戏目录：{choice}")

    def _mods_open_dir(self, kind):
        root = self._mods_root()
        if not root:
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        if kind == "plugins":
            target = self._mods_plugins_dir(root)
            if not os.path.isdir(target):
                QMessageBox.information(self, "目录不存在", "插件目录还不存在，请先安装加载器或 Mod。")
                return
        elif kind == "bepinex":
            target = os.path.join(root, "BepInEx")
            if not os.path.isdir(target):
                QMessageBox.information(self, "目录不存在", "BepInEx 目录还不存在，请先安装加载器。")
                return
        else:
            target = root
        try:
            # On Windows this is more reliable than delegating a directory URL
            # through the default browser/file handler.
            if hasattr(os, "startfile"):
                os.startfile(target)
                return
        except OSError:
            pass
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(target)):
            QMessageBox.warning(self, "无法打开目录", f"系统未能打开目录：\n{target}")

    # ---------------- loader detection ----------------
    def _mods_detect_loader(self, root):
        """Inspect a game root and return a BepInEx state dict."""
        state = {"root": root, "installed": False, "version": "", "backend": "unknown",
                 "plugins": 0, "has_doorstop": False, "core_count": 0}
        if not root:
            return state
        state["backend"] = _unity_backend(root)
        core = os.path.join(root, "BepInEx", "core")
        core_files = []
        if os.path.isdir(core):
            core_files = [n for n in os.listdir(core) if n.lower().endswith(".dll")]
        state["core_count"] = len(core_files)
        state["installed"] = state["core_count"] > 0
        names = os.listdir(root)
        state["has_doorstop"] = any(n.lower() in ("winhttp.dll", "version.dll") for n in names)
        plugins = self._mods_plugins_dir(root)
        state["plugins"] = len(_scan_plugin_entries(plugins)) if os.path.isdir(plugins) else 0
        return state

    def _mods_refresh_loader(self):
        root = self._mods_root()
        self.mods_dir_edit.setText(root)
        state = self._mods_detect_loader(root)
        backend = {"mono": "Mono", "il2cpp": "IL2CPP", "unknown": "未知运行时"}[state["backend"]]
        if not root:
            self.mods_loader_state.setText("未选择游戏目录")
            self.mods_loader_state.setProperty("active", False)
            self.mods_backend_lbl.setText("")
        elif state["installed"]:
            self.mods_loader_state.setText("已安装 BepInEx")
            self.mods_loader_state.setProperty("active", True)
            extra = "" if state["has_doorstop"] else " · 缺少 winhttp.dll 注入文件"
            self.mods_backend_lbl.setText(
                f"{backend} · core {state['core_count']} 个 dll · 插件 {state['plugins']} 个{extra}")
        else:
            self.mods_loader_state.setText("未安装")
            self.mods_loader_state.setProperty("active", False)
            self.mods_backend_lbl.setText(f"{backend} · 安装后游戏启动时才会加载 mod")
        self.mods_loader_state.style().polish(self.mods_loader_state)
        self.mods_install_loader_btn.setText(
            "修复/重装加载器" if state["installed"] else "安装加载器")

    # ---------------- loader installation ----------------
    def _mods_uninstall_bepinex(self):
        root = self._mods_root()
        if not root:
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        if self._mods_is_busy():
            QMessageBox.information(self, "任务进行中", "请等待当前任务结束后再卸载。")
            return
        if self._mods_game_running():
            QMessageBox.warning(self, "游戏正在运行", "请先退出游戏再卸载。")
            return
        try:
            targets = _bepinex_uninstall_targets(root)
        except Exception as exc:
            self._mods_fail(str(exc))
            return
        if not targets:
            QMessageBox.information(self, "无需卸载", "该目录没有发现 BepInEx 或加载器文件。")
            return
        listing = "\n".join(targets)
        answer = QMessageBox.question(
            self, "确认卸载 BepInEx 和全部 Mod",
            "将永久删除 BepInEx 目录中的全部 Mod（含已禁用项）、配置、缓存和日志，"
            "以及已识别的加载器文件。无法撤销。\n\n" + listing + "\n\n确定继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        failures = []
        try:
            # Validate again after the confirmation dialog before any deletion.
            current = _bepinex_uninstall_targets(root)
            if current != targets:
                raise RuntimeError("卸载目标已变化，请重新操作。")
            for path in targets:
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except OSError as exc:
                    failures.append(f"{path}：{exc}")
        except Exception as exc:
            failures.append(str(exc))
        self._mods_refresh_loader()
        self._mods_refresh_installed()
        if self._mods_online_rows:
            self._mods_on_manifest({"mods": self._mods_online_rows})
        if failures:
            self._mods_fail("卸载未完成：" + "；".join(failures))
        else:
            self._mods_ok("已卸载 BepInEx 和全部 Mod")

    def _mods_install_bepinex(self):
        root = self._mods_root()
        if not root:
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        if self._mods_game_running():
            QMessageBox.warning(self, "游戏正在运行",
                                "检测到游戏进程仍在运行，写入可能被占用。请先退出游戏再安装。")
            return
        if self._mods_is_busy():
            QMessageBox.information(self, "任务进行中", "已有任务正在运行，请稍候。")
            return
        self._mods_cancel_requested = False
        self.mods_progress.setMaximum(0)
        self.mods_cancel_btn.setEnabled(True)
        self.mods_status.setText("正在解析 BepInEx 最新版本…")
        worker = _CallWorker(_resolve_bepinex_asset, parent=self)
        self._mods_worker = worker
        self._mods_mode = "resolve"
        worker.finished_ok.connect(self._mods_on_bepinex_resolved)
        worker.failed.connect(self._mods_on_bepinex_resolve_failed)
        worker.finished.connect(self._mods_clear_worker)
        worker.start()

    def _mods_on_bepinex_resolved(self, url):
        self.mods_progress.setMaximum(100)
        self._mods_start_download(url, "正在下载 BepInEx…", "bepinex")

    def _mods_on_bepinex_resolve_failed(self, message):
        # The GitHub API can be rate limited; fall back to the pinned release.
        self.mods_status.setText(f"解析最新版本失败（{message}），改用固定版本下载…")
        self.mods_progress.setMaximum(100)
        self._mods_start_download(BEPINEX_FALLBACK_URL, "正在下载 BepInEx…", "bepinex")

    def _mods_install_bepinex_local(self):
        root = self._mods_root()
        if not root:
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 BepInEx 发行包", self._mods_root(), "压缩包 (*.zip);;所有文件 (*.*)")
        if not path:
            return
        self._mods_install_bepinex_archive(path)

    def _mods_install_bepinex_archive(self, archive):
        try:
            with zipfile.ZipFile(archive) as archive_file:
                count = self._extract_all(archive_file, self._mods_root(),
                                          archive_file.namelist())
            if not count:
                raise RuntimeError("包内没有可写入的文件")
        except Exception as exc:                                    # noqa: BLE001
            self._mods_fail(f"加载器安装失败：{exc}")
            return
        self._mods_refresh_loader()
        self._mods_refresh_installed()
        self._mods_ok(f"已安装 {count} 个加载器文件，现在可以把 mod 放进 BepInEx\\plugins 了")

    # ---------------- local / online install ----------------
    def _mods_install_local(self):
        plugins = self._mods_plugins_dir()
        if not plugins:
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Mod 文件", "",
            "支持的文件 (*.zip *.dll *.7z);;压缩包 (*.zip);;插件 (*.dll);;所有文件 (*.*)")
        if not path:
            return
        self._mods_install_file(path)

    def _mods_install_direct_url(self):
        """Download and install one mod from a direct HTTP(S) file URL."""
        if not self._mods_plugins_dir():
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        if self._mods_is_busy():
            QMessageBox.information(self, "任务进行中", "已有任务正在运行，请稍候。")
            return
        try:
            url, filename, suffix = _direct_mod_url_info(
                self.mods_direct_url_edit.text())
        except ValueError as exc:
            self._mods_fail(str(exc))
            return
        self._mods_cancel_requested = False
        self._mods_download_errors = []
        self._mods_download_queue = []
        name = os.path.splitext(filename)[0] if suffix == ".dll" else filename
        self._mods_start_download(
            url, f"正在下载 {name}…", "direct",
            payload={"name": name, "download": url})

    def _mods_install_file(self, path):
        """Install one local archive or dll into the plugins folder."""
        plugins = self._mods_plugins_dir()
        if not plugins:
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        os.makedirs(plugins, exist_ok=True)
        try:
            low = path.lower()
            if low.endswith(".dll"):
                target = os.path.join(plugins, os.path.basename(path))
                shutil.copy2(path, target)
                names = [os.path.basename(path)]
            elif low.endswith(".zip"):
                names = self._extract_mod_archive(path, self._mods_root())
            elif low.endswith(".7z"):
                self._mods_fail("暂不支持 7z 包，请先解压后选择里面的 zip 或 dll。")
                return
            else:
                self._mods_fail("不支持的文件类型，请选择 .zip 或 .dll。")
                return
        except Exception as exc:                                    # noqa: BLE001
            self._mods_fail(f"安装失败：{exc}")
            return
        self._mods_refresh_loader()
        self._mods_refresh_installed()
        self._mods_ok(f"已安装：{', '.join(names)}")

    def _mods_install_online_selected(self):
        rows = self._mods_selected_online()
        if not rows:
            QMessageBox.information(self, "未选择 Mod", "请先在清单中选择要安装的 Mod。")
            return
        if not self._mods_plugins_dir():
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        self._mods_cancel_requested = False
        self._mods_download_errors = []
        self._mods_download_queue = list(rows)
        self._mods_download_next()

    def _mods_selected_online(self):
        rows = []
        seen = set()
        for index in self.mods_online_table.selectionModel().selectedRows():
            row = index.row()
            if row in seen:
                continue
            seen.add(row)
            if row < len(self._mods_online_rows):
                rows.append(self._mods_online_rows[row])
        return rows

    def _mods_download_next(self):
        if not getattr(self, "_mods_download_queue", None):
            self._mods_refresh_installed()
            errors = getattr(self, "_mods_download_errors", [])
            if getattr(self, "_mods_cancel_requested", False):
                self._mods_fail("所选 Mod 安装已取消")
            elif errors:
                self._mods_fail("部分 Mod 安装失败：" + "、".join(errors))
            else:
                self._mods_ok("所选 Mod 安装完成")
            return
        mod = self._mods_download_queue.pop(0)
        url = str(mod.get("download") or "").strip()
        if not url:
            name = str(mod.get("name") or "未命名")
            self._mods_download_errors.append(f"{name}（没有下载地址）")
            self._mods_download_next()
            return
        self._mods_start_download(
            url, f"正在下载 {mod.get('name', 'Mod')}…", "mod", payload=mod)

    # ---------------- downloads ----------------
    def _mods_is_busy(self):
        """True while a background Mods task owns the progress bar."""
        worker = getattr(self, "_mods_worker", None)
        return bool(worker) and worker.isRunning()

    def _mods_start_download(self, url, label, mode, payload=None):
        self._mods_mode = mode
        self._mods_payload = payload
        self.mods_progress.setMaximum(100)
        self.mods_progress.setValue(0)
        self.mods_cancel_btn.setEnabled(True)
        self.mods_status.setText(label)
        worker = _DownloadWorker(url, parent=self)
        self._mods_worker = worker
        worker.progress.connect(self._mods_on_progress)
        worker.finished_ok.connect(self._mods_on_downloaded)
        worker.failed.connect(self._mods_on_download_failed)
        worker.finished.connect(self._mods_clear_worker)
        worker.start()

    def _mods_cancel_task(self):
        worker = getattr(self, "_mods_worker", None)
        if worker and worker.isRunning():
            self._mods_cancel_requested = True
            worker.cancel()
            self._mods_download_queue = []
            self.mods_status.setText("已取消")
            self.mods_cancel_btn.setEnabled(False)

    def _mods_clear_worker(self):
        # Chained tasks replace the worker before this handler runs; only the
        # worker that still owns the slot may clean up.
        sender = self.sender()
        if sender is not None and getattr(self, "_mods_worker", None) is not sender:
            # A chained task already took over; retire the previous worker.
            sender.deleteLater()
            return
        self.mods_cancel_btn.setEnabled(False)
        if getattr(self, "_mods_worker", None):
            self._mods_worker.deleteLater()
            self._mods_worker = None

    def _mods_on_progress(self, received, total):
        if total > 0:
            self.mods_progress.setMaximum(100)
            self.mods_progress.setValue(min(100, int(received * 100 / total)))
            return
        # Unknown size: show a moving bar based on megabytes received.
        mb = received / 1048576.0
        self.mods_progress.setMaximum(0 if mb < 1 else 100)
        self.mods_progress.setValue(int(min(mb, 100.0)))

    def _mods_on_downloaded(self, temp_path):
        if getattr(self, "_mods_cancel_requested", False):
            self._mods_remove_temp(temp_path)
            return
        mode = getattr(self, "_mods_mode", "mod")
        if mode == "bepinex":
            try:
                self._mods_install_bepinex_archive(temp_path)
            finally:
                self._mods_remove_temp(temp_path)
            return
        mod = getattr(self, "_mods_payload", None) or {}
        name = mod.get("name", "Mod")
        try:
            self._mods_install_downloaded_mod(temp_path, mod)
        except Exception as exc:                                    # noqa: BLE001
            if mode == "direct":
                self._mods_fail(f"直链 Mod 安装失败：{exc}")
                self._mods_remove_temp(temp_path)
                return
            self._mods_download_errors.append(f"{name}（{exc}）")
        finally:
            self._mods_remove_temp(temp_path)
        self._mods_refresh_installed()
        if mode == "direct":
            self._mods_refresh_loader()
            return
        self._mods_download_next()

    def _mods_on_download_failed(self, message):
        """Report a download error and continue a queued online install."""
        mode = getattr(self, "_mods_mode", "mod")
        if getattr(self, "_mods_cancel_requested", False):
            self._mods_download_queue = []
            self._mods_fail("所选 Mod 安装已取消")
            return
        if mode != "mod":
            self._mods_fail(message)
            return
        payload = getattr(self, "_mods_payload", None) or {}
        name = str(payload.get("name") or "未命名")
        self._mods_download_errors.append(f"{name}（下载失败：{message}）")
        self._mods_download_next()

    def _mods_remove_temp(self, path):
        try:
            if path and os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass

    def _mods_install_downloaded_mod(self, temp_path, mod):
        plugins = self._mods_plugins_dir()
        os.makedirs(plugins, exist_ok=True)
        download_url = str(mod.get("download") or "")
        suffix = os.path.splitext(urlparse(download_url).path.lower())[1]
        name = mod.get("name", "Mod")
        if suffix == ".dll":
            base_name = os.path.splitext(str(name))[0] if str(name).lower().endswith(".dll") else name
            target = _safe_join(plugins, f"{self._mods_sanitize(base_name)}.dll")
            if target is None:
                raise RuntimeError("插件名不合法")
            shutil.copy2(temp_path, target)
            installed = [os.path.basename(target)]
        else:
            installed = self._extract_mod_archive(temp_path, self._mods_root())
        self._mods_ok(f"已安装：{', '.join(installed)}")

    def _mods_sanitize(self, name):
        keep = [c for c in str(name) if c not in '\\/:*?"<>|']
        cleaned = "".join(keep).strip().strip(".")
        return cleaned or "mod"

    # ---------------- extraction ----------------
    def _extract_mod_archive(self, archive, game_root):
        """Install a mod archive into the game folder; return top-level names added.

        A full BepInEx package (members under BepInEx/) is unpacked into the game
        root so that patchers, config and plugins all land in the right place.
        Everything else is mapped into the plugins folder.
        """
        if not zipfile.is_zipfile(archive):
            raise RuntimeError("不是有效的 zip 包（7z/rar 请先自行解压）")
        plugins_dir = os.path.join(game_root, "BepInEx", "plugins")
        with zipfile.ZipFile(archive) as archive_file:
            names = archive_file.namelist()
            if _is_bepinex_package(names):
                count = self._extract_all(archive_file, game_root, names)
                if not count:
                    raise RuntimeError("包内没有可写入的文件")
                return _plugin_names_in_archive(names) or ["BepInEx"]
            plans = _plan_entry_map(names)
            if not plans:
                raise RuntimeError(
                    "包内没有找到可安装的插件布局（需要 .dll 或 plugins 目录）")
            targets = []
            for member, relative in plans.items():
                target = _safe_join(plugins_dir, relative)
                if target is None:
                    raise RuntimeError("压缩包包含越界路径，已中止")
                targets.append((member, target, relative))
            added = []
            for member, target, relative in targets:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive_file.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                top = relative.split("/")[0]
                if top not in added:
                    added.append(top)
        return added

    def _extract_all(self, archive_file, root_dir, names):
        """Extract every listed member into root_dir; return written count."""
        targets = []
        for member in names:
            if member.endswith("/") or "__MACOSX/" in member:
                continue
            target = _safe_join(root_dir, member)
            if target is None:
                raise RuntimeError("压缩包包含越界路径，已中止")
            targets.append((member, target))
        count = 0
        for member, target in targets:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive_file.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
        return count

    # ---------------- installed list ----------------
    def _mods_refresh_installed(self):
        table = self.mods_installed_table
        table.setRowCount(0)
        plugins = self._mods_plugins_dir()
        if not plugins:
            self.mods_installed_summary.setText("尚未选择游戏目录")
            self._mods_empty_row(table, "未选择游戏目录")
            return
        rows = _scan_plugin_entries(plugins)
        disabled_dir = os.path.join(plugins, "disabled")
        rows += [(name, kind, False, path)
                 for name, kind, _enabled, path in _scan_plugin_entries(disabled_dir)]
        if not rows:
            self.mods_installed_summary.setText("已安装 0 项")
            self._mods_empty_row(table, "尚未安装任何 Mod")
            return
        enabled_count = sum(1 for _name, _kind, enabled, _path in rows if enabled)
        disabled_count = len(rows) - enabled_count
        self.mods_installed_summary.setText(
            f"共 {len(rows)} 项 · 已启用 {enabled_count} · 已禁用 {disabled_count}")
        table.setRowCount(len(rows))
        for index, (name, kind, enabled, path) in enumerate(rows):
            values = [name, kind, "已启用" if enabled else "已禁用",
                      _human_size(_entry_size(path)), path]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 0:
                    item.setData(Qt.UserRole, path)
                    item.setData(Qt.UserRole + 1, enabled)
                item.setToolTip(text)
                table.setItem(index, column, item)

    def _mods_empty_row(self, table, text):
        table.setRowCount(1)
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        table.setItem(0, 0, item)
        table.setSpan(0, 0, 1, table.columnCount())

    def _mods_selected_installed(self):
        rows = []
        seen = set()
        for index in self.mods_installed_table.selectionModel().selectedRows():
            row = index.row()
            if row in seen:
                continue
            seen.add(row)
            item = self.mods_installed_table.item(row, 0)
            path = item.data(Qt.UserRole) if item else None
            if not path:
                continue
            enabled = bool(item.data(Qt.UserRole + 1))
            rows.append((item.text(), path, enabled))
        return rows

    def _mods_toggle_selected(self, enable):
        rows = self._mods_selected_installed()
        if not rows:
            QMessageBox.information(self, "未选择 Mod", "请先选择要操作的 Mod。")
            return
        plugins = self._mods_plugins_dir()
        if not plugins:
            QMessageBox.information(self, "未选择游戏目录", "请先选择游戏安装目录。")
            return
        if not os.path.isdir(plugins):
            QMessageBox.information(self, "插件目录不存在", "请先安装 Mod 再操作。")
            return
        disabled_dir = os.path.join(plugins, "disabled")
        os.makedirs(disabled_dir, exist_ok=True)
        moved, skipped = [], []
        for name, path, enabled in rows:
            if enabled == enable:
                skipped.append(name)
                continue
            target_dir = plugins if enable else disabled_dir
            target = os.path.join(target_dir, os.path.basename(path))
            if os.path.exists(target):
                skipped.append(f"{name}（目标已存在）")
                continue
            try:
                shutil.move(path, target)
                moved.append(name)
            except Exception as exc:                                # noqa: BLE001
                skipped.append(f"{name}（{exc}）")
        self._mods_refresh_installed()
        parts = []
        if moved:
            parts.append("已" + ("启用" if enable else "禁用") + "：" + "、".join(moved))
        if skipped:
            parts.append("跳过：" + "、".join(skipped))
        self._mods_ok("；".join(parts) or "没有需要处理的 Mod")

    def _mods_uninstall_selected(self):
        rows = self._mods_selected_installed()
        if not rows:
            QMessageBox.information(self, "未选择 Mod", "请先选择要卸载的 Mod。")
            return
        plugins = self._mods_plugins_dir()
        listing = "\n".join(f"  • {name}  ({path})" for name, path, _ in rows)
        answer = QMessageBox.question(
            self, "确认卸载",
            f"将从插件目录删除以下 {len(rows)} 项，且无法撤销：\n{listing}\n\n确定继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        removed, failed = [], []
        for name, path, _enabled in rows:
            if _safe_join(plugins, os.path.relpath(path, plugins)) != os.path.abspath(path):
                failed.append(f"{name}（路径不在插件目录内，已拒绝）")
                continue
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                removed.append(name)
            except Exception as exc:                                # noqa: BLE001
                failed.append(f"{name}（{exc}）")
        self._mods_refresh_installed()
        self._mods_refresh_loader()
        parts = []
        if removed:
            parts.append("已卸载：" + "、".join(removed))
        if failed:
            parts.append("失败：" + "、".join(failed))
        self._mods_ok("；".join(parts))

    # ---------------- online manifest ----------------
    def _mods_pick_manifest(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Mod 清单文件", "",
            "JSON 清单 (*.json);;所有文件 (*.*)")
        if not path:
            return
        with QSignalBlocker(self.mods_manifest_edit):
            self.mods_manifest_edit.setText(path)
        self._mods_save_manifest_url()
        self._mods_refresh_online()

    def _mods_refresh_online(self):
        source = self.mods_manifest_edit.text().strip()
        self._mods_save_manifest_url()
        if self._mods_is_busy():
            QMessageBox.information(self, "任务进行中", "已有任务正在运行，请稍候。")
            return
        self._mods_cancel_requested = False
        if not source:
            self.mods_online_table.setRowCount(0)
            self._mods_online_rows = []
            self._mods_fail("还没有填写 Mod 清单地址，可选择本地 json 或填写在线清单 URL。")
            return
        if source.lower().startswith(("http://", "https://")):
            self.mods_status.setText("正在获取在线清单…")
            worker = _CallWorker(lambda: _http_json(source), parent=self)
        else:
            if not os.path.isfile(source):
                self._mods_fail(f"清单文件不存在：{source}")
                return
            worker = _CallWorker(
                lambda: json.loads(io.open(source, "r", encoding="utf-8").read()), parent=self)
        self._mods_worker = worker
        self._mods_mode = "manifest"
        self.mods_progress.setMaximum(0)
        worker.finished_ok.connect(self._mods_on_manifest)
        worker.failed.connect(self._mods_fail)
        worker.finished.connect(self._mods_clear_worker)
        worker.start()

    def _mods_on_manifest(self, data):
        mods = (data or {}).get("mods") or []
        self._mods_online_rows = [m for m in mods if isinstance(m, dict)]
        plugins_dir = self._mods_plugins_dir()
        installed_rows = _scan_plugin_entries(plugins_dir)
        installed_rows += _scan_plugin_entries(os.path.join(plugins_dir, "disabled"))
        installed_names = [n.lower() for n, _k, _e, _p in installed_rows]
        table = self.mods_online_table
        table.setRowCount(len(self._mods_online_rows))
        for index, mod in enumerate(self._mods_online_rows):
            name = str(mod.get("name") or mod.get("id") or "未命名")
            version = str(mod.get("version") or "-")
            author = str(mod.get("author") or "-")
            desc = str(mod.get("description") or "")
            key = str(mod.get("id") or name).lower()
            installed = any(key in n or n.startswith(key) for n in installed_names)
            values = [name, version, author, desc, "已安装" if installed else "可安装"]
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                table.setItem(index, column, item)
        if not self._mods_online_rows:
            self._mods_ok("清单已加载，但没有列出任何 Mod")
        else:
            self._mods_ok(f"清单已加载：共 {len(self._mods_online_rows)} 个 Mod")

    def _mods_open_selected_homepage(self):
        rows = self._mods_selected_online()
        if not rows:
            QMessageBox.information(self, "未选择 Mod", "请先在清单中选择一个 Mod。")
            return
        url = str(rows[0].get("homepage") or rows[0].get("download") or "").strip()
        if not url:
            self._mods_fail("该 Mod 没有提供主页地址。")
            return
        QDesktopServices.openUrl(QUrl(url))

    # ---------------- misc ----------------
    def _mods_game_running(self):
        try:
            pid, _exe = find_game_process()
        except Exception:                                           # noqa: BLE001
            return False
        return pid is not None

    def _mods_ok(self, text):
        self.mods_progress.setMaximum(100)
        self.mods_progress.setValue(100)
        self.mods_status.setText(text)
        try:
            self.set_status(f"✅ {text}")
        except Exception:                                           # noqa: BLE001
            pass

    def _mods_fail(self, text):
        self.mods_progress.setMaximum(100)
        self.mods_progress.setValue(0)
        self.mods_status.setText(text)
        try:
            self.set_status(f"⚠️ {text}")
        except Exception:                                           # noqa: BLE001
            pass
