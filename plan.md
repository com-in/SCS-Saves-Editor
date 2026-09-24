# AI 执行计划：SCS Saves Editor 真实 Unity 游戏地图渲染

## 0. 执行目标

在现有 SCS Saves Editor 中新增"真实游戏地图 3D 预览"功能。

功能目标：

1. 修复当前 `placed_table` 初始化错误。
2. 保证原有存档编辑、加载、保存、查找存档、默认最大化和主题 UI 不回归。
3. 读取 `F:\GameUnpack\UnderKingdom` 中的 Unity 游戏资源。
4. 解析真实游戏场景中的 Terrain / Mesh / GameObject / Transform / Material / Texture / Light / Collider。
5. 在修改器内显示可旋转、缩放、平移的真实 3D 场景。
6. 将存档中的 `PlaceItems`、`Items`、`Workers`、`Dirt` 坐标叠加到真实地图上。
7. 支持按对象类别显示/隐藏。
8. 支持点击场景对象查看来源、坐标和存档字段。
9. 支持在不修改游戏原始资源的情况下生成缓存和预览数据。
10. 失败时必须降级为可用的场景骨架或坐标点云视图。

---

## 1. 已知问题与资源位置

### 1.1 placed_table 初始化错误（已修复）

`build_placed_and_other_tab()` 已从 `refresh_map3d` 中拆出，`build_ui` 调用序列已修正，18 项回归测试全部通过。

### 1.2 Unity 资源位置

```text
F:\GameUnpack\UnderKingdom\
F:\GameUnpack\UnderKingdom\Scam Center Simulator UnderKingdom_Data\
```

关键文件：

```text
level0 / level1                       # 场景文件（level0: 2995 对象，无内嵌 Mesh）
globalgamemanagers / .assets
sharedassets0.assets                  # 52 Mesh / 51 Material / 120 Texture2D / 142 Sprite
sharedassets1.assets                  # 3320 Mesh / 767 Material / 1932 Texture2D / 36707 GameObject
resources.assets                      # 24 Material / 177 Texture2D
StreamingAssets\aa\StandaloneWindows64\*.bundle   # 本地化资源（非主场景）
```

游戏为 URP 渲染管线，依赖 Addressables、glTFast、ProBuilder、Terrain 模块。

### 1.3 解析依赖

- UnityPy 1.25.3 已安装（用户已允许联网安装，MIT 许可）。
- numpy 已安装。渲染采用 QOpenGLWidget 自研 GLSL 渲染器（零新增依赖），失败降级 QPainter 软渲染。

---

## 2. 执行顺序约束

严格按顺序执行；任意阶段失败则记录原因、保留当前可运行版本、实现降级路径，不得跳过验证直接宣布完成：

```text
A. 读取仓库状态
B. 修复 placed_table 初始化问题（已完成）
C. 运行语法和初始化测试
D. 扫描 Unity 资源（已完成：上述清单）
E. 确定资源解析方案（已确定：UnityPy）
F. 建立中间格式
G. 实现缓存
H. 实现真实场景渲染
I. 接入 UI
J. 接入存档对象叠加
K. 运行回归测试
L. 更新 README 和 CHANGELOG
M. 检查 git diff
N. 只有验证完成后才创建发布构建
```

---

## 3. 代码结构规划

新增文件（置于 `F:\Projects\文件夹\SCS Saves Edit`）：

```text
_map3d_loader.py    # UnityPy 解析资源 -> 中间数据；版本差异；结构化错误；不操作 Qt
_map3d_cache.py     # 资源指纹(SHA-256+尺寸+时间+解析器版本)；JSON/模型/贴图缓存；原子写入；失败保留旧缓存
_map3d_scene.py     # 场景节点、层级、变换计算、场景过滤、存档对象叠加
_map3d_renderer.py  # QOpenGLWidget GLSL 渲染：相机/光照/网格/材质/拾取；OpenGL 不可用降级 QPainter
_map3d_overlay.py   # 图例、加载进度、错误提示、对象详情、过滤器
plan.md             # 本执行计划
cache\unity_scene\  # 缓存目录（scene_manifest.json / level*_scene.json / meshes\ / textures\ / terrain\）
```

