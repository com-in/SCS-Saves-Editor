"""Non-blocking GitHub Release update checks for the desktop application."""
import json
import re
import os
from pathlib import Path
import shutil
import sys
import tempfile

from PySide6.QtCore import QSettings, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from _version import APP_VERSION
from _self_update import validate_download, prepare_update_bat, launch_update_bat

REPOSITORY = "com-in/SCS-Saves-Editor"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value).strip())
    if not match:
        raise ValueError("无法识别版本号：" + str(value))
    return tuple(int(part) for part in match.groups())


def release_update(data, current=APP_VERSION):
    """Return a validated newer stable release, or None."""
    if not isinstance(data, dict):
        raise ValueError("更新服务返回的数据格式不正确")
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    if version_tuple(tag) <= version_tuple(current):
        return None
    prefix = f"https://github.com/{REPOSITORY}/releases/"
    page = str(data.get("html_url") or "")
    if not page.startswith(prefix + "tag/"):
        raise ValueError("更新服务返回的发布页地址不正确")
    asset = next((asset
                     for asset in data.get("assets", [])
                     if isinstance(asset, dict) and asset.get("name") == "SCS.exe"
                     and asset.get("state") == "uploaded"), {})
    download = str(asset.get("browser_download_url") or "")
    if download and not download.startswith(prefix + "download/"):
        raise ValueError("更新服务返回的下载地址不正确")
    return {"tag": tag, "page": page, "download": download,
            "size": int(asset.get("size") or 0), "digest": str(asset.get("digest") or ""),
            "notes": str(data.get("body") or "")[:12000]}


