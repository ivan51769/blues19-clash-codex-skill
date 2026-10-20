# Clash Codex Optimizer · 公共技能

让 Codex/OpenAI 请求在 **Clash 规则模式**下按国家自动选择低延迟节点，并从这些自动组中排除名称标注 **超过 1 倍**的节点。

这是标准 `SKILL.md` 技能包，也可以不使用 AI 助手，直接将附带脚本安装到 Clash Verge 的全局扩展。没有模型 API、后台服务、账号采集、telemetry、权限提升或自动 TUN 设置。

## 功能

- **一条命令同时配置两层代理**：检测 Clash HTTP/mixed 端口，安装分流扩展，并生成 Codex 专用代理启动入口。
- **初始化分层诊断**：不因直连超时就跳过 Computer Use 检查；支持显式授权的一次正常重启、仅新日志观测和 unknown 结果，拒绝虚假的能力就绪结论。
- **仅作用于 Codex 进程树**：不写系统环境变量，不改原应用/快捷方式；已验证的 Electron 桌面端同时使用 Chromium `--proxy-server`。
- **跨订阅复用**：当前订阅每次经过全局扩展处理时重新筛选；不是将几个订阅合并。
- **250 个国家/地区预设**：249 个 ISO 3166-1 代码加 XK；只显示有合格节点的组。
- **排序置顶**：Codex 代理 → 日本自动 → 美国自动 → 新加坡自动 → 英国/香港/台湾 → 其他地区 → 原有组。
- **倍率过滤**：识别 `0.5x`、`2倍`、`×3`、`倍率:2` 等名称标记；冲突标记中只要一个超过 1 就排除。
- **防空组/误选**：排除“剩余流量、套餐到期”等说明条目；首选国家缺失时默认 `REJECT`，不自动直连或选高倍率节点。
- **自动测速**：使用中的组默认每 300 秒进行 HTTPS 延迟测试，50ms 切换容差。
- **保守安装**：默认只读预览，应用前逐字节备份；保护自定义脚本，支持完整性校验和回滚。
- **不破坏原分流**：保留原有分组与规则，新规则优先；名称冲突时拒绝而非删除原组。

> **重要边界**
>
> 倍率是名称推断，不是实际账单保证。默认保留未标倍率节点；可改为排除。国家标签不保证真实出口。延迟低不等于带宽大、地区受支持或 OpenAI 一定可用。
>
> 域名规则会影响进入 Clash 的**全部 OpenAI/ChatGPT 流量**，包括浏览器与其他客户端，不限 Codex。超过 1 倍的排除只约束本技能生成的自动组，**不会删除原订阅里的高倍率节点**。

## 安装为用户级技能

要求 Python 3.10+（标准库，不需要 pip）。从仓库根目录运行。

```bash
git clone https://github.com/ivan51769/blues19-clash-codex-skill.git
```

先预览 Claude Code 与 Codex 的用户级安装位置：

```bash
python -I blues19-clash-codex-skill/skills/clash-codex-optimizer/scripts/install_skill.py --target both
```

确认后安装：

```bash
python -I blues19-clash-codex-skill/skills/clash-codex-optimizer/scripts/install_skill.py --target both --apply
```

| 客户端 | 用户级位置 |
|---|---|
| Claude Code | `~/.claude/skills/clash-codex-optimizer/` |
| Codex | `~/.agents/skills/clash-codex-optimizer/` |

只安装一个客户端时，将 `both` 改为 `claude` 或 `codex`。工具不会改设置、权限或其他技能。升级已安装且完整性未变的本技能时，增加 `--upgrade`：先备份旧技能，再安装新版本；自定义或被编辑的技能仍拒绝覆盖。

新建会话后使用 `/clash-codex-optimizer`（以客户端的技能发现结果为准），或者说：

> 用 clash-codex-optimizer 检查 Codex 只有全局代理才能连接的问题；预设国家自动组，排除超过 1 倍节点，默认日本，先预览再应用。

技能安装与 Clash 配置安装是两件事；安装技能**不会自动修改网络配置**。

## 一次配置：Clash 分流 + Codex 代理端口

