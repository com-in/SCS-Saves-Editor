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
from _save_support import number, integer_list, atomic_write, validate_changes, prepare_es3_document


def property_orders(value, path=()):
    """Capture every object order without conflating JSON numeric formatting."""
    result = {}
    if isinstance(value, dict):
        result[path] = tuple(value)
        for key, child in value.items():
            result.update(property_orders(child, path + (key,)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(property_orders(child, path + (index,)))
    return result


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
    def test_sequential_unity_components_and_unknown_fields(self):
        orders = ('xy', 'xyz', 'xyzw', 'rgba', ('x', 'y', 'width', 'height'))
        for order in orders:
            expected = dict(zip(order, range(1, len(order) + 1)))
            broken = dict(reversed(list(expected.items())))
            fixed = prepare_es3_document({'nested': [broken]})['nested'][0]
            self.assertEqual(list(fixed), list(order))
            self.assertEqual(tuple(fixed.values()), tuple(expected.values()))
            self.assertEqual(fixed, broken)
        for unknown in ({'z': 1, 'y': 2, 'x': 3, 'extra': 4},
                        {'y': 'north', 'x': 'east'}, {'y': False, 'x': True},
                        {'beta': 1, 'alpha': 2}):
            self.assertEqual(property_orders(prepare_es3_document(unknown)), property_orders(unknown))

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

    def test_atomic_write_repairs_quaternion_order_without_mutating_input(self):
        data = {'PlaceItems': {'value': [{'rotation': {'w': 0.8, 'x': 0, 'y': 0.6, 'z': 0},
                 'unknown': {'z': 2, 'a': 1}}]}}
        before = json.dumps(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rotation.es3'
            atomic_write(path, data)
            saved = json.loads(path.read_text(encoding='utf-8'))
            item = saved['PlaceItems']['value'][0]
            self.assertEqual(list(item['rotation']), list('xyzw'))
            self.assertEqual(list(item['unknown']), ['z', 'a'])
            self.assertEqual(saved, data)
        self.assertEqual(json.dumps(data), before)


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

    def test_table_roundtrip_preserves_nested_property_order(self):
        # QVariantMap sorts dict keys, while ES3's Unity type readers consume
        # values sequentially. Dict equality alone cannot detect this loss.
        item = {'id': 'order-test', 'rotation': {'x': 0, 'y': 0, 'z': 0, 'w': 1},
                'nested': {'z_last': 1, 'a_first': 2},
                'color': {'r': 0.1, 'g': 0.2, 'b': 0.3, 'a': 1}}
        self.w._list_load(self.w.placed_table, [item])
        result = self.w._list_save(self.w.placed_table)
        self.assertEqual(json.dumps(result), json.dumps([item]))

    def test_special_pages_preserve_extension_order_after_edits(self):
        data = fixture()
        extension = {'z_custom': {'second': 2, 'first': 1},
                     'color': {'r': 0.1, 'g': 0.2, 'b': 0.3, 'a': 1},
                     'rect': {'x': 1, 'y': 2, 'width': 3, 'height': 4}}
        data['Interior']['value'] = [{'upgradeName': 'CustomInterior', 'unlocked': False,
            'selected': False, 'extension': copy.deepcopy(extension)}]
        data['BodyGuard']['value']['guards'][0]['extension'] = copy.deepcopy(extension)
        w = self.load(data)
        w.interior_table.item(0, 1).setCheckState(Qt.Checked)
        w.bodyguard_table.item(0, 1).setText('0.75')
        result = w.collect_document()
        self.assertTrue(result['Interior']['value'][0]['unlocked'])
        self.assertEqual(result['BodyGuard']['value']['guards'][0]['healthNormalized'], 0.75)
        for record in (result['Interior']['value'][0], result['BodyGuard']['value']['guards'][0]):
            self.assertEqual(record['extension'], extension)
            self.assertEqual(property_orders(record['extension']), property_orders(extension))

    def test_json_export_repairs_reordered_unity_components(self):
        data = fixture()
        data['CustomGeometry'] = {'value': {'position': {'x': 1, 'y': 2, 'z': 3}}}
        w = self.load(data)
        w.other_key_box.setCurrentIndex(w.other_key_box.findText('CustomGeometry'))
        w.other_json.setPlainText('{"position":{"z":3,"y":2,"x":1},"color":{"a":1,"b":0.3,"g":0.2,"r":0.1}}')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'export.json'
            with patch('_document.QFileDialog.getSaveFileName', return_value=(str(path), '')):
                self.assertTrue(w.export_json())
            result = json.loads(path.read_text(encoding='utf-8'))['CustomGeometry']['value']
            self.assertEqual(tuple(result['position'].values()), (1, 2, 3))
            self.assertEqual(tuple(result['color'].values()), (0.1, 0.2, 0.3, 1))
        self.assertIsNone(w.file_path)

    def test_saved_rotations_match_sequential_game_reader(self):
        data = fixture()
        expected = {'x': 0.0, 'y': 0.6, 'z': 0.0, 'w': 0.8}
        # Reproduce files already written with alphabetically sorted keys.
        broken = {axis: expected[axis] for axis in 'wxyz'}
        for key in ('PlaceItems', 'Items', 'Workers'):
            data[key]['value'] = [{'id': key, 'itemDataId': 42, 'itemId': 42,
                'position': {'x': 1.0, 'y': 2.0, 'z': 3.0},
                'rotation': copy.deepcopy(broken)}]
        w = self.load(data)
        before = copy.deepcopy(w.data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixed.es3'
            self.assertTrue(w._write_document(str(path)))
            saved = json.loads(path.read_text(encoding='utf-8'))
            for key in ('PlaceItems', 'Items', 'Workers'):
                rotation = saved[key]['value'][0]['rotation']
                self.assertEqual(list(rotation), list('xyzw'))
                self.assertEqual(tuple(rotation.values()), tuple(expected.values()))
            self.assertEqual(saved, before)  # Only property order is repaired.
            self.assertEqual(json.dumps(w.collect_document()), json.dumps(saved))

    def test_map_move_and_rotation_refresh_preview_and_save_together(self):
        data = fixture()
        data['PlaceItems']['value'] = [{
            'id': 'placed-test', 'itemDataId': 42,
            'position': {'x': 0.0, 'y': -1.5, 'z': 0.0},
            'rotation': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
            'unknownMetadata': 'preserve',
        }]
        self.load(data)
        self.w._move_placed_item(0, (2.0, -1.5, 4.0))
        self.w._rotate_placed_item(0, 90)
        point = next(p for p in self.w.map3d_view.points if p[3] == '放置物品')
        self.assertEqual(point[:3], (2.0, -1.5, 4.0))
        detail = self.w.map3d_view.point_details[point[3:]]
        self.assertAlmostEqual(detail['yaw'], 90, places=4)
        self.assertNotEqual(detail['name'], '放置物品')
        saved = self.w.collect_document()['PlaceItems']['value'][0]
        self.assertEqual(saved['position'], {'x': 2.0, 'y': -1.5, 'z': 4.0})
        self.assertAlmostEqual(saved['rotation']['y'], 2**-0.5, places=6)
        self.assertEqual(saved['unknownMetadata'], 'preserve')
        self.assertTrue(self.w.isWindowModified())

    def test_wall_sign_classification_does_not_modify_save(self):
        from tests.test_map import floor
        data = fixture()
        data['PlaceItems']['value'] = [{'id':'wall-sign','itemDataId':82,
            'position':{'x':-2.39295578,'y':1.2375623,'z':-0.8861097},
            'rotation':{'x':0,'y':0,'z':0,'w':1}}]
        w = self.load(data)
        levels = [-4.6170687675,-1.7475000001,2.1148311496]
        w._on_scene_loaded({'objects':[floor(y) for y in levels],
            'floor_levels':levels,'item_definitions':{82:{'is_wall':True}}})
        before = copy.deepcopy(w.collect_document())
        w.map3d_view.set_floor_index(1)
        visible = [p for p in w.map3d_view._visible_points() if p[3]=='放置物品']
        self.assertEqual(len(visible),1)
        self.assertEqual(visible[0][1],1.2375623)
        self.assertTrue(w.map3d_view.point_details[visible[0][3:]]['is_wall'])
        w.map3d_view.set_floor_index(2)
        self.assertFalse([p for p in w.map3d_view._visible_points() if p[3]=='放置物品'])
        self.assertEqual(w.collect_document(),before)

    def test_map_floor_controls_follow_arrow_navigation(self):
        from tests.test_map import floor
        w = self.w
        w._on_scene_loaded({"objects": [floor(-1.5),floor(2)], "floor_levels": [-1.5,2]})
        w.map3d_view.set_floor_index(0)
        self.assertEqual(w.map_floor_box.currentData(),0)
        self.assertFalse(w.map_floor_prev.isEnabled())
        w.map_floor_next.click()
        self.assertEqual(w.map_floor_box.currentData(),1)
        self.assertFalse(w.map_floor_next.isEnabled())
        w.map_floor_box.setCurrentIndex(w.map_floor_box.findData("all"))
        self.assertEqual(w.map3d_view.floor_mode,"all")
        w.map_floor_prev.click()
        self.assertEqual(w.map3d_view.floor_mode,"level")
        self.assertEqual(w.map_floor_box.currentData(),0)

    def test_map_rotation_preserves_pitch_roll_and_refreshes_full_quaternion(self):
        from _map_items import quaternion, rotate_world_y
        original = quaternion((0.2,0.3,-0.1,0.9))
        data = fixture()
        data['PlaceItems']['value'] = [{'id':'tilted','itemDataId':2,
            'position':{'x':0,'y':0,'z':0}, 'rotation':dict(zip('xyzw',original))}]
        self.load(data)
        self.w._rotate_placed_item(0,35)
        saved = self.w.collect_document()['PlaceItems']['value'][0]['rotation']
        expected = rotate_world_y(original,35)
        for axis,value in zip('xyzw',expected):
            self.assertAlmostEqual(saved[axis],value,places=6)
        details=self.w.map3d_view.point_details[("放置物品","放置物品 #1")]
        self.assertEqual(details['item_id'],2)
        for actual,value in zip(details['rotation'],expected):
            self.assertAlmostEqual(actual,value,places=6)

    def test_actual_save_roundtrips(self):
        for name in ('666.es3', 'awapro.es3'):
            path = Path(__file__).resolve().parents[1] / name
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            with self.subTest(save=name):
                self.load(data)
                self.assertEqual(self.w.collect_document(), data)
                saved = self.w.collect_document()
                self.assertEqual(property_orders(saved), property_orders(data))
                for key in ('PlaceItems', 'Items', 'Workers'):
                    for item in saved.get(key, {}).get('value', []):
                        if isinstance(item, dict) and isinstance(item.get('rotation'), dict):
                            self.assertEqual(list(item['rotation']), list('xyzw'))

    def _placement_scene(self):
        from tests.test_map import floor
        definitions = {
            0: dict(is_placable=True,has_placable_component=True,is_wall=False,is_shelf=False,shelf_type=0),
            50: dict(is_placable=True,has_placable_component=True,is_wall=False,is_shelf=True,shelf_type=3),
            115: dict(is_placable=True,has_placable_component=True,is_wall=False,is_shelf=False,shelf_type=0),
            2: dict(is_placable=False,has_placable_component=False,is_wall=False,is_shelf=False,shelf_type=0),
            9: dict(is_placable=True,has_placable_component=True,is_wall=True,is_shelf=False,shelf_type=0)}
        return {'objects':[floor(-1.5),floor(2)],'floor_levels':[-1.5,2],'item_definitions':definitions}

    def _deletion_fixture(self):
        data=fixture()
        data['PlaceItems']['value']=[
            {'id':'remove-me','itemDataId':0,'position':{'x':-2,'y':-1.5,'z':0},
             'rotation':{'x':0,'y':0,'z':0,'w':1},'tamingNpcs':[], 'extra':'keep-until-deleted'},
            {'id':'keep-me','itemDataId':50,'position':{'x':2,'y':-1.5,'z':0},
             'rotation':{'x':0,'y':0,'z':0,'w':1},'tamingNpcs':[], 'extra':{'keep':True}}]
        data['Workers']['value'][0].update(assignedBedId='remove-me',assignedWorkplaceId='keep-me')
        data['Workers']['value'][1].update(assignedWorkplaceId='remove-me',assignedBedId=None)
        return data

    def _select_first_map_item(self):
        from PySide6.QtCore import QEvent,QPointF
        from PySide6.QtGui import QMouseEvent
        view=self.w.map3d_view
        view.set_placement_mode(False)
        view.resize(900,650)
        view.set_floor_index(0)
        view.set_camera_preset('top')
        point=view.points[0]
        *_,mx,mz,scale,cx,cy=view._scene_bounds()
        sx,sy,_=view._project(point[0]-mx,point[1],point[2]-mz,scale,cx,cy)
        cursor=QPointF(sx,sy)
        for event_type,buttons in ((QEvent.MouseButtonPress,Qt.LeftButton),(QEvent.MouseButtonRelease,Qt.NoButton)):
            QApplication.sendEvent(view,QMouseEvent(event_type,cursor,cursor,Qt.LeftButton,buttons,Qt.NoModifier))
        self.assertEqual(view.selected_marker,0)
        self.assertTrue(self.w.map_delete_btn.isEnabled())

    def test_map_delete_key_clears_assignments_and_saves_without_deleting_next_item(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        data=self._deletion_fixture()
        w=self.load(data)
        w._on_scene_loaded(self._placement_scene())
        self._select_first_map_item()
        view=w.map3d_view
        bounds=view._scene_bounds()
        QApplication.sendEvent(view,QKeyEvent(QEvent.KeyPress,Qt.Key_Delete,Qt.NoModifier))
        result=w.collect_document()
        self.assertEqual(result['PlaceItems']['value'],data['PlaceItems']['value'][1:])
        self.assertIsNone(result['Workers']['value'][0]['assignedBedId'])
        self.assertIsNone(result['Workers']['value'][1]['assignedWorkplaceId'])
        self.assertEqual(result['Workers']['value'][0]['assignedWorkplaceId'],'keep-me')
        self.assertIsNone(view.selected_marker)
        self.assertFalse(w.map_delete_btn.isEnabled())
        self.assertEqual(view._scene_bounds(),bounds)
        self.assertEqual(len([p for p in view.points if p[3]=='放置物品']),1)
        QApplication.sendEvent(view,QKeyEvent(QEvent.KeyPress,Qt.Key_Delete,Qt.NoModifier))
        self.assertEqual(w.collect_document(),result)
        self.assertTrue(w.isWindowModified())
        for key in data:
            if key not in ('PlaceItems','Workers'):
                self.assertEqual(result[key],data[key])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'deleted.es3'
            self.assertTrue(w._write_document(str(path)))
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')),result)

    def test_map_delete_button_resolves_id_after_table_reorder(self):
        data=self._deletion_fixture()
        w=self.load(data)
        w._on_scene_loaded(self._placement_scene())
        self._select_first_map_item()
        w._list_load(w.placed_table,list(reversed(data['PlaceItems']['value'])))
        w.map_delete_btn.click()
        self.assertEqual([x['id'] for x in w.collect_document()['PlaceItems']['value']],['keep-me'])

    def test_map_delete_protects_occupied_cage_and_hidden_selection(self):
        data=self._deletion_fixture()
        data['PlaceItems']['value'][0]['tamingNpcs']=[{'id':'cage-npc','isTamed':False}]
        w=self.load(data)
        w._on_scene_loaded(self._placement_scene())
        self._select_first_map_item()
        before=w.collect_document()
        w.map_delete_btn.click()
        self.assertEqual(w.collect_document(),before)
        self.assertIn('NPC',w.map3d_info.text())
        w.map3d_view.set_floor_index(1)
        self.assertFalse(w.map_delete_btn.isEnabled())
        self.assertFalse(w.map3d_view.delete_selected_item())
        self.assertEqual(w.collect_document(),before)

    def test_map_click_places_on_active_floor_without_camera_jump_and_roundtrips(self):
        from PySide6.QtCore import QEvent,QPointF
        from PySide6.QtGui import QMouseEvent
        from _map_items import heading
        w = self.w
        w._on_scene_loaded(self._placement_scene())
        view=w.map3d_view
        view.resize(900,650)
        view.set_floor_index(1)
        view.set_camera_preset('angle')
        view.pan_x,view.pan_y,view.zoom=35,-20,1.6
        w.map_item_box.setCurrentIndex(w.map_item_box.findData(50))
        w.map_place_btn.setChecked(True)
        view.preview_yaw=90
        bounds=view._scene_bounds()
        *_,mx,mz,scale,cx,cy=bounds
        target=(1.5,2.0,-1.0)
        sx,sy,_=view._project(target[0]-mx,target[1],target[2]-mz,scale,cx,cy)
        cursor=QPointF(sx,sy)
        for event_type,button,buttons in (
            (QEvent.MouseMove,Qt.NoButton,Qt.NoButton),
            (QEvent.MouseButtonPress,Qt.LeftButton,Qt.LeftButton),
            (QEvent.MouseButtonRelease,Qt.LeftButton,Qt.NoButton)):
            QApplication.sendEvent(view,QMouseEvent(event_type,cursor,cursor,button,buttons,Qt.NoModifier))
        saved=w.collect_document()
        self.assertEqual(len(saved['PlaceItems']['value']),1)
        item=saved['PlaceItems']['value'][0]
        self.assertEqual(item['itemDataId'],50)
        self.assertEqual(item['position'],dict(zip(('x','y','z'),target)))
        self.assertAlmostEqual(heading(item['rotation']),90)
        self.assertTrue(item['isShelf'])
        self.assertEqual(item['shelfType'],3)
        self.assertEqual(item['assignedNpcId'],[])
        self.assertEqual(view._scene_bounds(),bounds)
        self.assertEqual(len([p for p in view._visible_points() if p[3]=='放置物品']),1)
        self.assertTrue(w.isWindowModified())
        # A second placement must use the same view and a different persistent ID.
        w.map_item_box.setCurrentIndex(w.map_item_box.findData(115))
        self.assertTrue(w._place_item_at_map_point((-2,2,1),180))
        items=w.collect_document()['PlaceItems']['value']
        self.assertEqual(items[1]['tamingNpcs'],[])
        self.assertNotEqual(items[0]['id'],items[1]['id'])
        self.assertEqual(view._scene_bounds(),bounds)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'placed.es3'
            self.assertTrue(w._write_document(str(path)))
            self.assertFalse(w.isWindowModified())
            self.load(json.loads(path.read_text(encoding='utf-8')))
            self.assertEqual(w.collect_document()['PlaceItems']['value'],items)

    def test_map_placement_preserves_existing_actual_save_rows(self):
        for name in ('awapro.es3','666.es3'):
            path=Path(__file__).resolve().parents[1]/name
            if not path.exists():
                continue
            with self.subTest(save=name):
                data=json.loads(path.read_text(encoding='utf-8-sig'))
                w=self.load(data)
                w._on_scene_loaded(self._placement_scene())
                w.map_item_box.setCurrentIndex(w.map_item_box.findData(115))
                self.assertTrue(w._place_item_at_map_point((1,2,3),75))
                result=w.collect_document()
                self.assertEqual(result['PlaceItems']['value'][:-1],data['PlaceItems']['value'])
                self.assertEqual(json.dumps(result['PlaceItems']['value'][:-1]),
                                 json.dumps(data['PlaceItems']['value']))
                added=result['PlaceItems']['value'][-1]
                self.assertEqual(added['tamingNpcs'],[])
                self.assertEqual(added['assignedNpcId'],[])
                self.assertEqual(added['position'],{'x':1,'y':2,'z':3})
                for key in data:
                    if key != 'PlaceItems':
                        self.assertEqual(result[key],data[key])

    def test_map_placement_filters_invalid_items_and_rejects_empty_click(self):
        from PySide6.QtCore import QEvent,QPointF
        from PySide6.QtGui import QMouseEvent
        w=self.w
        w._on_scene_loaded(self._placement_scene())
        self.assertEqual({w.map_item_box.itemData(i) for i in range(w.map_item_box.count())},{0,50,115})
        before=w.collect_document()
        w.map_place_btn.setChecked(True)
        cursor=QPointF(-100,-100)
        QApplication.sendEvent(w.map3d_view,QMouseEvent(QEvent.MouseButtonPress,cursor,cursor,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
        self.assertEqual(w.collect_document(),before)
        # Guard the write path too, even if an unsupported ID reaches the selector.
        w.map_item_box.addItem('unsupported',2)
        w.map_item_box.setCurrentIndex(w.map_item_box.findData(2))
        self.assertFalse(w._place_item_at_map_point((0,-1.5,0)))
        self.assertEqual(w.collect_document(),before)

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