class UpdateMixin:
    def setup_updates(self):
        self._update_reply = None
        self._update_download_reply = None
        self._pending_update = None
        self._update_manager = QNetworkAccessManager(self)
        menu = getattr(self, "_help_menu", None)
        if menu is None:
            menu = self.menuBar().addMenu("帮助(&H)")
            self._help_menu = menu
        version = menu.addAction(f"当前版本：v{APP_VERSION}")
        version.setEnabled(False)
        self._check_update_action = menu.addAction("检查更新…")
        self._check_update_action.triggered.connect(lambda: self.check_updates(manual=True))
        auto = menu.addAction("启动时自动检查更新")
        auto.setCheckable(True)
        auto.setChecked(QSettings().value("updates/automatic", True, type=bool))
        auto.toggled.connect(lambda enabled: QSettings().setValue("updates/automatic", enabled))

    def check_updates(self, *, manual=False):
        if not manual and not QSettings().value("updates/automatic", True, type=bool):
            return
        if self._update_reply is not None or self._update_download_reply is not None:
            return
        request = QNetworkRequest(QUrl(RELEASE_API))
        request.setRawHeader(b"User-Agent", f"SCS-Saves-Editor/{APP_VERSION}".encode("ascii"))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setTransferTimeout(15000)
        self._check_update_action.setEnabled(False)
        self._check_update_action.setText("正在检查更新…")
        reply = self._update_manager.get(request)
        self._update_reply = reply
        reply.finished.connect(lambda: self._update_finished(reply, manual))

    def _update_finished(self, reply, manual):
        self._update_reply = None
        self._check_update_action.setEnabled(True)
        self._check_update_action.setText("检查更新…")
        try:
            if reply.error() != QNetworkReply.NoError:
                raise ValueError(reply.errorString())
            update = release_update(json.loads(bytes(reply.readAll()).decode("utf-8")))
        except Exception as exc:
            if manual:
                QMessageBox.warning(self, "检查更新失败", f"无法获取版本信息，请稍后重试。\n\n{exc}")
            return
        finally:
            reply.deleteLater()
        if update is None:
            if manual:
                QMessageBox.information(self, "检查更新", f"当前已是最新正式版本（v{APP_VERSION}）。")
            return
        box = QMessageBox(self)
        box.setWindowTitle("发现新版本")
        box.setTextFormat(Qt.PlainText)
        box.setText(f"发现新版本 {update['tag']}，当前版本为 v{APP_VERSION}。")
        box.setInformativeText("下载完成后可退出并自动替换、重启程序。" if update["download"] and getattr(sys, "frozen", False)
                               else "下载后退出当前程序，再运行新版本。" if update["download"]
                               else "该版本暂未提供 SCS.exe，可前往发布页查看。")
        if update["notes"]:
            box.setDetailedText(update["notes"])
        accelerated = box.addButton("国内加速下载", QMessageBox.AcceptRole) if update["download"] else None
        original = box.addButton("GitHub 下载", QMessageBox.ActionRole) if update["download"] else None
        page = box.addButton("查看发布页", QMessageBox.ActionRole)
        box.addButton("稍后", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        url = None
        if accelerated is not None and clicked == accelerated:
            url = "https://gh-proxy.org/" + update["download"]
        elif original is not None and clicked == original:
            url = update["download"]
        elif clicked == page:
            url = update["page"]
        if url and clicked != page and getattr(sys, "frozen", False) and sys.platform == "win32":
            self._download_update(url, update)
        elif url and not QDesktopServices.openUrl(QUrl(url)):
            QMessageBox.warning(self, "无法打开浏览器", "请复制地址到浏览器打开：\n" + url)

    def _download_update(self, url, update):
        if self._update_download_reply is not None:
            return
        directory = tempfile.mkdtemp(prefix="scs_update_")
        path = Path(directory) / "SCS.exe"
        try:
            output = path.open("wb")
        except OSError as exc:
            shutil.rmtree(directory)
            QMessageBox.warning(self, "无法下载更新", str(exc))
            return
        dialog = QProgressDialog("正在下载更新…", "取消", 0, 100, self)
        dialog.setWindowTitle("更新程序")
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.show()
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", f"SCS-Saves-Editor/{APP_VERSION}".encode("ascii"))
        request.setTransferTimeout(30000)
        reply = self._update_manager.get(request)
        self._update_download_reply = reply
        self._check_update_action.setEnabled(False)
        state = {"cancelled": False, "error": ""}

        def cancel():
            state["cancelled"] = True
            reply.abort()

        def read():
            try:
                output.write(bytes(reply.readAll()))
                if update["size"] > 0 and output.tell() > update["size"]:
                    raise ValueError("下载内容超过 Release 文件大小。")
            except (OSError, ValueError) as exc:
                state["error"] = str(exc)
                reply.abort()

        def progress(received, total):
            if total > 0:
                dialog.setRange(0, 100)
                dialog.setValue(min(99, int(received * 100 / total)))
            else:
                dialog.setRange(0, 0)
            dialog.setLabelText(f"正在下载更新… {received / 1048576:.1f} MB")

        def finished():
            self._update_download_reply = None
            self._check_update_action.setEnabled(True)
            try:
                if state["cancelled"]:
                    return
                if state["error"]:
                    raise ValueError(state["error"])
                if reply.error() != QNetworkReply.NoError:
                    raise ValueError(reply.errorString())
                read()
                output.close()
                if state["error"]:
                    raise ValueError(state["error"])
                validate_download(path, update["size"], update["digest"])
                dialog.hide()
                answer = QMessageBox.question(
                    self, "更新已就绪",
                    f"{update['tag']} 已下载并校验完成。\n\n"
                    "现在退出并更新？未保存的修改将按正常退出流程询问，旧程序会保留为 .bak 文件。",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer == QMessageBox.Yes:
                    bat, backup = prepare_update_bat(path, sys.executable, os.getpid())
                    self._pending_update = (bat, backup)
                    if self.close():
                        # The detached helper now owns the downloaded files.
                        state["handed_off"] = True
            except Exception as exc:
                QMessageBox.warning(self, "更新失败", f"当前程序未被替换，可重试或使用 GitHub 下载。\n\n{exc}")
            finally:
                self._pending_update = None
                output.close()
                reply.deleteLater()
                dialog.deleteLater()
                if not state.get("handed_off"):
                    shutil.rmtree(directory, ignore_errors=True)

        dialog.canceled.connect(cancel)
        reply.readyRead.connect(read)
        reply.downloadProgress.connect(progress)
        reply.finished.connect(finished)

    def _launch_pending_update(self):
        """Called only after the normal close/save confirmation accepts exit."""
        if self._pending_update:
            worker = getattr(self, "_mods_worker", None)
            if worker is not None and worker.isRunning():
                QMessageBox.warning(self, "无法更新", "请等待 Mod 任务结束后再更新。")
                return False
            try:
                launch_update_bat(self._pending_update[0])
            except OSError as exc:
                QMessageBox.warning(self, "无法启动更新", str(exc))
                return False
        return True