1. 在 Clash Verge 中确认数据目录，并启动 Clash。Windows 常见位置是 `%APPDATA%/io.github.clash-verge-rev.clash-verge-rev`；其他平台从应用中打开配置目录确认。
2. 确认真实 Codex 可执行文件与类型：CLI 使用 `--kind cli`；Windows Electron 桌面程序使用 `--kind electron`，工具会检查相邻的 Electron 资源。不要误选 `app-server` 后端来当桌面程序，也不使用 Store 启动别名或 `.cmd` shim 代替真实程序。
3. 从仓库根目录运行统一入口，默认只读预览**两项**配置：

```bash
python -I skills/clash-codex-optimizer/scripts/configure.py --clash-dir "<Clash-data-dir>" --codex-exe "<Codex-executable>" --kind electron
```

一次应用两项，不需要用户分开执行端口和分流命令：

```bash
python -I skills/clash-codex-optimizer/scripts/configure.py --clash-dir "<Clash-data-dir>" --codex-exe "<Codex-executable>" --kind electron --apply
```

CLI 将 `electron` 改为 `cli`。如果桌面资源中有 `owl-electron-app.json` 且 runtimeName 为 `owl`，必须显式使用 `--kind owl`；它会请求 Chromium 代理参数，但 **Owl 的参数支持和 GUI 路由仍需重启后实际验证**，不能据此宣称是标准 Electron。已运行桌面实例会阻止再次启动；不会强制关闭它。版本化程序路径在应用更新后失效时需重新配置。

可用 `--proxy-port` 指定已确认的本地 HTTP/mixed 端口；默认读取 Clash `config.yaml` 的顶层 `mixed-port`，否则使用 HTTP `port`。不会误用 `socks-port` 或 `external-controller`，不输出配置全文。端口未监听时应用前就失败；TCP 检测只证明端口开放，不能证明该进程一定是代理或服务可用。

统一入口先全部预检，再安装扩展与专用启动配置。若第二项失败，会尝试回滚第一项并明确报告回滚结果，不把半配置说成成功。

### 应用后怎么启动

- 结果会返回专用启动入口：Windows 为 `launch-codex.cmd`，CLI 的其他系统为 `launch-codex.sh`。它们存放在独立的用户级状态目录，不在仓库或订阅目录中。Windows 默认是 `~/.clash-codex-optimizer/`，避免从 MSIX 打包助手配置时，新建 LocalAppData 目录被虚拟化、导致从资源管理器启动找不到文件。
- **以后从这个专用入口启动 Codex**。原图标、原快捷方式、系统/用户环境变量不会被修改。
- 启动器只对子进程设置 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 及小写版本；将子进程的 `NO_PROXY` 限定为 loopback，避免继承 `*` 或 OpenAI 域名而绕过代理。
- 已验证的 Electron 桌面端还会带上 `--proxy-server`，覆盖只设置环境变量但 Chromium 前端未走代理的情况。
- 正在运行的 Electron/Owl 实例可能忽略新参数。启动器会检查并拒绝复用已运行实例；请先正常退出，再从专用入口打开。**不会强制杀进程，也不会声称配置能热更新到当前实例**。
- Windows `.cmd` 是启动专用，不转发额外 CLI 参数；需要参数时直接用 Python 执行状态目录中的 `launch_codex.py`。为支持中文路径，`.cmd` 会将其所附控制台切到 UTF-8 代码页 65001，不修改持久系统设置。
- 在 Clash Verge 中重新应用订阅/全局扩展，选择**规则模式**；在 **Codex 代理**中选择国家。最后在 Codex 中 Retry，确认工作区实际恢复。

工具不会改账号、认证、原程序、原快捷方式、系统代理、TUN、节点或运行时 YAML。普通配置不会重启应用；只有下一节显式授权的一次桌面修复才请求正常关闭并重新启动。自定义全局脚本仍拒绝静默覆盖。对已经人工审查的旧脚本，可用 `--reviewed-sha256 <exact-hash>` 明确批准一次内容完全匹配的迁移；哈希不同就停止，并且仍先备份。**不要把该参数当作跳过审查的 force 开关。**

### 两项一起回滚

