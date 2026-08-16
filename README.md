# 诈骗园区模拟器 - ES3 存档修改器

基于 Python + PySide6 开发的《诈骗园区模拟器》存档修改工具。可安全读取、编辑并写回 Unity **ES3** 格式存档（JSON，顶层 key 为 `"__type"` / `"value"` 包装），内置自动备份，防止误改损坏存档。

## ✨ 功能特性

- **安全读写**：支持打开 / 保存 `.es3` 存档，写回时使用临时文件 + 原子替换，避免数据损坏。
- **自动备份**：每次保存前自动把原档备份到存档同目录下的 `ES3_Backups/` 文件夹。
- **基础数据**：货币、等级、经验、天数、电力、店名、呼叫数据、难度等一键编辑。
- **工人管理**：查看 / 修改工资金钱、能力值、状态，支持搜索、批量加满、重置状态。
- **加密货币 / 物品 / 放置物品 / 升级 / 其他**：表格或原始 JSON 编辑。
- **界面**：左右布局 + 可折叠侧边栏、亮色 / 暗色主题切换、默认全屏、标题栏显示当前文件名。

## 🚀 本地运行

```bash
# 安装依赖（Python 3.10+）
pip install -r requirements.txt

# 启动
python main.py
```

## 📦 打包发布

程序已配置 **GitHub Actions**（`.github/workflows/build.yml`），会在推送到 `v*` 标签时自动用 PyInstaller 打包（内嵌 `icon.ico`），打包结果上传为 **Artifact** 并发布 **GitHub Release**。

```bash
# 手动本地打包
pyinstaller --noconfirm --clean --onefile --windowed `
  --name "SCS存档修改器" `
  --icon "icon.ico" `
  --add-data "icon.ico;." `
  "main.py"
```

> 发布新版本：推一个新标签（如 `v1.1.0`）即可自动触发构建与发布。

## 📁 项目结构

```
main.py                     # 程序入口（PySide6 界面 + 存档处理）
icon.ico                    # 程序 / exe 图标
requirements.txt            # 依赖
.github/workflows/build.yml # 自动打包并发布 Release
ES3_Backups/                # 保存时自动生成的备份目录
```

## ⚠️ 使用提示

- 修改后请点击顶部的【保存存档】才会写入文件。
- 涉及结构复杂的数据（物品 / 放置物品 / 其他）以原始 JSON 形式提供，仅在你了解结构时修改。
- 每次保存前会自动备份，若改坏可用 `ES3_Backups/` 里的备份还原。

## 许可

仅供学习与存档修改交流使用，请勿用于破坏他人游戏体验。