# Clash Codex Optimizer · 公共技能

让 Codex/OpenAI 请求在 **Clash 规则模式**下按国家自动选择低延迟节点，并从这些自动组中排除名称标注 **超过 1 倍**的节点。

这是标准 `SKILL.md` 技能包，也可以不使用 AI 助手，直接将附带脚本安装到 Clash Verge 的全局扩展。没有模型 API、后台服务、账号采集、telemetry、权限提升或自动 TUN 设置。

## 功能

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

只安装一个客户端时，将 `both` 改为 `claude` 或 `codex`。工具不会改设置、权限或其他技能，遇到已存在的不同内容会拒绝覆盖。

新建会话后使用 `/clash-codex-optimizer`（以客户端的技能发现结果为准），或者说：

> 用 clash-codex-optimizer 检查 Codex 只有全局代理才能连接的问题；预设国家自动组，排除超过 1 倍节点，默认日本，先预览再应用。

技能安装与 Clash 配置安装是两件事；安装技能**不会自动修改网络配置**。

## 直接安装 Clash 全局扩展

1. 在 Clash Verge 中确认数据目录。Windows 常见位置是 `%APPDATA%/io.github.clash-verge-rev.clash-verge-rev`；其他平台从应用中打开配置目录确认。
2. 使用真实目录替换下面的 `<Clash-data-dir>`。命令从仓库根目录运行，默认只读。

```bash
python -I skills/clash-codex-optimizer/scripts/install.py --clash-dir "<Clash-data-dir>"
```

```bash
python -I skills/clash-codex-optimizer/scripts/install.py --clash-dir "<Clash-data-dir>" --apply
```

3. 在 Clash Verge 中重新应用当前订阅/全局扩展，并使用**规则模式**。
4. 在“代理”页面找到 **Codex 代理**，选择日本自动、美国自动、新加坡自动等组。
5. 在 Codex 中 Retry，验证工作区实际恢复。仅文件保存或 API 返回 401 不能证明登录与工作区正常。

安装工具**仅写 `profiles/Script.js`**，不读取订阅 YAML、不修改节点、模式、TUN、系统代理或运行时 YAML，也不会重启应用。它保护已有自定义脚本；如果拒绝安装，请人工审查并组合，不要删除原脚本来绕过保护。

请求必须先进入 Clash（例如客户端已正确使用本地代理）。仅增加 `PROCESS-NAME` 规则不能捕获本来绕过代理的直连请求。

### 回滚

应用结果会返回一个本地备份 manifest 路径。先预览：

```bash
python -I skills/clash-codex-optimizer/scripts/install.py --clash-dir "<Clash-data-dir>" --restore "<manifest-path>"
```

```bash
python -I skills/clash-codex-optimizer/scripts/install.py --clash-dir "<Clash-data-dir>" --restore "<manifest-path>" --apply
```

备份保存在 `profiles/.clash-codex-backups/`，**不要上传**。安装后脚本若被修改，回滚会拒绝覆盖，避免抹掉新修改。回滚后仍需让 Clash 重新应用配置。

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
- Python 工具拒绝 symlink/junction/reparse-point 路径；需要链接目录的用户请人工集成。
- 本项目不改变服务地区限制，不保证特定国家的节点可使用 OpenAI。

## 开发与测试

没有 npm 或 pip 依赖，安装用户不需要 Node.js。开发测试使用 Node.js 20+ 与 Python 3.10+。

```bash
npm test
```

测试覆盖倍率、250 个地区代码、排序、空组、原规则保留、幂等性、名称冲突、订阅变化，以及临时目录中的预览/应用/备份/回滚/并发修改保护。Windows 不具备创建符号链接权限时，相应测试会显式跳过。

仓库只包含代码、国家表、文档和虚构测试。**请勿提交订阅链接、token、节点密码、控制器 secret、运行时配置、备份、连接日志或用户专用路径。**

## 参考

- [Claude Code 技能文档](https://code.claude.com/docs/en/skills)
- [Codex 技能文档](https://developers.openai.com/codex/skills/)
- [Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)
- [Mihomo 代理组文档](https://wiki.metacubex.one/config/proxy-groups/)

国家名称表是冻结的公开地理名称数据，初始标签使用 Node.js `Intl.DisplayNames` 生成，附带常用中文展示名修正；构建时不访问互联网，也不根据构建机器重新翻译。

## License

[MIT](LICENSE)