统一执行返回的 transaction 路径仅保存在本地。使用相同 Clash 目录与 `--state-dir`（未自定义时可省略）：

```bash
python -I skills/clash-codex-optimizer/scripts/configure.py --clash-dir "<Clash-data-dir>" --restore "<transaction-path>"
```

```bash
python -I skills/clash-codex-optimizer/scripts/configure.py --clash-dir "<Clash-data-dir>" --restore "<transaction-path>" --apply
```

会先校验两项备份与当前内容。脚本/启动器若被修改，拒绝覆盖，避免丢失新修改。回滚后仍需 Clash 重新应用配置，并在正常退出后从用户希望使用的入口重开 Codex。

### 高级：只安装扩展

需要兼容旧流程时仍可单独使用 `scripts/install.py`；此入口**不会配置 Codex 端口**。它仅写 `profiles/Script.js`，备份在 `profiles/.clash-codex-backups/`。公共技能默认使用上面的统一入口。

所有本地状态、备份、transaction 和程序路径**都不要上传**。

## Computer Use 初始化问题：代理、一次重启与分层检查

**不要因为直连探测超时就跳过 Computer Use 检查，也不要直接认定它被网络禁用。** “后端已连接”“组件已复制”“插件同步完成”“窗口出现”和 API 401 都不是能力就绪证明。

v1.2 可在统一配置后，执行**用户明确授权的一次正常重启**并观察本次启动的新日志。普通预览/应用、技能安装/升级和回滚仍不关闭或启动 Codex。

```bash
python -I skills/clash-codex-optimizer/scripts/configure.py --clash-dir "<Clash-data-dir>" --codex-exe "<Codex-executable>" --kind owl --desktop-action restart --action-id "<single-use-32-hex-id>" --startup-log-dir "<Codex-desktop-Logs-dir>" --apply
```

- 技能为**本次授权**生成一次 ID，并在工具超时/返回不确定时保留同一 ID，不换 ID 反复重启。每个 ID 通过独占本地记录最多允许一次动作；记录在 `~/.clash-codex-actions/` 等状态同级目录，不在公开仓库中。
- 不带 `--apply` 只预览；不带 `--desktop-action restart` 不重启。同一次已授权修复不再逐项重复询问，但不绕过工具本身的审批边界。
- 仅 Windows 桌面支持此动作。核实完整程序路径、PID、父 PID 和创建时间后，向该浏览器根进程的可见窗口发 `WM_CLOSE`；拒绝退出、保存提示、后台残留、身份变化或并发实例都会停止。绝不强制终止、点掉保存提示或关闭其他工具。
- 如果关闭窗口后程序仍在托盘/后台，结果会是 `close_timeout`，不会把“窗口消失”当作完全退出；此时请用户保存工作并使用应用菜单/托盘的“退出”，不要改用强制终止。没有实际启动时，网络检查标记为 `not_checked`，而不是“未发现错误”。
- 正常退出后通过已有进程级代理环境与同一组启动参数尝试启动一次。早退、单实例交接或无法确认新根 PID 时不重试，也不声称新代理已激活。Owl 支持仍需实际路由证据。
- `--startup-log-dir` 必须是明确确认的**桌面 Logs 目录**，不是账号、对话或 Codex 主数据目录。先记录文件身份/EOF，再仅看启动时间之后、日志文件 PID 与新桌面匹配的事件；限制目录、字节、行长及观察时间。
- 默认观察 60 秒，可用 `--readiness-timeout` 设置 0–120 秒。只输出允许的事件类别和计数，不输出原始日志、URL 查询、对话或凭据。

### 分别报告，不混为一个“成功”

| 项目 | 可报告的证据 |
|---|---|
| 配置已保存 | 两项配置和备份完整性通过 |
| 本地后端已连接 | 本次桌面 PID 的新 stdio 初始化/连接事件 |
| 请求/功能配置超时 | 新桌面日志明确报告请求超时或功能配置 bootstrap 超时；不猜测直连/代理归因 |
| Computer Use | 当前已知日志格式没有经过验证的能力就绪事件，保持 **unknown**；需在应用中确认能力或做获准的最小只读验证 |

