"""Document lifecycle shared by save, save-as and JSON export."""
import copy
import hashlib
import json
import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox
from _save_support import atomic_write, validate_changes, validate_document, prepare_es3_document


class DocumentMixin:
    def _ui_state(self):
        """Capture editable values only; selection, filters and layout are not edits."""
        tables = set(self._table_keys.values()) | {self.crypto_table, self.upgrade_table,
            self.interior_table, self.dirt_table, self.bodyguard_table, self.airport_table}
        state = {}
        for table in tables:
            state[id(table)] = [
                [(cell.text(), cell.checkState().value) if cell else None
                 for cell in (table.item(r, c) for c in range(table.columnCount()))]
                for r in range(table.rowCount())]
        state['basic'] = [e.text() for e in self.entry_basic.values()]
        state['purchase'] = [self.npcp_entries['count'].text(),
            self.npcp_entries['interval'].text(), self.npcp_entries['auto'].isChecked()]
        state['cat'] = [self.cat_adopted.text(), self.cat_indices_input.text(), self.cat_feed_input.text()]
        state['delivery'] = self.delivery_combo.currentIndex()
        state['roles'] = [self.rolefound_table.item(r, 0).data(Qt.UserRole)
            for r in range(self.rolefound_table.rowCount()) if self.rolefound_table.item(r, 0)]
        for key, cfg in [('tutorial', self._h_tutorial), ('schedule', self._h_schedule)]:
            state[key] = [w.isChecked() if cfg['is_bool'] else w.text() for w in cfg['widgets']]
        return state

    def _remember_saved(self):
        self._disk_snapshot = copy.deepcopy(self.data)
        self._saved_ui = self._ui_state()
        self._disk_hash = self._file_hash(self.file_path)
        self._dirt_modified = False
        self._refresh_document_state()

    @staticmethod
    def _file_hash(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest() if path and Path(path).is_file() else None

    def _refresh_document_state(self):
        if getattr(self, '_loading', False):
            return
        loaded = self.data is not None
        dirty = loaded and (self.data != getattr(self, '_disk_snapshot', None)
                            or self._ui_state() != getattr(self, '_saved_ui', None)
                            or self._other_has_edits())
        self.setWindowModified(bool(dirty))
        base = os.path.basename(self.file_path) if self.file_path else '未打开存档'
        self.setWindowTitle(f'{base}[*] — SCS 存档修改器')
        self.file_label.setText(base)
        self.file_label.setToolTip(self.file_path or '打开 .es3 存档以开始编辑')
        self.document_badge.setText('未保存' if dirty else '已保存' if loaded else '等待打开')
        self.document_badge.setProperty('dirty', bool(dirty))
        self.document_badge.style().unpolish(self.document_badge)
        self.document_badge.style().polish(self.document_badge)
        self.save_button.setEnabled(loaded)
        self.save_as_button.setEnabled(loaded)
        self.check_button.setEnabled(loaded)
        for row, page in enumerate(self.nav_items):
            if page[2] not in ('home', 'memory', 'map3d'):
                self.stack.widget(row).setEnabled(loaded)
        for key, label in self.overview_values.items():
            value = self.es3_get(key)
            if isinstance(value, list):
                text = str(len(value))
            elif value is None:
                text = '—'
            elif key == 'Currency':
                text = f'{value:,.2f}' if isinstance(value, (int, float)) else str(value)
            else:
                text = str(value)
            label.setText(text)

    def _confirm_discard(self):
        self._refresh_document_state()
        if not self.isWindowModified():
            return True
        result = QMessageBox.question(self, '尚未保存', '当前存档有未保存的修改，是否先保存？',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if result == QMessageBox.Save:
            return self.save_file()
        return result == QMessageBox.Discard

    def collect_document(self):
        """Build a candidate; validation failure never mutates the live document."""
        original, workers = self.data, self.workers
        self.data = copy.deepcopy(original)
        self.workers = copy.deepcopy(workers)
        try:
            self.save_ui_to_data()
            self.merge_json_tabs()
            validate_changes(self.data, getattr(self, '_disk_snapshot', original))
            return prepare_es3_document(self.data)
        finally:
            self.data, self.workers = original, workers

    def check_document(self):
        try:
            candidate = self.collect_document()
            baseline = getattr(self, '_disk_snapshot', self.data)
            changes = [k for k, value in candidate.items() if value != baseline.get(k)]
            detail = '、'.join(changes) if changes else '没有数据变化'
            QMessageBox.information(self, '存档检查通过',
                f'结构与修改字段校验通过。共 {len(candidate)} 个存档键。\n待保存：{detail}')
        except (ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, '请修正输入', str(exc))

    def _load_file(self, path):
        try:
            candidate = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            validate_document(candidate)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, '打开失败', str(exc))
            return False
        if not self._confirm_discard():
            return False
        previous, previous_path = self.data, self.file_path
        try:
            self._loading = True
            self.data, self.file_path = candidate, str(Path(path).resolve())
            self.parse_data_to_ui()
        except Exception as exc:
            self.data, self.file_path = previous, previous_path
            if previous is not None:
                self.parse_data_to_ui()
            QMessageBox.critical(self, '存档结构不兼容', str(exc))
            return False
        finally:
            self._loading = False
        self._remember_saved()
        self._record_recent_file(self.file_path)
        self._mem_sync_save_label()
        self.log('已打开存档。保存时自动备份；Ctrl+S 保存，Ctrl+Shift+S 另存为。')
        self.set_status(f'已加载 {len(candidate)} 个存档键')
        return True

    def _write_document(self, path, *, switch=True):
        try:
            candidate = self.collect_document()
            same = self.file_path and os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(self.file_path))
            if same and self._file_hash(path) != getattr(self, '_disk_hash', None):
                raise ValueError('磁盘上的存档已被其他程序修改，请先另存为保留本次修改，再重新打开原档。')
            backup = atomic_write(path, candidate)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.critical(self, '未能保存', str(exc))
            return False
        if switch or same:
            self._loading = True
            try:
                self.data, self.file_path = candidate, str(Path(path).resolve())
                self.parse_data_to_ui()
            finally:
                self._loading = False
            self._remember_saved()
            self._record_recent_file(self.file_path)
        self.log(f'已保存：{path}' + (f'；备份：{backup}' if backup else ''))
        self.set_status('保存完成 · 已自动备份' if backup else '保存完成')
        return True

    def save_file(self):
        if self.data is None:
            return False
        return self._write_document(self.file_path) if self.file_path else self.save_file_as()

    def save_file_as(self):
        if self.data is None:
            return False
        path, _ = QFileDialog.getSaveFileName(self, '另存为存档', self.file_path or 'save.es3',
            'ES3 存档 (*.es3);;JSON 文件 (*.json)')
        return self._write_document(path) if path else False

    def export_json(self):
        if self.data is None:
            return False
        start = str(Path(self.file_path).with_name('save_export.json')) if self.file_path else 'save_export.json'
        path, _ = QFileDialog.getSaveFileName(self, '导出当前修改', start, 'JSON 文件 (*.json)')
        return self._write_document(path, switch=False) if path else False

    def closeEvent(self, event):
        worker = getattr(self, '_mem_worker', None)
        if worker is not None and worker.isRunning():
            self.set_status('请等待当前内存扫描结束后退出')
            event.ignore()
        elif self._confirm_discard():
            from PySide6.QtCore import QSettings
            QSettings().setValue('ui/geometry', self.saveGeometry())
            event.accept()
        else:
            event.ignore()
