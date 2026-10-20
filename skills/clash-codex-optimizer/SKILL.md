---
name: clash-codex-optimizer
description: Configure Codex proxy ports and Clash country routing together. Diagnose global-mode-only connectivity, detect local HTTP/mixed ports, create a process-scoped Codex proxy launcher, install country auto-selection groups with <=1x name-label filtering, and back up or restore both. Use for workspace-settings errors, Codex proxy settings, country switching, and rule-mode routing.
---

# Codex 代理端口 + Clash 国家分流：一起执行

默认使用**统一入口**同时处理两层设置：
1. Codex → Clash 本地 HTTP/mixed 代理端口；
2. Clash → 国家自动组与低倍率节点。

不是只添加规则就声称 Codex 已走代理。也不让已明确要求配置的用户再分别执行两个安装命令。仅需 Python 3.10+ 标准库，不使用模型 API、不装常驻服务、hooks 或权限规则。

## 必须遵守的边界

- 仅优化用户有权管理的本地配置，不保证服务可用性，不绕过账号、地区或访问限制。
- 倍率来自**节点名称**，不是账单验证；默认保留未标倍率节点，严格模式改为 `keepUnmarked: false`。国家标签不保证真实出口；延迟最低不等于带宽最大或 OpenAI 可用。
- 域名规则影响进入 Clash 的**所有 OpenAI/ChatGPT 流量**，不限 Codex。`routeProcess` 默认只匹配 `codex.exe` 后端，不保证匹配使用其他文件名的 GUI。
- 不写用户/系统环境变量、注册表、账号或认证文件，不改原 EXE/快捷方式，不擅自开 TUN、系统代理或全局模式。
- 专用启动器只影响新启动的 Codex 及其子进程。配置已生成，不等于运行中的桌面实例已生效。
- 仅支持展开为 `config.proxies` 的订阅；provider-only 需要人工集成。

## 1. 只读诊断与客户端识别

先定位**本 SKILL.md 所在目录**，下文记为 `<skill-dir>`。

1. 确认 Clash 数据目录、用户国家偏好和倍率上限；默认日本、上限 1 倍。Windows 常见目录是 `%APPDATA%/io.github.clash-verge-rev.clash-verge-rev`，其他平台从应用打开目录确认。
2. 仅检查必要的顶层端口配置、脚本状态和程序身份，不输出完整配置、订阅、secret、账号凭据或进程命令行。
3. 确认 **实际 Codex 可执行文件**：不能把 `app-server` 后端、用量悬浮条、npm `.cmd/.ps1` shim 当作桌面入口。Windows MSIX 应优先参考包清单的 Application Executable，而非猜一个 `Codex.exe`；实际入口可能叫 `ChatGPT.exe`。
4. 明确类型：`cli`、`electron`、`owl`。Electron 资源存在不一定代表标准 Electron：若有 `resources/owl-electron-app.json` 且 runtimeName 为 owl，使用显式 `owl` 兼容模式并说明代理参数未验证。不要把 Owl 当作已验证的 Electron。
5. 出现多客户端歧义时询问用户，不猜版本最新的后台进程。版本化 MSIX 路径更新后若失效，应重新配置，不擅自换到另一个程序。
6. 检查现有全局脚本是否默认/本技能管理；自定义或被修改的文件不能静默覆盖。

## 2. 一次预览两项

```bash
python -I "<skill-dir>/scripts/configure.py" --clash-dir "<Clash-data-dir>" --codex-exe "<Codex-executable>" --kind <client-kind>
```

`<client-kind>` 替换为 `cli`、`electron` 或 `owl`。必要时增加 `--proxy-port <confirmed-port>`，只接受本地 HTTP/mixed 代理端口，不接受 SOCKS-only/控制器端口。默认从 Clash `config.yaml` 的顶层 `mixed-port`，否则 HTTP `port` 检测，并验证 loopback 监听；TCP 可连不等于已确认代理协议或服务可用。

预览不写入、不启动 Codex。任何一项预检失败都不应用另一项。

## 3. 用户要求执行时，两项一起应用

用户已要求“帮我配置/一起执行”即构成该范围授权；只有询问原理时仍只预览。不要拆成两次让用户手工执行。