`cua-swift-helper` 组件解析成功、通用插件跳过或 gate-disabled **不会**被当成 Computer Use 已就绪/已禁用的证据。不会自动开启 OS 权限、修改许可、解除策略或启用未授权能力。

显式修复返回 **退出码 2** 表示配置已保存，但启动或能力未完全验证；请看结构化分层结果，**不要自动再重启**。生命周期失败不回滚已成功保存的配置，回滚配置也不自动关闭应用。启动/退出超时与未知状态不等于功能被永久禁用。

## 自定义参数

配置在 [`global-script.template.js`](skills/clash-codex-optimizer/assets/global-script.template.js) 顶部：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `maxMultiplier` | `1` | 允许 0–1；不会接受更高上限 |
| `keepUnmarked` | `true` | `false` 可排除所有未识别倍率节点 |
| `preferredCountry` | `JP` | 改为 `US` / `SG` 等；无该地区节点时默认拒绝 |
| `countryPriority` | JP、US、SG、GB、HK、TW | 决定分组排列顺序 |
| `interval` | `300` | 秒，最小 60 |
| `tolerance` | `50` | 毫秒；减少因微小延迟波动换节点 |
| `testUrl` | Google HTTPS 204 | 会向该地址发送健康检测流量，不代表 Codex 健康检查 |
| `routeDomains` | `true` | OpenAI/ChatGPT 域名分流；对其他客户端也生效 |
| `routeProcess` | `true` | `codex.exe` / `Codex.exe`；依赖 Clash 进程识别 |

开发者修改模板后生成脚本（需要 Node.js 20+）：

```bash
node skills/clash-codex-optimizer/scripts/build.cjs
```

或者将可信的生成脚本放入 Clash 的全局扩展编辑器中人工修改。人工编辑后的文件不再符合旧安装清单，自动更新/回滚可能拒绝覆盖，这是保护而非错误。

## 兼容性与限制

- 为 Clash Verge 的 JavaScript 全局扩展接口 `main(config, profileName)` 编写。
- 仅支持展开到 `config.proxies` 的订阅；**provider-only 配置明确拒绝**，不会声称跨全部配置兼容。
- 全局脚本命名冲突、自定义脚本、被修改的管理组会明确拒绝；不静默覆盖用户分流。
- 命名不明确的节点会进入“其他地区自动”；可手动排除。只支持文档与测试列出的倍率写法，不识别订阅未公布的账单倍率。
- 当前手工联网验证环境为 Windows + Clash Verge/Mihomo。公开版有额外所有权/冲突保护；其自动化测试使用虚构数据，不宣称在所有系统/应用版本上完成联网验证。
- 桌面启动器当前仅支持 Windows 的已识别 Electron/Owl 包；其他系统仅支持 CLI，桌面模式在预检阶段就会拒绝。
- Python 工具拒绝 symlink/junction/reparse-point 路径；需要链接目录的用户请人工集成。
- 本项目不改变服务地区限制，不保证特定国家的节点可使用 OpenAI。

## 开发与测试

没有 npm 或 pip 依赖，安装用户不需要 Node.js。开发测试使用 Node.js 20+ 与 Python 3.10+。

```bash
npm test
```

测试覆盖倍率、250 个地区代码、排序、空组、原规则保留、幂等性、名称冲突、订阅变化、端口检测、子进程环境、运行中桌面拒绝启动，以及临时目录中的统一应用/回滚、恢复世代绑定、旧技能升级和并发修改保护。Windows 不具备创建符号链接权限时，相应测试会显式跳过。

仓库只包含代码、国家表、文档和虚构测试。**请勿提交订阅链接、token、节点密码、控制器 secret、运行时配置、备份、连接日志或用户专用路径。**

## 参考

- [Claude Code 技能文档](https://code.claude.com/docs/en/skills)
- [Codex 技能文档](https://developers.openai.com/codex/skills/)
- [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)
- [Mihomo 代理组文档](https://wiki.metacubex.one/config/proxy-groups/)

国家名称表是冻结的公开地理名称数据，初始标签使用 Node.js `Intl.DisplayNames` 生成，附带常用中文展示名修正；构建时不访问互联网，也不根据构建机器重新翻译。

## License

[MIT](LICENSE)
