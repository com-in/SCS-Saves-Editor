"""Offline regressions for source-derived save semantics and Qt interactions."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication, QMessageBox, QTableWidget, QTableWidgetItem
from main import ES3Editor
from _save_support import number, integer_list, atomic_write, validate_changes


def fixture():
    npc = {'npcName': 'Airport person', 'npcRoleId': 3, 'money': 12.75,
           'abilities': [{'abilityName': 'Strength', 'value': 3.5}],
           'unknownMetadata': {'preserve': True}}
    values = dict(Currency=100.25, Level=1, Exp=0, Day=2, Electricity=50,
        ShopName='测试', CallData=-1, Difficulty=0, Workers=[
            {'id': 'first', 'npcDataRole': {'npcName': 'Alice', 'npcRoleId': 0, 'money': 10}},
            {'id': 'second', 'npcDataRole': {'npcName': 'Bob', 'npcRoleId': 3, 'money': 20}}],
        CryptoData=[{'cryptoName': 'TestCoin', 'currentPrice': 10.75, 'coinAmount': 1.25,
                     'avgBuyPrice': 4.125, 'priceHistory': [9.0, 10.75], 'extra': True}],
        Items=[{'itemId': 1, 'quantity': 2, 'position': {'x': 0, 'y': 0.5, 'z': 0}}],
        PlaceItems=[], Upgrade=[], Progress=[], EasterEgg=[], Mayor=[],
        NpcRoleFound=[0, 3, 999], Interior=[], Dirt=[], Tutorial=[True, False],
        TutorialSaveData=[], MissionProgress=[], Debt=[], GameStats=[],
        ScheduleCall=[2, 3], AirportNpc=[[npc]],
        BodyGuard={'guards': [{'slotIndex': 1, 'healthNormalized': 0.5, 'extra': 42}]},
        NpcPurchase={'npcCountPerPurchase': 2, 'timeInterval': 30.5, 'autoPurchaseEnabled': False},
        Cat={'adoptedCatIndex': -1, 'catIndices': [0, 1], 'feedStreaks': [2, 3]},
        DeliveryLocation=1)
    return {k: {'__type': 'preserved-test-type', 'value': v} for k, v in values.items()}


class SaveSupportTests(unittest.TestCase):
    def test_numeric_input_rejects_lossy_or_nonfinite_values(self):
        for value in ('NaN', 'inf', '-inf', 'abc', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                number(value)
        with self.assertRaises(ValueError):
            number('1.5', integer=True)
        self.assertEqual(number('2e3', integer=True), 2000)
        self.assertEqual(integer_list('1，2,3'), [1, 2, 3])
        with self.assertRaises(ValueError):
            integer_list('1,bad,3')

    def test_atomic_backup_and_failed_replace_preserve_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'save.es3'
            path.write_text('{"original":true}', encoding='utf-8')
            previous = path.read_bytes()
            with patch('_save_support.os.replace', side_effect=OSError('locked')):
                with self.assertRaises(OSError):
                    atomic_write(path, fixture())
            self.assertEqual(path.read_bytes(), previous)
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])
            backup = atomic_write(path, fixture())
            self.assertEqual(backup.read_bytes(), previous)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), fixture())

    def test_game_specific_validation(self):
        original = fixture()
        for key, value in [('AirportNpc', [[3]]), ('Difficulty', 4),
                           ('Cat', {'catIndices': [0, 1], 'feedStreaks': [1]}),
                           ('BodyGuard', {'guards': [{'slotIndex': 0, 'healthNormalized': 2}]}),
                           ('NpcPurchase', {'npcCountPerPurchase': 1, 'timeInterval': 0})]:
            candidate = copy.deepcopy(original)
            candidate[key]['value'] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_changes(candidate, original)


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings_dir = tempfile.TemporaryDirectory()
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, cls.settings_dir.name)
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setOrganizationName('SCS-RegressionTests')
        cls.app.setApplicationName('EditorTests')
        cls.window = ES3Editor()
        cls.window._state_timer.stop()

    @classmethod
    def tearDownClass(cls):
        cls.window.deleteLater()
        cls.settings_dir.cleanup()

    def load(self, data):
        w = self.window
        w._loading = True
        w.data = copy.deepcopy(data)
        w.file_path = None
        w.search_entry.clear()
        w.parse_data_to_ui()
        w._loading = False
        w._remember_saved()
        return w

    def setUp(self):
        critical_guard = patch.object(QMessageBox, 'critical', side_effect=lambda *args: (_ for _ in ()).throw(AssertionError(str(args[1:]))))
        critical_guard.start()
        self.addCleanup(critical_guard.stop)
        self.dialog_guard = patch.object(QMessageBox, 'warning', side_effect=AssertionError('Unexpected warning'))
        self.dialog_guard.start()
        self.addCleanup(self.dialog_guard.stop)
        self.w = self.load(fixture())

    def test_fixture_roundtrip_preserves_every_field(self):
        self.assertEqual(self.w.collect_document(), fixture())
        self.assertFalse(self.w.isWindowModified())

    def test_actual_save_roundtrips(self):
        for name in ('666.es3', 'awapro.es3'):
            path = Path(__file__).resolve().parents[1] / name
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            with self.subTest(save=name):
                self.load(data)
                self.assertEqual(self.w.collect_document(), data)

    def test_crypto_decimals_and_price_history(self):
        self.w.crypto_table.item(0, 1).setText('18.125')
        self.w.crypto_table.item(0, 2).setText('2.875')
        self.w.crypto_table.item(0, 3).setText('5.0625')
        result = self.w.collect_document()['CryptoData']['value'][0]
        self.assertEqual(result['priceHistory'], [9.0, 18.125])
        self.assertEqual(result['coinAmount'], 2.875)
        self.assertEqual(result['avgBuyPrice'], 5.0625)
        self.assertTrue(result['extra'])

    def test_airport_retains_full_npc_objects(self):
        npc = fixture()['AirportNpc']['value'][0][0]
        result = self.w._airport_save()
        self.assertEqual(result, [[npc]])
        self.w.airport_table.item(0, 1).setText('[3]')
        with self.assertRaisesRegex(ValueError, '机场队列'):
            self.w.collect_document()

    def test_difficulty_easy_and_sandbox(self):
        self.assertEqual(self.w.difficulty_combo.currentData(), 0)
        self.w.difficulty_combo.setCurrentIndex(3)
        self.assertEqual(self.w.collect_document()['Difficulty']['value'], 3)

    def test_filtered_worker_edits_correct_person(self):
        self.w.search_entry.setText('Bob')
        self.w.worker_list.setCurrentRow(0)
        self.assertEqual(self.w.current_worker, 1)
        before = copy.deepcopy(self.w.workers[0])
        self.w.worker_entries['money'].setText('123.75')
        self.w.on_worker_field_changed('money')
        self.assertEqual(self.w.workers[0], before)
        self.assertEqual(self.w.workers[1]['npcDataRole']['money'], 123.75)

    def test_worker_selection_does_not_mutate_data(self):
        before = copy.deepcopy(self.w.data)
        self.w.worker_list.setCurrentRow(0)
        self.w.worker_list.setCurrentRow(1)
        self.assertEqual(self.w.data, before)

    def test_validation_failure_does_not_mutate_live_document(self):
        before = copy.deepcopy(self.w.data)
        self.w.entry_basic['currency'].setText('500')
        self.w.cat_feed_input.setText('1')
        with self.assertRaisesRegex(ValueError, '一一对应'):
            self.w.collect_document()
        self.assertEqual(self.w.data, before)

    def test_generic_tables_preserve_sparse_null_and_empty_objects(self):
        rows = [{'id': 1, 'nullable': None, 'empty': {}, 'p': {'x': 0}},
                {'id': 2, 'p': {'x': 0.25}, 'flag': True}]
        table = QTableWidget()
        self.w._list_load(table, rows)
        self.assertEqual(self.w._list_save(table), rows)
        column = next(i for i,spec in enumerate(table._list_meta['cols']) if spec['name']=='p.x')
        table.item(1, column).setText('0.375')
        result = self.w._list_save(table)
        self.assertEqual(result[0], rows[0])
        self.assertEqual(result[1]['p']['x'], 0.375)
        table.removeRow(0)
        self.assertEqual(self.w._list_save(table), [result[1]])
        table.deleteLater()

    def test_invalid_table_value_is_not_silently_zeroed(self):
        table = self.w.items_table
        column = next(i for i,spec in enumerate(table._list_meta['cols']) if spec['name']=='quantity')
        table.item(0, column).setText('bad')
        with self.assertRaisesRegex(ValueError, 'Items'):
            self.w.collect_document()

    def test_unknown_keys_do_not_shadow_dedicated_editors(self):
        data = fixture()
        data['CustomA'] = {'__type': 'int', 'value': 10}
        data['CustomB'] = {'__type': 'int', 'value': 20}
        self.load(data)
        self.assertEqual(self.w.other_key_box.count(), 2)
        self.w._other_scalar_entry.setText('12')
        self.w.other_key_box.setCurrentIndex(1)
        self.w._other_scalar_entry.setText('24')
        self.w.entry_basic['currency'].setText('888.25')
        result = self.w.collect_document()
        self.assertEqual(result['CustomA']['value'], 12)
        self.assertEqual(result['CustomB']['value'], 24)
        self.assertEqual(result['Currency']['value'], 888.25)

    def test_save_and_export_include_table_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'export.json'
            table = self.w.items_table
            column = next(i for i,spec in enumerate(table._list_meta['cols']) if spec['name']=='quantity')
            table.item(0, column).setText('15')
            with patch('_document.QFileDialog.getSaveFileName', return_value=(str(destination), '')):
                self.assertTrue(self.w.export_json())
            self.assertEqual(json.loads(destination.read_text(encoding='utf-8'))['Items']['value'][0]['quantity'], 15)
            self.assertIsNone(self.w.file_path)

    def test_bodyguard_add_fills_gap_and_preserves_extensions(self):
        self.w._bodyguard_add()
        guards = self.w.collect_document()['BodyGuard']['value']['guards']
        self.assertEqual([guard['slotIndex'] for guard in guards], [1, 0])
        self.assertEqual(guards[0]['extra'], 42)

    def test_missing_keys_stay_missing_after_switch(self):
        data = {'Currency': {'__type': 'float', 'value': 23.5}}
        self.load(data)
        self.assertEqual(self.w.collect_document(), data)
        self.assertFalse(self.w.cat_adopted.isEnabled())
        self.assertEqual(self.w.cat_indices_input.text(), '')

    def test_navigation_and_dirty_state(self):
        self.w.nav_search.setText('AirportNpc')
        visible = [leaf.data(0, Qt.UserRole) for leaf in self.w._nav_leaves if not leaf.isHidden()]
        self.assertEqual(visible, [self.w._key_to_row['airport']])
        self.w._go_to_page('items')
        self.assertEqual(self.w.stack.currentIndex(), self.w._key_to_row['items'])
        self.w.entry_basic['currency'].setText('123')
        self.w._refresh_document_state()
        self.assertTrue(self.w.isWindowModified())
        self.w.entry_basic['currency'].setText('100.25')
        self.w._refresh_document_state()
        self.assertFalse(self.w.isWindowModified())


if __name__ == '__main__':
    unittest.main()
