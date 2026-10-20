---
name: clash-codex-optimizer
description: Diagnose Codex connectivity that only works in Clash global mode, install safe global country auto-selection groups, filter node-name multipliers above 1x, prioritize Japan/US/Singapore, and back up or restore Clash Verge extensions. Use for Codex workspace-settings connection errors, Clash rule-mode routing, country switching, and low-multiplier automatic node selection.
---

# Clash / Codex 国家自动分流优化

为 Clash Verge 的**全局扩展脚本**提供国家选择、低倍率筛选和 Codex/OpenAI 分流。不使用模型 API、不需要账号凭据，也不安装常驻进程、hooks 或权限规则。

## 先说明边界

- 本技能不保证服务可用性，不绕过服务的账号、地区或访问限制。只优化用户有权管理的本地代理配置。
- 倍率来自**节点名称**，不验证实际计费。默认保留未标倍率节点；需要严格限制时将 `keepUnmarked` 改为 `false`。
- 国旗、国家名、城市名只是出口位置线索；延迟最低不代表带宽最大或 OpenAI 可用。
- 域名规则作用于进入 Clash 的**所有 OpenAI/ChatGPT 流量**，不限 Codex。可配置 `routeDomains: false`，但单独进程规则依赖进程识别。
- 请求必须先进入 Clash。仅增加规则不会让绕过 Clash 的直连流量自动被捕获；不要擅自开启 TUN、系统代理或全局模式。
- 支持展开为 `config.proxies` 的订阅；provider-only 配置会明确拒绝，需要人工集成。

## 工作流程

### 1. 只读诊断

1. 询问/确认用户想修复的症状、国家偏好和倍率上限；默认是日本、上限 1 倍。
2. 找到 Clash Verge 数据目录，确认 `profiles/Script.js` 是否为默认模板、自定义脚本或本技能管理的版本。不要读取登录凭据；不要输出完整订阅、节点密码、控制器 secret 或连接日志。
3. 根据用户允许的范围检查规则/全局模式、Codex 是否使用本地代理，以及现有策略组。全局能用而规则模式失败是分流线索，不是单凭截图即可确认的根因。
4. 区分保存扩展脚本、Clash 重新生成配置、实际路由成功三种状态，不把文件写入成功说成应用已恢复。

Windows 常见数据目录为 `%APPDATA%/io.github.clash-verge-rev.clash-verge-rev`。其他平台让用户从 Clash Verge 打开配置目录并确认；不要猜测其他用户的主目录。

### 2. 预览安装

先定位**本 SKILL.md 所在目录**，下文用 `<skill-dir>` 表示该目录。安装工具仅需 Python 3.10+ 标准库。

```bash
python -I "<skill-dir>/scripts/install.py" --clash-dir "<Clash-data-dir>"
```

默认只读预览，不创建目录/备份，不修改订阅、运行时 YAML、模式或系统代理。

- 默认空脚本可以应用；自定义脚本、名称冲突或被编辑的管理版本不可静默覆盖。
- 自定义脚本需要人工审查并组合，不使用 `--force`，也不要求删除现有脚本。
- 如果用户需要调整参数，在可信的脚本副本中修改顶端 `CODEX_OPTIONS`，解释差异并验证后由用户在 Clash 界面人工合并。不要为绕过完整性保护而伪造安装记录。

### 3. 明确获准后应用

用户要求“帮我配置/安装”已构成该范围授权；只有询问原理时不要直接写入。

```bash
python -I "<skill-dir>/scripts/install.py" --clash-dir "<Clash-data-dir>" --apply
```

它只写 `profiles/Script.js`，原文件字节与清单保存在该目录下 `.clash-codex-backups/` 的唯一备份子目录中。记录命令返回的 manifest 路径；备份只保留本地，不能提交到 Git 或上传。

若需要切回规则模式、重启应用或更改系统代理，单独说明并获取相应授权；安装工具不会自动执行这些操作。

### 4. 在 Clash 中启用与验证

1. 让 Clash Verge 重新应用当前订阅/全局扩展脚本，保持用户批准的规则模式。不要覆盖应用管理的运行时 YAML。
2. 查看代理组顺序：`Codex 代理 → 日本自动 → 美国自动 → 新加坡自动 → 其他国家/地区 → 原有组`。无合格节点的国家不会显示。
3. 在 `Codex 代理` 中选择国家，自动组按 HTTPS 延迟选择节点；默认每 300 秒检测，50ms 容差。
4. 检查匹配请求的规则与代理链。进程识别失败时不能宣称进程规则已验证。
5. 网络可达与账号功能分别验证：无凭据 API 返回 401 可以证明抵达服务，但不是登录成功；403/Cloudflare challenge 不是应用恢复证据。最后让用户在 Codex 中 Retry/重开并确认工作区加载。
6. 不自动关闭现有连接、不强制重启，不发真实聊天请求或收费 API 测试。

### 5. 回滚

先预览，再确认应用：

```bash
python -I "<skill-dir>/scripts/install.py" --clash-dir "<Clash-data-dir>" --restore "<manifest-path>"
```

```bash
python -I "<skill-dir>/scripts/install.py" --clash-dir "<Clash-data-dir>" --restore "<manifest-path>" --apply
```

只接受目标一致且哈希校验通过的备份。若安装后脚本被修改，回滚会拒绝覆盖，交由用户人工比较。回滚后同样需在 Clash 中重新应用配置。

## 默认策略

| 参数 | 默认 |
|---|---|
| 最高可识别倍率 | 1；代码不允许上限高于 1 |
| 未标倍率 | 保留，可选排除 |
| 首选国家 | JP；缺失时默认 REJECT，用户可手选其他现有国家 |
| 排序 | JP、US、SG、GB、HK、TW，然后其他地区 |
| 测速 | `https://www.gstatic.com/generate_204`；300 秒；50ms 容差 |
| 适用范围 | 所有经过全局扩展处理的当前订阅；不合并多个订阅的节点 |
| 无合格节点 | 不显示空国家组，不以高倍率节点或 DIRECT 兜底 |

原有分组与规则保留，新增规则置顶，因此会改变 OpenAI/ChatGPT 匹配优先级。名称冲突时明确拒绝，不删除用户已有同名组。支持 249 个 ISO 3166-1 国家/地区代码及 XK 预设，不把它们称为 250 个主权国家。

## 发布与分享

公开内容仅限本技能的源码、说明、国家表和虚构测试。不得附带真实订阅地址、token、代理认证、节点配置、控制器 secret、运行时 YAML、备份、本机日志、截图或用户专用路径。不要将本地 Clash 数据目录整体提交到仓库。
