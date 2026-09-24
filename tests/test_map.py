"""Map projection and placement contracts independent of game assets."""
import os
import math
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent

from main import Map3DWidget
from unity_scene_loader import _rotate
from _map_items import box_corners, heading, quaternion, rotate_world_y, yaw_rotation
from _unity_item_profiles import transform_corners
from _unity_item_profiles import _read_item_refs, _read_mayor_refs


class SceneCatalogTests(unittest.TestCase):
    def test_mayor_rewards_skip_variable_role_lists(self):
        import struct
        raw = (struct.pack('<i', 2) + struct.pack('<iqiii', 3, 101, 2, 0, 1)
               + struct.pack('<iq', 3, 999) + struct.pack('<iqiii', 3, 102, 4, 0, 0))
        self.assertEqual(_read_mayor_refs(raw, 0, 3, {101: 38, 102: 55}), [38, 55])
        for malformed, lookup in ((raw[:-1], {101: 38, 102: 55}), (raw, {101: 38}),
                                  (struct.pack('<i', -1), {})):
            with self.subTest(raw=malformed), self.assertRaises(ValueError):
                _read_mayor_refs(malformed, 0, 3, lookup)

    def test_item_reference_list_rejects_truncated_and_unknown_entries(self):
        import struct
        raw = struct.pack('<iiqiq', 2, 3, 101, 3, 102)
        self.assertEqual(_read_item_refs(raw, 0, 3, {101: 11, 102: 98}), [11, 98])
        for malformed, lookup in ((raw[:-1], {101: 11, 102: 98}),
                                  (raw, {101: 11}),
                                  (struct.pack('<i', -1), {}),
                                  (struct.pack('<iiq', 1, 4, 101), {101: 11})):
            with self.subTest(raw=malformed), self.assertRaises(ValueError):
                _read_item_refs(malformed, 0, 3, lookup)


def floor(y):
    corners = [(-5.0, y, -5.0), (5.0, y, -5.0),
               (5.0, y, 5.0), (-5.0, y, 5.0)]
    return {"name": "Floor", "kind": "floor", "quad": corners,
            "base_y": y, "triangles": [(corners[0], corners[1], corners[2]),
                                      (corners[0], corners[2], corners[3])]}


def wall(base, top=5.0):
    corners = [(-2.0, top, -0.2), (2.0, top, -0.2),
               (2.0, top, 0.2), (-2.0, top, 0.2)]
    return {"name": "Wall", "kind": "wall", "quad": corners,
            "base_y": base, "triangles": [(corners[0], corners[1], corners[2]),
                                            (corners[0], corners[2], corners[3])]}


class MapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_parent_rotation_preserves_scene_coordinates(self):
        vector = _rotate((0.0, 2**-0.5, 0.0, 2**-0.5), (1.0, 0.0, 0.0))
        self.assertAlmostEqual(vector[0], 0.0, places=5)
        self.assertAlmostEqual(vector[2], -1.0, places=5)

    def test_prefab_size_offset_rotation_and_preview_share_geometry(self):
        widget = Map3DWidget()
        widget.resize(900,650)
        widget.set_camera_preset("top")
        box = box_corners((1,0.5,0),(4,1,0.8))
        profile = {'boxes': [box], 'bounds': [(-1,3),(0,1),(-0.4,0.4)]}
        widget.set_scene({'objects': [floor(0)], 'floor_levels': [0], 'item_profiles': {2:profile}})
        point = (0,0,0,"放置物品","放置物品 #1")
        for yaw in (0,90,180,270):
            widget.set_points([point],{point[3:]: {'item_id':2,'rotation':yaw_rotation(yaw)}})
            base,top = widget._marker_prisms(point)[0]
            for local,world in zip(box,base+top):
                expected = _rotate(yaw_rotation(yaw),local)
                for a,b in zip(world,expected):
                    self.assertAlmostEqual(a,b)
            widget.set_preview_item(2)
            preview = (*point[:3],"放置物品","预览")
            self.assertEqual(widget._marker_prisms(preview,yaw=yaw),widget._marker_prisms(point))
            warm = widget.grab().toImage()
            widget._item_render_cache_key = None
            widget._item_geometry_cache.clear()
            self.assertEqual(warm,widget.grab().toImage())
            *_,mx,mz,scale,cx,cy=widget._scene_bounds()
            end = _rotate(yaw_rotation(yaw),(2.6,1,0))
            sx,sy,_=widget._project(end[0]-mx,end[1],end[2]-mz,scale,cx,cy)
            self.assertEqual(widget._pick_placed_marker(sx,sy),0)

    def test_quaternion_sign_scale_and_tilt_are_preserved(self):
        q=quaternion((0.2,0.3,-0.1,0.9))
        self.assertAlmostEqual(heading(q),heading(tuple(-2*v for v in q)))
        rotated=rotate_world_y(q,35)
        for axis in ((1,0,0),(0,1,0),(0,0,1)):
            expected=_rotate(yaw_rotation(35),_rotate(q,axis))
            for a,b in zip(_rotate(rotated,axis),expected):
                self.assertAlmostEqual(a,b)
        widget=Map3DWidget()
        point=(0,0,0,"放置物品","放置物品 #1")
        widget.set_points([point],{point[3:]: {'rotation':q}})
        center,front=widget._marker_direction(point)
        for a,b in zip(((front[i]-center[i])/0.45 for i in range(3)),_rotate(q,(0,0,1))):
            self.assertAlmostEqual(a,b)

    def test_child_collider_trs_preserves_nonuniform_scale_and_offset(self):
        chain=[((0,0,0),(0,0,0,1),(2,1,3)),
               ((1,2,3),yaw_rotation(90),(1,2,1))]
        # Child (1,1,1) -> scaled (1,2,1), rotated (1,2,-1),
        # translated (2,4,2), then root scale -> (4,4,6).
        actual=transform_corners([(1,1,1)],chain)[0]
        for a,b in zip(actual,(4,4,6)):
            self.assertAlmostEqual(a,b)

    def test_top_view_is_not_mirrored(self):
        widget = Map3DWidget()
        widget.set_camera_preset("top")
        y = widget._floor_reference()
        origin = widget._project(0, y, 0, 20, 200, 200)
        right = widget._project(1, y, 0, 20, 200, 200)
        forward = widget._project(0, y, 1, 20, 200, 200)
        self.assertAlmostEqual(right[0]-origin[0], 20)
        self.assertAlmostEqual(right[1]-origin[1], 0)
        self.assertAlmostEqual(forward[0]-origin[0], 0)
        self.assertAlmostEqual(forward[1]-origin[1], -20)
        self.assertGreater(widget._project(0,y+1,0,20,200,200)[2], origin[2])

    def test_projection_matches_unity_camera_basis(self):
        widget = Map3DWidget()
        for yaw in (-130, 0, 35, 180):
            for pitch in (25, 55, 90):
                with self.subTest(yaw=yaw, pitch=pitch):
                    widget.yaw, widget.pitch = yaw, pitch
                    ya, pi = math.radians(yaw)/2, math.radians(pitch)/2
                    qy = (0, math.sin(ya), 0, math.cos(ya))
                    qx = (math.sin(pi), 0, 0, math.cos(pi))
                    axes = [_rotate(qy, _rotate(qx, v)) for v in ((1,0,0),(0,1,0),(0,0,1))]
                    v = (2.0, 0.7, -3.0)
                    camera = [sum(a*b for a,b in zip(v, axis)) for axis in axes]
                    actual = widget._project(v[0], v[1]+widget._floor_reference(), v[2], 10, 100, 100)
                    for a,b in zip(actual, (100+10*camera[0], 100-10*camera[1], -camera[2])):
                        self.assertAlmostEqual(a,b,places=6)

    def test_item_forward_and_clockwise_rotation_match_unity(self):
        widget = Map3DWidget()
        widget.set_camera_preset("top")
        point = (0,0,0,"放置物品","放置物品 #1")
        for yaw in (0,15,90,180,270,-45):
            with self.subTest(yaw=yaw):
                _,top = widget._marker_geometry(point,yaw=yaw)
                center = tuple(sum(v[i] for v in top)/4 for i in range(3))
                front = tuple((top[2][i]+top[3][i])/2 for i in range(3))
                direction = tuple((front[i]-center[i])/0.3 for i in range(3))
                half = math.radians(yaw)/2
                expected = _rotate((0,math.sin(half),0,math.cos(half)), (0,0,1))
                for a,b in zip(direction,expected):
                    self.assertAlmostEqual(a,b,places=6)
        # E / right (+90 degrees) must turn screen-up towards screen-right.
        self.assertGreater(widget._project(1,0,0,20,200,200)[0],200)

    def test_screen_world_roundtrip_in_all_camera_quadrants(self):
        widget = Map3DWidget()
        widget.resize(900,650)
        for scene in (None, {"objects": [floor(-1.5)], "floor_levels": [-1.5]}):
            widget.set_points([(0,-1.5,0,"放置物品","放置物品 #1")])
            if scene: widget.set_scene(scene)
            for yaw in (-120,0,35,170):
                for pitch in (25,55,90):
                    widget.yaw,widget.pitch = yaw,pitch
                    *_, mx,mz,scale,cx,cy = widget._scene_bounds()
                    for x,z in ((-2,1),(1,-3),(2,2)):
                        expected = (x,-1.5 if scene else 0,z)
                        sx,sy,_ = widget._project(x-mx,expected[1],z-mz,scale,cx,cy)
                        actual = widget.screen_to_ground(sx,sy)
                        self.assertIsNotNone(actual)
                        for a,b in zip(actual,expected):
                            self.assertAlmostEqual(a,b,places=6)

    def test_top_view_picks_nearest_floor_in_all_mode(self):
        widget = Map3DWidget()
        widget.set_scene({"objects": [floor(-1.5),floor(2.0)], "floor_levels": [-1.5,2.0]})
        widget.set_floor_mode("all")
        widget.set_camera_preset("top")
        *_,mx,mz,scale,cx,cy = widget._scene_bounds()
        sx,sy,_ = widget._project(-mx,2,-mz,scale,cx,cy)
        self.assertAlmostEqual(widget.screen_to_ground(sx,sy)[1],2)

    def test_click_hits_selected_floor_and_rejects_empty_space(self):
        widget = Map3DWidget()
        widget.resize(600, 500)
        widget.set_points([(0.0, -1.5, 0.0, "放置物品", "放置物品 #1")])
        widget.set_scene({"objects": [floor(-1.5), floor(2.0)]})
        widget.set_camera_preset("top")
        bounds = widget._scene_bounds()
        _, _, _, _, _, midx, midz, scale, cx, cy = bounds
        point = widget._project(-midx, -1.5, -midz, scale, cx, cy)
        self.assertAlmostEqual(widget.screen_to_ground(point[0], point[1])[1], -1.5)
        self.assertIsNone(widget.screen_to_ground(0, 0))
        widget.set_floor_mode("upper")
        upper = widget._project(-midx, 2.0, -midz, scale, cx, cy)
        self.assertAlmostEqual(widget.screen_to_ground(upper[0], upper[1])[1], 2.0)

    def test_points_are_visible_only_on_active_floor(self):
        widget = Map3DWidget()
        widget.floor_levels = [-1.5, 2.0]
        widget.set_points([
            (1.0, -1.5, 1.0, "放置物品", "放置物品 #1"),
            (2.0, 2.0, 2.0, "物品", "物品 #2"),
        ])
        widget.set_floor_index(0)
        self.assertEqual([point[1] for point in widget._visible_points()], [-1.5])
        widget.set_floor_index(1)
        self.assertEqual([point[1] for point in widget._visible_points()], [2.0])
        widget.set_floor_mode("all")
        self.assertEqual(len(widget._visible_points()), 2)

    def test_wall_mounted_item_uses_wall_base_floor(self):
        widget = Map3DWidget()
        widget.floor_levels = [0.0, 2.0, 5.0]
        point = (0.0, 4.7, 0.0, "物品", "物品 #1")
        widget.set_scene({"objects": [floor(0.0), floor(2.0), floor(5.0), wall(2.0)],
                          "floor_levels": [0.0, 2.0, 5.0]})
        widget.set_points([point], {point[3:]: {"is_wall": True}})
        widget.set_floor_index(1)
        self.assertEqual(widget._visible_points(), [point])
        widget.set_floor_index(2)
        self.assertEqual(widget._visible_points(), [])

    def test_non_wall_item_keeps_position_floor_semantics(self):
        widget = Map3DWidget()
        point = (0.0, 4.7, 0.0, "物品", "物品 #1")
        widget.set_scene({"objects": [floor(0.0), floor(2.0), floor(5.0), wall(2.0)],
                          "floor_levels": [0.0, 2.0, 5.0]})
        widget.set_points([point], {point[3:]: {"is_wall": False}})
        widget.set_floor_index(2)
        self.assertEqual(widget._visible_points(), [point])

    def test_high_sign_stays_on_second_floor_without_wall_colliders(self):
        widget = Map3DWidget()
        levels = [-4.6170687675, -1.7475000001, 2.1148311496]
        point = (-2.39295578, 1.2375623, -0.8861097, "放置物品", "放置物品 #3")
        widget.set_points([point], {point[3:]: {"item_id": 82}})
        widget.set_scene({"objects": [floor(level) for level in levels],
                          "floor_levels": levels,
                          "item_definitions": {82: {"is_wall": True}}})
        # Loading definitions after save points must also choose the right initial floor.
        self.assertEqual(widget.floor_index, 1)
        self.assertEqual(widget._visible_points(), [point])
        for mode in ("current", "upper", "all"):
            widget.set_floor_mode(mode)
            self.assertEqual(widget._visible_points(), [] if mode == "upper" else [point])
        widget.set_floor_index(2)
        self.assertEqual(widget._visible_points(), [])
        self.assertEqual(widget.points, [point])  # Classification never changes saved height.

    def test_wall_item_missing_geometry_uses_lower_storey_interval(self):
        widget = Map3DWidget()
        widget.set_scene({"objects": [], "floor_levels": [0, 3, 6]})
        for height, expected in ((2.8,0), (5.8,3), (6.2,6)):
            point = (0,height,0,"放置物品","放置物品 #1")
            widget.set_points([point], {point[3:]: {"is_wall": True}})
            self.assertEqual(widget._point_floor_height(point), expected)

    def test_multistorey_wall_does_not_assign_upper_sign_to_its_base(self):
        widget = Map3DWidget()
        widget.set_scene({"objects": [wall(0,9)], "floor_levels": [0,3,6]})
        point = (0,5.7,0,"放置物品","放置物品 #1")
        widget.set_points([point], {point[3:]: {"is_wall": True}})
        self.assertEqual(widget._point_floor_height(point), 3)

    def test_vertical_wall_footprint_has_finite_length(self):
        quad = [(-2,0,0),(2,0,0),(2,3,0),(-2,3,0)]
        self.assertTrue(Map3DWidget._point_in_xz_quad(0,.1,quad,.2))
        self.assertFalse(Map3DWidget._point_in_xz_quad(100,0,quad,.2))
        self.assertFalse(Map3DWidget._point_in_xz_quad(0,1,quad,.2))
        self.assertFalse(Map3DWidget._point_in_xz_quad(20,20,[(0,0,0)]*4,.2))

    def test_floor_assignment_cache_refreshes_on_point_and_scene_changes(self):
        widget = Map3DWidget()
        scene = {"objects": [floor(0),floor(3),floor(6)], "floor_levels": [0,3,6]}
        widget.set_scene(scene)
        point = (0,5.8,0,"放置物品","放置物品 #1")
        details = {point[3:]: {"is_wall": True}}
        widget.set_points([point], details)
        self.assertEqual(widget._point_floor_height(point), 3)
        with patch.object(widget, "_wall_floor_height", side_effect=AssertionError("must use cached assignment")):
            self.assertEqual(widget._point_floor_height(point), 3)
        widget.set_points([point], {point[3:]: {"is_wall": False}})
        self.assertEqual(widget._point_floor_height(point), 5.8)
        widget.set_points([point], details)
        widget.set_scene({"objects": [floor(0)], "floor_levels": [0]})
        self.assertEqual(widget._point_floor_height(point), 0)

    def test_visual_top_is_clickable_and_rotation_changes_footprint(self):
        widget = Map3DWidget()
        widget.resize(900, 650)
        point = (0.0, -1.5, 0.0, "放置物品", "放置物品 #1")
        widget.set_points([point])
        widget.set_scene({"objects": [floor(-1.5)], "floor_levels": [-1.5]})
        widget.set_camera_preset("angle")
        base, top = widget._marker_geometry(point)
        *_, midx, midz, scale, cx, cy = widget._scene_bounds()
        center = tuple(sum(v[i] for v in top)/4 for i in range(3))
        sx, sy, _ = widget._project(center[0]-midx, center[1], center[2]-midz, scale, cx, cy)
        self.assertEqual(widget._pick_placed_marker(sx, sy), 0)
        rotated, _ = widget._marker_geometry(point, yaw=90)
        width = lambda corners: max(v[0] for v in corners)-min(v[0] for v in corners)
        length = lambda corners: max(v[2] for v in corners)-min(v[2] for v in corners)
        self.assertAlmostEqual(width(base), length(rotated))
        self.assertAlmostEqual(length(base), width(rotated))
        widget.zoom = 4.0
        widget.set_view_mode("all")
        self.assertEqual(widget._marker_geometry(point), (base, top))

    def test_floor_switch_keeps_framing_and_cancels_hidden_edit(self):
        widget = Map3DWidget()
        widget.set_points([(0, -1.5, 0, "放置物品", "放置物品 #1"),
                           (10, 2, 5, "放置物品", "放置物品 #2")])
        widget.set_scene({"objects": [floor(-1.5), floor(2)], "floor_levels": [-1.5, 2]})
        widget.set_floor_index(0)
        lower_bounds = widget._scene_bounds()
        widget.selected_marker = widget._drag_marker = 0
        widget.preview_point = (1, -1.5, 1)
        widget.set_floor_index(1)
        self.assertEqual(widget._scene_bounds(), lower_bounds)
        self.assertIsNone(widget.preview_point)
        self.assertIsNone(widget.selected_marker)
        self.assertIsNone(widget._drag_marker)
        # Rendering also exercises the painter paths; the old tests never painted.
        self.assertFalse(widget.grab().isNull())

    def test_cached_render_matches_cold_render_after_view_changes(self):
        widget = Map3DWidget()
        widget.resize(800, 600)
        widget.set_points([(0, -1.5, 0, "放置物品", "放置物品 #1")])
        widget.set_scene({"objects": [floor(-1.5), floor(2)], "floor_levels": [-1.5, 2]})
        for change in (lambda: None, lambda: widget.set_camera_preset("top"),
                       lambda: setattr(widget, "yaw", 45), lambda: setattr(widget, "zoom", 2),
                       lambda: setattr(widget, "pan_x", 80), lambda: setattr(widget, "pan_y", -35),
                       lambda: widget.set_floor_index(1), lambda: widget.resize(700, 500)):
            change()
            warm = widget.grab().toImage()
            widget._scene_render_cache = widget._scene_geometry_cache = None
            widget._item_render_cache_key = None
            self.assertEqual(warm, widget.grab().toImage())

    def test_hover_cache_follows_moved_items_and_floor(self):
        widget = Map3DWidget()
        widget.resize(900, 650)
        widget.set_view_mode("all")
        widget.set_camera_preset("top")
        point = (0, -1.5, 0, "放置物品", "放置物品 #1")
        widget.set_points([point])
        widget.set_scene({"objects": [floor(-1.5), floor(2)], "floor_levels": [-1.5, 2]})
        *_, mx, mz, scale, cx, cy = widget._scene_bounds()
        x,y,_ = widget._project(-mx,-1.5,-mz,scale,cx,cy)
        self.assertEqual(widget._pick_placed_marker(x,y),0)
        widget.set_points([(3,-1.5,0,*point[3:]),(-3,-1.5,0,"物品","物品 #2")])
        self.assertIsNone(widget._pick_placed_marker(x,y))
        widget.set_floor_index(1)
        self.assertIsNone(widget._pick_placed_marker(x,y))

    def test_drag_preserves_grab_offset_and_click_does_not_move(self):
        widget = Map3DWidget()
        widget.resize(900, 650)
        widget.set_camera_preset("angle")
        widget.set_points([(0,-1.5,0,"放置物品","放置物品 #1")])
        widget.set_scene({"objects": [floor(-1.5)], "floor_levels": [-1.5]})
        moves = []
        widget.move_callback = lambda *args: moves.append(args)
        *_, mx,mz,scale,cx,cy = widget._scene_bounds()
        x,y,_ = widget._project(0.2-mx,-0.95,-mz,scale,cx,cy)
        start = QPointF(x,y)

        def mouse(event_type, pos, button, buttons):
            QApplication.sendEvent(widget, QMouseEvent(event_type,pos,pos,button,buttons,Qt.NoModifier))

        mouse(QEvent.MouseButtonPress,start,Qt.LeftButton,Qt.LeftButton)
        mouse(QEvent.MouseButtonRelease,start,Qt.LeftButton,Qt.NoButton)
        self.assertEqual(moves, [])
        mouse(QEvent.MouseButtonPress,start,Qt.LeftButton,Qt.LeftButton)
        initial = widget.screen_to_ground(x,y)
        end = start+QPointF(25,10)
        final = widget.screen_to_ground(end.x(),end.y())
        mouse(QEvent.MouseMove,end,Qt.NoButton,Qt.LeftButton)
        # Only releasing commits the edit to the document.
        self.assertEqual(moves, [])
        mouse(QEvent.MouseButtonRelease,end,Qt.LeftButton,Qt.NoButton)
        self.assertEqual(len(moves),1)
        self.assertAlmostEqual(moves[0][1][0],final[0]-initial[0])
        self.assertAlmostEqual(moves[0][1][2],final[2]-initial[2])

    def test_middle_drag_pans_and_updates_ground_and_object_picking(self):
        for preset in ("top", "angle"):
            with self.subTest(preset=preset):
                widget = Map3DWidget()
                widget.resize(900,650)
                widget.set_points([(0,-1.5,0,"放置物品","放置物品 #1")])
                widget.set_scene({"objects": [floor(-1.5)], "floor_levels": [-1.5]})
                widget.set_camera_preset(preset)
                *_, mx,mz,scale,cx,cy = widget._scene_bounds()
                x,y,_ = widget._project(-mx,-0.95,-mz,scale,cx,cy)
                start = QPointF(x,y)
                end = start+QPointF(85,-45)
                world_before = widget.screen_to_ground(x,y)
                self.assertEqual(widget._pick_placed_marker(x,y),0)
                widget.grab()  # Warm all camera-dependent caches before panning.
                bounds_cache = widget._bounds_cache
                camera = (widget.yaw,widget.pitch,widget.zoom)
                moves = []
                widget.move_callback = lambda *args: moves.append(args)
                for event_type,pos,button,buttons in (
                    (QEvent.MouseButtonPress,start,Qt.MiddleButton,Qt.MiddleButton),
                    (QEvent.MouseMove,end,Qt.NoButton,Qt.MiddleButton),
                    (QEvent.MouseButtonRelease,end,Qt.MiddleButton,Qt.NoButton)):
                    QApplication.sendEvent(widget,QMouseEvent(event_type,pos,pos,button,buttons,Qt.NoModifier))
                self.assertEqual((widget.pan_x,widget.pan_y),(85,-45))
                self.assertEqual((widget.yaw,widget.pitch,widget.zoom),camera)
                self.assertEqual(moves,[])
                self.assertEqual(widget._pick_placed_marker(end.x(),end.y()),0)
                self.assertIsNone(widget._pick_placed_marker(x,y))
                world_after = widget.screen_to_ground(end.x(),end.y())
                for a,b in zip(world_before,world_after):
                    self.assertAlmostEqual(a,b)
                self.assertIs(widget._bounds_cache,bounds_cache)
                warm = widget.grab().toImage()
                widget._scene_render_cache = None
                self.assertEqual(warm,widget.grab().toImage())

    def test_middle_drag_in_placement_mode_does_not_place(self):
        widget = Map3DWidget()
        widget.resize(900,650)
        widget.set_scene({"objects": [floor(-1.5)], "floor_levels": [-1.5]})
        widget.set_camera_preset("top")
        placements = []
        widget.set_placement_mode(True,lambda *args: placements.append(args))
        start,end = QPointF(450,325),QPointF(490,345)
        for event_type,pos,button,buttons in (
            (QEvent.MouseButtonPress,start,Qt.MiddleButton,Qt.MiddleButton),
            (QEvent.MouseButtonPress,start,Qt.LeftButton,Qt.LeftButton|Qt.MiddleButton),
            (QEvent.MouseMove,end,Qt.NoButton,Qt.MiddleButton),
            (QEvent.MouseButtonRelease,end,Qt.MiddleButton,Qt.NoButton)):
            QApplication.sendEvent(widget,QMouseEvent(event_type,pos,pos,button,buttons,Qt.NoModifier))
        self.assertEqual(placements,[])
        self.assertEqual(widget.cursor().shape(),Qt.CrossCursor)
        self.assertIsNotNone(widget.preview_point)
        QApplication.sendEvent(widget,QMouseEvent(QEvent.MouseButtonPress,end,end,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
        self.assertEqual(len(placements),1)
        for actual,expected in zip(placements[0][0],(0,-1.5,0)):
            self.assertAlmostEqual(actual,expected)

    def test_zoom_refreshes_placement_preview_before_click(self):
        widget=Map3DWidget()
        widget.resize(900,650)
        widget.set_scene({'objects':[floor(-1.5)],'floor_levels':[-1.5]})
        widget.set_camera_preset('angle')
        placements=[]
        widget.set_placement_mode(True,lambda *args:placements.append(args))
        cursor=QPointF(500,320)
        widget.preview_point=widget.screen_to_ground(cursor.x(),cursor.y())
        before=widget.preview_point
        event=QWheelEvent(cursor,cursor,QPoint(0,0),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
        QApplication.sendEvent(widget,event)
        self.assertNotEqual(widget.preview_point,before)
        preview=widget.preview_point
        QApplication.sendEvent(widget,QMouseEvent(QEvent.MouseButtonPress,cursor,cursor,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
        self.assertEqual(placements[0][0],preview)


if __name__ == "__main__":
    unittest.main()