```bash
python -I "<skill-dir>/scripts/configure.py" --clash-dir "<Clash-data-dir>" --codex-exe "<Codex-executable>" --kind <client-kind> --apply
```

统一入口复用安全安装器，为 Clash 脚本和 Codex 专用启动配置分别备份，并返回统一 transaction。第二项出错时尝试补偿回滚第一项；若并发修改导致无法安全回滚，要明确报告部分状态与恢复记录，不能宣称绝对原子性。

- 不改运行时 YAML、模式、TUN、系统代理或账号。
- 不使用无条件 force。只有经过人工内容审查的旧脚本，才可用 `--reviewed-sha256 <exact-hash>` 显式批准一次完全一致的迁移，仍先备份并立即复核；不得现算未知脚本哈希就自动当作审查授权。
- 状态与备份保存在仓库外本机目录，绝不提交 Git。可用 `--state-dir` 明确指定支持的本地状态目录。
- 修改选项时审查可信脚本副本并验证，不伪造旧清单绕过保护。

## 4. 启动与实际验证

1. 从命令返回的专用入口启动：Windows 为 `launch-codex.cmd`，CLI 其他系统为 `launch-codex.sh`。原图标/快捷方式不会改变，以后继续使用原图标可能仍不带这份配置。
2. 启动器只在子进程设置 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 和小写版本；将子进程的 `NO_PROXY` 设为 loopback，避免继承外部直连绕过列表。父进程和全系统环境不变。
3. 标准 Electron 桌面还设置 `--proxy-server`；Owl 显式兼容模式只代表请求该 Chromium 参数，**必须实际验证**，不能声称 GUI 支持已确认。
4. 如同路径桌面程序已经运行，启动器会拒绝复用旧实例。让用户保存工作并正常退出后再启动，不强制杀进程、不用新 user-data-dir 偷换账号上下文。
5. 在 Clash 中重新应用订阅/全局扩展，使用用户批准的规则模式。查看组顺序：`Codex 代理 → 日本自动 → 美国自动 → 新加坡自动 → 其他地区 → 原有组`，在 Codex 代理里切国家。
6. 分别验证后端代理环境、GUI 请求代理链与 Codex 工作区加载。无凭据 API 的 401 只能证明抵达服务；403/challenge 不是恢复证据。不自动发真实聊天/收费 API 请求。
7. 报告四个不同状态：文件已配置、Clash 已重新应用、Codex 已从新入口启动、工作区已恢复。无法不重启就完成的验证明确写出。

## 5. 两项一起回滚

保留统一执行返回的 transaction 路径；自定义状态目录时使用相同 `--state-dir`。

```bash
python -I "<skill-dir>/scripts/configure.py" --clash-dir "<Clash-data-dir>" --restore "<transaction-path>"
```

```bash
python -I "<skill-dir>/scripts/configure.py" --clash-dir "<Clash-data-dir>" --restore "<transaction-path>" --apply
```

两项先验证完整性；若文件被编辑，拒绝覆盖并让用户人工比较。回滚不会杀进程，Clash 仍需重新应用，Codex 仍需正常退出后从希望使用的入口重开。

## 策略与高级入口

- 国家表：249 个 ISO 3166-1 国家/地区代码加 XK；只显示有合格节点的组，不合并多个订阅。
- 最高倍率 1；未标倍率默认保留可配置；首选 JP 不可用时默认 REJECT，不用高倍率或 DIRECT 兜底。
- 自动测速：HTTPS 204，300 秒、50ms 容差；只代表目标连通延迟。
- 原组与原规则保留，新增规则置顶；名称冲突明确拒绝。
- `scripts/install.py` 仍是只安装 Clash 扩展的高级入口，**不是默认执行流程**。
- 更新用户级技能使用 `scripts/install_skill.py --target both --upgrade --apply`：先校验旧安装清单、备份，再更新；被编辑/来源不明的技能拒绝覆盖。

## 发布隐私

只公开源码、说明、国家表和虚构测试。不要附带本机路径、订阅链接、token、代理认证、节点配置、控制器 secret、启动状态、transaction、运行时 YAML、备份、日志或截图。不得整体提交 Clash/Codex 数据目录。
