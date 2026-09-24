"""Draw the collider layout and world-sized save-object proxies using Qt."""
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygon, QPixmap, QPalette
import math
from _map_items import heading


COLORS = {"放置物品": "#3b82f6", "物品": "#f59e0b", "工人": "#10b981", "污垢": "#a855f7"}


def draw_map(view):
    painter = QPainter(view)
    painter.setRenderHint(QPainter.Antialiasing)
    dark = view.palette().color(QPalette.Window).lightness() < 128
    backdrop = QColor("#202737" if dark else "#edf2f6")
    overlay_bg = QColor(39, 46, 63, 240) if dark else QColor(255, 255, 255, 235)
    overlay_text = QColor("#dce5f2" if dark else "#334155")
    painter.fillRect(view.rect(), backdrop)
    bounds = view._scene_bounds()
    if bounds is None:
        painter.setPen(overlay_text)
        painter.drawText(view.rect(), Qt.AlignCenter, "游戏地图尚未加载\n\n打开存档后，在“地图设置”中载入游戏场景")
        painter.end()
        return
    bx0, bx1, bz0, bz1, span, midx, midz, scale, cx, cy = bounds
    reference = view._floor_reference()
    ya, pi = math.radians(view.yaw), math.radians(view.pitch)
    ca, sa, cp, sp = math.cos(ya), math.sin(ya), math.cos(pi), math.sin(pi)

    def project(v):
        x, y, z = v[0]-midx, v[1]-reference, v[2]-midz
        xx, zz = x*ca-z*sa, x*sa+z*ca
        return cx+xx*scale, cy-(y*cp+zz*sp)*scale, y*sp-zz*cp
    polygon = lambda points: QPolygon([QPoint(round(p[0]), round(p[1])) for p in points])
    surfaces, overlays = [], []
    viewport_width, viewport_height = view.width(), view.height()

    def face(vertices, color, outline, width=0.7):
        points = [project(v) for v in vertices]
        add_face(points, color, outline, width)

    def add_face(points, color, outline, width):
        # Reject off-screen geometry before constructing Qt polygons.
        if (max(p[0] for p in points) < -2 or min(p[0] for p in points) > viewport_width+2
                or max(p[1] for p in points) < -2 or min(p[1] for p in points) > viewport_height+2):
            return
        surfaces.append((sum(p[2] for p in points)/len(points), polygon(points), color, outline, width))

    def prism(base, top, color, outline=None, width=0.7):
        # Draw the side facing the camera; back faces must not paint over the top.
        bottom_points, top_points = [project(v) for v in base], [project(v) for v in top]
        for i in range(4):
            j = (i+1) % 4
            points = [bottom_points[i], bottom_points[j], top_points[j], top_points[i]]
            area = sum(points[k][0]*points[(k+1)%4][1] - points[(k+1)%4][0]*points[k][1] for k in range(4))
            if area < 0:
                add_face(points, color.darker(130 if i % 2 else 115), outline or color.darker(145), width)
        for points in (top_points, list(reversed(bottom_points))):
            area = sum(points[k][0]*points[(k+1)%4][1] - points[(k+1)%4][0]*points[k][1] for k in range(4))
            if area < 0:
                add_face(points, color, outline or color.darker(135), width)

    # Precompute world geometry once per floor. A bounding sphere conservatively
    # culls off-screen rooms before any per-face projection during camera drags.
    geometry_key = (id(view.scene), view.floor_mode, view.floor_index, reference)
    geometry = view._scene_geometry_cache
    if geometry is None or geometry[0] != geometry_key:
        floors, walls = [], []

        def sphere(vertices):
            lower = [min(v[i] for v in vertices) for i in range(3)]
            upper = [max(v[i] for v in vertices) for i in range(3)]
            center = tuple((a+b)/2 for a,b in zip(lower, upper))
            radius = math.sqrt(sum((b-a)**2 for a,b in zip(lower, upper)))/2
            return center, radius

        for obj in view._visible_scene_objects("floor"):
            color = QColor("#dce2de" if "office" in obj.get("name", "").lower() else "#d3dce0")
            floors.append((sphere(obj["quad"]), obj["quad"], color, color.darker(105)))
        for obj in view._visible_scene_objects("wall"):
            quad = obj["quad"]
            wall_reference = obj["base_y"] if view.floor_mode == "all" else reference
            bottom = max(obj["base_y"], wall_reference)
            top_y = min(max(v[1] for v in quad), bottom+0.65)
            if top_y <= bottom:
                continue
            base = [(v[0], bottom, v[2]) for v in quad]
            top = [(v[0], top_y, v[2]) for v in quad]
            walls.append((sphere(base+top), base, top))
        geometry = (geometry_key, floors, walls)
        view._scene_geometry_cache = geometry

    def visible(ball):
        center, radius = ball
        x, y, _ = project(center)
        radius = radius*scale+2
        return -radius <= x <= viewport_width+radius and -radius <= y <= viewport_height+radius

    # Cache static projections while keeping walls sortable with moving items.
    scene_key = (id(view.scene), bounds, view.yaw, view.pitch, reference,
                 view.floor_mode, view.floor_index, view.devicePixelRatioF(), dark)
    cached = view._scene_render_cache
    if cached is None or cached[0] != scene_key:
        for ball, quad, color, outline in geometry[1]:
            if visible(ball):
                face(quad, color, outline, 0.5)
        dpr = view.devicePixelRatioF()
        background = QPixmap(round(view.width()*dpr), round(view.height()*dpr))
        background.setDevicePixelRatio(dpr)
        background.fill(backdrop)
        floor_painter = QPainter(background)
        floor_painter.setRenderHint(QPainter.Antialiasing)
        # Room-sized floor quads must be drawn before furniture.
        for _, poly, color, outline, width in sorted(surfaces, key=lambda item: item[0]):
            floor_painter.setBrush(color)
            floor_painter.setPen(QPen(outline, width))
            floor_painter.drawPolygon(poly)
        floor_painter.end()
        surfaces.clear()
        wall_color = QColor("#899ba8")
        for ball, base, top in geometry[2]:
            if visible(ball):
                prism(base, top, wall_color)
        cached = (scene_key, background, tuple(surfaces))
        view._scene_render_cache = cached
    painter.drawPixmap(0, 0, cached[1])
    surfaces = list(cached[2])

    if not view.scene:
        painter.setPen(QPen(QColor("#d5dfe5"), 1))
        for i in range(11):
            t = i/10
            for a,b in (((bx0+(bx1-bx0)*t, 0, bz0), (bx0+(bx1-bx0)*t, 0, bz1)),
                        ((bx0, 0, bz0+(bz1-bz0)*t), (bx1, 0, bz0+(bz1-bz0)*t))):
                pa,pb = project(a),project(b)
                painter.drawLine(round(pa[0]), round(pa[1]), round(pb[0]), round(pb[1]))

    points = view._visible_points()
    item_cache_key = (scene_key, view._points_revision)
    if view._item_render_cache_key != item_cache_key:
        view._item_render_cache = {}
        view._item_render_cache_key = item_cache_key
    for point in points:
        kind, label = point[3:]
        index = view._marker_index(point)
        selected = index is not None and index == view.selected_marker
        hovered = point == view.hovered_point
        position = view.preview_point if index is not None and index == view._drag_marker else None
        item_state = (selected, hovered, position)
        item_cached = view._item_render_cache.get(point)
        if item_cached is not None and item_cached[0] == item_state:
            surfaces.extend(item_cached[1])
            overlays.extend(item_cached[2])
            continue
        surface_start, overlay_start = len(surfaces), len(overlays)
        base, top = view._marker_geometry(point, position=position)
        color = QColor(COLORS.get(kind, "#64748b"))
        outline = QColor("#f59e0b") if selected else QColor("#1e293b") if hovered else None
        for part_base, part_top in view._marker_prisms(point, position=position):
            prism(part_base, part_top, color, outline, 2 if selected or hovered else 0.8)
        # Root direction is independent of the model's long edge or child rotation.
        if kind == "放置物品":
            center, front = view._marker_direction(point, position=position)
            overlays.append(("direction", (project(center), project(front)), selected or hovered))
        if selected or hovered:
            title = view.point_details.get((kind, label), {}).get("name", kind)
            caption = f"{title} · {label}"
            if kind == "放置物品":
                profile = view._marker_profile(point)
                caption += f" · {heading(view._marker_rotation(point)):.0f}°"
                if profile:
                    dimensions = [b-a for a,b in profile['bounds']]
                    caption += f" · {dimensions[0]:.2f}×{dimensions[2]:.2f}m"
                else:
                    caption += " · 估算尺寸"
            anchor = project(tuple(sum(v[i] for v in top)/4 for i in range(3)))
            overlays.append(("label", anchor, caption))
        view._item_render_cache[point] = (item_state, tuple(surfaces[surface_start:]), tuple(overlays[overlay_start:]))

    if view.placement_enabled and view.preview_point is not None:
        ghost = (*view.preview_point, "放置物品", "预览")
        base, top = view._marker_geometry(ghost, yaw=view.preview_yaw)
        for part_base, part_top in view._marker_prisms(ghost, yaw=view.preview_yaw):
            prism(part_base, part_top, QColor(59,130,246,150), QColor("#2563eb"), 1.5)
        center, front = view._marker_direction(ghost, yaw=view.preview_yaw)
        overlays.append(("direction", (project(center), project(front)), True))
        overlays.append(("label", project(center), f"点击放置 · {view.preview_yaw:.0f}°"))

    # Projection depth increases towards the camera: paint distant surfaces first.
    for _, poly, color, outline, width in sorted(surfaces, key=lambda item: item[0]):
        painter.setBrush(color)
        painter.setPen(QPen(outline, width))
        painter.drawPolygon(poly)
    for kind, geometry, caption in overlays:
        if kind == "direction":
            a,b = geometry
            dx,dy = b[0]-a[0],b[1]-a[1]
            length = math.hypot(dx,dy)
            if length < 1e-5:
                continue  # Forward points at the camera; do not invent a heading.
            if length < 2 and not caption:
                continue  # Do not make a tiny item look large with a giant arrow.
            dx,dy = dx/length,dy/length
            length = max(12 if caption else 3,min(26,length))
            tip = (a[0]+dx*length,a[1]+dy*length)
            wing = min(5,length*0.4)
            painter.setPen(QPen(QColor("#1e3a5f"), 1))
            painter.setBrush(QColor("#ffffff"))
            painter.drawPolygon(polygon([tip,(a[0]-dy*wing,a[1]+dx*wing),
                                         (a[0]+dx*length*0.2,a[1]+dy*length*0.2),
                                         (a[0]+dy*wing,a[1]-dx*wing)]))
    # Names are shown only for the hovered/selected object; labels never blanket the room.
    occupied = []
    for kind, anchor, caption in overlays:
        if kind != "label":
            continue
        width = min(view.width()-32, painter.fontMetrics().horizontalAdvance(caption)+24)
        rect = QRect(max(12, min(view.width()-width-12, round(anchor[0]-width/2))),
                     max(46, min(view.height()-65, round(anchor[1]-40))), width, 28)
        if any(rect.intersects(other) for other in occupied):
            continue
        occupied.append(rect)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(15,23,42,230))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QColor("#f8fafc"))
        painter.drawText(rect, Qt.AlignCenter, painter.fontMetrics().elidedText(caption, Qt.ElideRight, width-16))

    painter.setPen(Qt.NoPen)
    painter.setBrush(overlay_bg)
    status_rect = QRect(10,10,min(290,view.width()-136),30)
    painter.drawRoundedRect(status_rect, 6, 6)
    painter.setPen(overlay_text)
    status = f"{'存档区域' if view.view_mode == 'save' else '完整场景'} · 当前可见 {len(points)} 个对象"
    painter.drawText(status_rect.adjusted(12,0,-8,0), Qt.AlignVCenter,
                     painter.fontMetrics().elidedText(status, Qt.ElideRight, status_rect.width()-20))
    # World axes rotate with the view; do not label them as geographic north/east.
    painter.setPen(Qt.NoPen)
    painter.setBrush(overlay_bg)
    painter.drawRoundedRect(QRect(view.width()-116,10,106,102),6,6)
    ax,ay = view.width()-63,62
    reference = view._floor_reference()
    for axis, color, vector in (("+X", "#dc5b61", (1,reference,0)),
                                 ("+Z", "#3b82f6", (0,reference,1))):
        tx,ty,_ = view._project(*vector,26,ax,ay)
        dx,dy = tx-ax,ty-ay
        distance = (dx*dx+dy*dy)**0.5
        dx,dy = dx/distance,dy/distance
        painter.setPen(QPen(QColor(color),2))
        painter.drawLine(ax,ay,round(tx),round(ty))
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygon([QPoint(round(tx),round(ty)),
            QPoint(round(tx-6*dx+3*dy),round(ty-6*dy-3*dx)),
            QPoint(round(tx-6*dx-3*dy),round(ty-6*dy+3*dx))]))
        rect = QRect(round(tx+12*dx)-12,round(ty+12*dy)-9,24,18)
        painter.drawText(rect,Qt.AlignCenter,axis)
    painter.end()
