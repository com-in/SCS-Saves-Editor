# SCS Saves Edit - 项目长期笔记

## 项目概况

《诈骗园区模拟器》(Scam Center Simulator / UnderKingdom) 的 Unity ES3 存档修改器。
Python + PySide6，单文件 GUI 入口 `main.py` + 多个 `_xxx.py` 混入类（Mixin）模块。

## 架构约定

- `main.py` 中的 `ES3Editor(DocumentMixin, EditorUiMixin, ExtraPagesMixin, ModsPageMixin, QMainWindow)`
  由多个 mixin 组合而成；新增功能模块时写成独立 `_xxx_page.py` 的 mixin 再加入基类。
- 界面 = 左侧可折叠分组树导航（`QTreeWidget`）+ 右侧 `QStackedWidget` 分页。
- **新增页面的三处必须按顺序对齐**（索引即 stack 页号）：
  1. `self.nav_items` 追加 `(图标, 文字, key)`；
  2. 新建页面容器 `self.tab_xxx = QWidget()`；
  3. 页面容器加入 `self.stack.addWidget()` 的遍历元组，并在 `build_ui()` 中调用 `build_xxx_tab()`。
     如需调整分组显示顺序，同步改 `self._nav_groups`。
- QSS 里按页面 `objectName` 加样式（如 `QWidget#ModsPage QPushButton`），记得补上 disabled 态。
- 游戏目录设置沿用 `map/game_data_dir`（指向 `*_Data` 目录），取上一层即安装根目录。
- 后台耗时任务用 `QThread` 子类 + 信号；链式任务清理 worker 时要校验 `self.sender()`
  仍是当前 worker，否则会误清掉新起的线程。

## 环境

- 运行依赖：`PySide6`、`UnityPy`、`numpy`（见 requirements.txt）。
- 本机沙箱默认没有这些包；pip 官方源很慢，改用阿里云镜像
  `https://mirrors.aliyun.com/pypi/simple/`。
- GitHub release 的 CDN 直链在沙箱内会被代理拦（502），需要时用本地 http 服务验证下载逻辑。
- 测试：`python -m unittest tests.test_mods tests.test_editor tests.test_map`（离屏
  `QT_QPA_PLATFORM=offscreen`）。

## 文件用途速查

- `_document.py` 存档文档/读写；`_editor_ui.py` 通用 UI 构建；`_save_support.py` 原子写入与校验。
- `_extra_pages.py` 成长/采购/市政/装修等扩展页；`_mods_page.py` Mod 安装页。
- `_memscan.py` 内存扫描引擎（含 `find_game_process`）；`unity_scene_loader.py` Unity 场景解析。
- `mods_index.json` 在线 Mod 清单示例（`.gitignore` 里有 `!mods_index.json` 例外）。
