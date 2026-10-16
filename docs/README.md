# Mod 链接清单

## GitHub Pages 部署

此目录已包含静态首页 `index.html` 和 `.nojekyll`，可直接作为 Pages 发布目录，无需安装依赖或构建。

1. 将 `docs` 目录提交并推送到仓库 `main` 分支。
2. 在仓库 Settings → Pages 中将 Source 设为 **GitHub Actions**（首页更新 CI 会直接部署 `docs`）。
3. 发布 Release，或在 Actions 中手动运行“更新首页下载与 Pages”，等待部署完成。手动运行使用最新的正式 Release，需包含已上传的 EXE。

按当前仓库名称，默认站点地址为 `https://com-in.github.io/SCS-Saves-Editor/`，在线 JSON 清单地址为 `https://com-in.github.io/SCS-Saves-Editor/mods_index.json`。这是部署后的预期地址，实际发布状态请以仓库 Pages 页面为准；使用自定义域名时以实际域名替换。

修改器中填写 JSON 地址，不是站点首页地址。首页也提供自动生成的 JSON 地址和复制按钮，兼容项目子路径及自定义域名。

后续编辑 `docs/mods_index.json` 并推送后，手动运行“更新首页下载与 Pages”即可重新部署清单。`mods_index.example.json` 仅供参考，不要将其中的示例链接加入正式清单。

## Release 下载按钮自动更新

`.github/workflows/update-download.yml` 在 Release 发布后读取实际上传的 `SCS.exe`，将首页“加速下载（国内）”按钮改为 `https://gh-proxy.org/` 加上该文件的 GitHub 下载地址，然后提交到默认分支并部署 Pages。保留 GitHub 原始下载入口。例如：`https://gh-proxy.org/https://github.com/com-in/SCS-Saves-Editor/releases/download/v1.3.0/SCS.exe`。未上传 `SCS.exe` 时流程会报错，不会更新为其他文件。

现有“打包发布”流程在创建 Release、上传文件完成后也会调用此流程，兼容由 `GITHUB_TOKEN` 创建的 Release 不会触发后续 Release 事件的情况。预发布版本通过发布事件同样可以更新按钮；手动运行时选择最新正式版本。

需允许工作流写入仓库内容及部署 Pages；默认分支保护规则也需允许该机器人提交。`github-pages` 环境的部署分支规则需允许 Release 标签及默认分支。CI 不会自动修改仓库保护规则。代理服务为第三方，页面同时保留 GitHub 下载作为备用入口。

## 清单格式

正式清单为 `mods_index.json`，安装 Mod 页默认使用此文件。当前尚未收录真实 Mod 链接，因此 `mods` 为空；可参考 `mods_index.example.json` 添加条目。示例域名仅用于展示格式，不能下载安装。

每个 Mod 对应 `mods` 数组中的一个对象：

| 字段 | 用途 |
| --- | --- |
| `id` | 稳定且唯一的标识，建议与插件 DLL 文件名或插件文件夹名相同（DLL 不带扩展名） |
| `name` | 显示名称；单 DLL 下载会以此名称生成文件名 |
| `version` | Mod 版本，仅用于显示 |
| `author` | 作者名称 |
| `description` | 功能说明、支持的游戏版本和依赖；依赖需要自行安装 |
| `download` | 完整 HTTP/HTTPS 文件直链，指向 ZIP 或 DLL，可带查询参数 |
| `homepage` | Mod 发布页或项目主页 |

将示例对象复制到正式清单的 `mods` 数组，替换所有示例字段。多个对象之间使用逗号分隔，最后一项后不要加逗号；JSON 不支持注释。

DLL 链接的 URL 路径应以 `.dll` 结尾；其他地址按 ZIP 解析。ZIP 支持 `BepInEx/plugins/`、`plugins/`、根目录 DLL 或单目录包裹布局。网页展示页、需要登录的网盘页面和提取码页面不能作为下载地址。

在安装 Mod 页点击“本地清单…”选择此 JSON，再点击“刷新”加载。托管在线清单时，填写返回原始 JSON 内容的 URL（例如 GitHub 的 Raw 地址），不要填写仓库文件预览页。仅打开清单或主页不会安装 Mod，需选择条目并点击“安装所选”。

清单中的版本不会触发自动更新，也不会校验文件哈希；“已安装”状态按插件名称匹配，仅供参考。