中间格式（scene_manifest.json 结构）：

```json
{
  "scene": "level0",
  "objects": [
    {
      "path": "Root/Building/Wall", "name": "Wall", "type": "MeshRenderer",
      "mesh": "mesh_123", "material": ["mat_456"],
      "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0, 1.0],
      "scale": [1.0, 1.0, 1.0], "active": true
    }
  ],
  "meshes": {}, "materials": {}, "textures": {}, "terrain": {}
}
```

坐标转换约定：Unity X 右 / Y 上 / Z 前；出现镜像或正反面错误统一修正（Z 翻转、winding、法线、UV V）。

## 4. UI 集成

- 导航"工具"分组保留 `🌐 游戏地图`（不再用"3D地图 Demo"）。
- 页面：顶部场景选择/加载刷新/重新解析/清空缓存/状态；左侧过滤器（Terrain/建筑/道具/物品/工人/污垢/灯光/存档对象）；中央 3D 视口；右侧对象详情（名称/路径/类型/位置/旋转/缩放/Mesh/材质/存档字段）。
- 交互：左键旋转、中键平移、滚轮缩放、双击详情、F 聚焦、R 重置相机，默认俯视+包围盒适配。
- 存档叠加：PlaceItems→放置物品、Items→物品、Workers→工人、Dirt→污垢，不同颜色标记；点击显示来源键/数组索引/ID/坐标/原始 JSON；坐标系偏移/缩放/轴翻转可配置。

## 5. 异步与错误处理

- UnityPy 解析运行在 QThread，主线程只做进度/取消/结果切换/错误显示。
- 进度阶段：扫描资源→识别场景→读取对象→读取网格→读取材质→读取贴图→构建缓存→上传 GPU→完成。
- 错误等级：可恢复（单模型/贴图/Shader/Transform 缺失→日志+跳过）、场景级（显示错误+点云降级+保留编辑器）、程序级（OpenGL 初始化失败→文本错误+资源统计页，绝不影响存档编辑）。

## 6. 缓存策略

- 指纹：文件路径 + 大小 + 修改时间 + SHA-256 + 解析器版本 + 格式版本。
- 失效：资源变化/解析器版本变化/用户"重新解析"/缓存损坏/模型缺失。
- 安全：临时文件原子替换；不覆盖原始 Unity 文件；失败保留旧缓存；清缓存二次确认。

## 7. 测试与验收

- 静态：`python -m py_compile` 全部通过。
- 初始化：ES3Editor 可创建，placed_table/items_table/map3d_view 存在，导航与 stack 页数正确。
- 回归：awapro.es3 / 666.es3 / 空骨架 / 缺 PlaceItems / 缺 Workers / 损坏 JSON 均可打开、切换、保存、另存为；地图失败不阻止基础编辑。
- Unity：level0 / level1 / 共享资源 / 无贴图 / 无材质 / TerrainData / 空场景 / 损坏资源。
- 性能：启动不阻塞；首次解析显示进度；二次走缓存；1 万三角形流畅旋转。

## 8. 构建与发布

- requirements.txt 只加实际使用依赖（UnityPy）。
- PyInstaller 需包含地图解析/渲染模块；不得把整个 UnderKingdom 目录打进发布包。
- 首次运行自动检测游戏目录、允许手动选择并保存设置；缺资源时地图页显示未找到+选择按钮。

## 9. 完成标准

- `py_compile` 通过；无 placed_table/map3d_view AttributeError。
- 原有功能可打开/查找/编辑/保存/另存为；窗口最大化；主题切换正常。
- 地图：能读取至少一个 level 文件；显示真实场景对象或 Terrain；可旋转/缩放/平移；分类显示；叠加存档坐标。
- 降级：Unity 解析失败时编辑器仍可用、地图页显示明确错误、可切换点云、不破坏存档。
- 文档：README 使用说明、CHANGELOG 版本记录、plan.md 保留本计划。
- Git：diff 检查通过、status 清晰、无临时缓存与游戏原始资源提交。
