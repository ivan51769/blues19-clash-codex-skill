# Windows Store Codex：启动、规则分流与额度

此流程适用于 Windows 桌面版和正在本机运行的 Clash Verge Rev / Mihomo。**不需要全局模式、系统代理或 TUN，不等于不需要代理**；如果 OpenAI 端点可直连，不为联网而额外启用代理。

## 1. 区分本地启动与上游网络

- `Connection for host ID local not found` 表示桌面端没有可用的本地 App Server 连接，不是远程额度不足。[OpenAI #62722](https://github.com/openai/codex/issues/62722) 记录了快速重开的同类错误；它是诊断线索，不能替代本机证据。
- 用 `Get-AppxPackage OpenAI.Codex` 及其清单确认 Store/MSIX 入口；不要把 `codex.exe` CLI / App Server 或额度浮层当成桌面进程。确认 `chatgpt-desktop.exe` 执行别名可用。如果正在使用不同发行版，不强行套用本说明。
- 仅读必要的新日志/错误分类，核实是否出现本地初始化、HTTPS/代理错误；不要上传原日志、命令行、账号、浏览器档案或订阅。
- 从 Clash 设置中确认 `mixed-port` 或 HTTP 代理端口与 loopback 监听；不是 SOCKS-only、控制器端口或随便猜的默认端口。先做下列无凭据探测，替换示例端口（保持 TLS 校验）：

```powershell
curl.exe --head --max-time 8 --noproxy '*' https://chatgpt.com/
```

```powershell
curl.exe --head --max-time 8 --noproxy '' --proxy http://127.0.0.1:<PORT> https://chatgpt.com/
```

HTTP 有返回只证明抵达某个服务层；不把 HTTP 401/403、验证挑战或 CONNECT 成功当成账号、消息或额度通过。

## 2. 在当前订阅里补规则，不替换全局分流

1. 查实际运行模式、系统代理、TUN、当前订阅和可用代理组。如果在「规则」模式下已经正确路由 OpenAI，就不再加重复规则。
2. 选用户现有、已验证可用的组。如果需要修改，先备份**本次要改的订阅增强规则/脚本**并核对副本，保留既有规则的顺序与无关逻辑；不要编辑生成的运行时 YAML，也不要覆盖自定义全局扩展。
3. 通过当前订阅的规则增强置顶所需规则。把 `EXISTING_GROUP` 全部换成实际已有代理组名，不照抄占位符：

```text
DOMAIN-SUFFIX,chatgpt.com,EXISTING_GROUP
DOMAIN-SUFFIX,openai.com,EXISTING_GROUP
DOMAIN-SUFFIX,oaistatic.com,EXISTING_GROUP
DOMAIN-SUFFIX,oaiusercontent.com,EXISTING_GROUP
```

4. 在 Clash 中重新激活当前订阅，检查生成规则位于首条适用的兜底（如 `MATCH`）之前。若全局脚本随后把兜底插到前面，只在本人有权编辑时合并到该订阅的**最终脚本**，保留其他规则；有冲突或编辑会影响其他订阅时先停。四条规则只影响进入 Clash 的匹配域名流量，不限制调用进程；不改原有兜底、节点或其他订阅。
5. 使用「规则」模式，确保验证时系统代理和 TUN 均关闭。切换模式可能受「自动关闭连接」设置影响；存在其他业务连接时，先保留现场，不擅自断开。不要为使 Codex 可用而开启全局模式、系统代理或 TUN。

仅当规则增强最终排在兜底之后时，才使用下面的订阅脚本写法。已有 `main` 就合并规则逻辑，不覆盖其余内容。用实际存在的组名取代 `EXISTING_GROUP`：

```javascript
function main(config) {
  const group = 'EXISTING_GROUP';
  if (!(config['proxy-groups'] || []).some(item => item.name === group)) return config;
  const domains = ['chatgpt.com', 'openai.com', 'oaistatic.com', 'oaiusercontent.com'];
  const rules = domains.map(domain => `DOMAIN-SUFFIX,${domain},${group}`);
  config.rules = rules.concat((config.rules || []).filter(rule => !rules.includes(rule)));
  return config;
}
```

## 3. 只给 Store Codex 进程加代理

先把 [启动器](../assets/start-windows-store-codex.ps1) 复制到普通 PowerShell 和资源管理器都可访问的**可信本地用户目录**，避免从网盘/映射盘或临时下载目录直接执行。保留已存在的自定义文件或快捷方式，不降低系统执行策略；遇到签名/互联网来源提示先检查来源与组织策略。

从新建的 PowerShell 运行，替换脚本路径和端口：

```powershell
powershell.exe -NoProfile -File '<LOCAL_LAUNCHER_PATH>' -ProxyPort <PORT>
```

也可新建一个独立桌面快捷方式，目标为 Windows PowerShell 的本机完整路径，参数如下，原入口保持不动：

```text
-NoProfile -WindowStyle Hidden -File "<LOCAL_LAUNCHER_PATH>" -ProxyPort <PORT> -ShowErrorDialog
```

脚本每次解析当前 Store 包路径，不固定版本号。启动时为 Electron 设置 `--proxy-server`，为后端子进程设置 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`，`NO_PROXY` 只保留 loopback，并恢复当前调用进程环境。只接受本地端口；TCP 可连不表示该端口支持 HTTP 代理。脚本不会改注册表、Windows 系统代理、账号、权限、全局规则或安装目录。

- 已打开的窗口会被激活；短时间关闭/重开会先等待，确认旧进程退出或稳定驻留托盘后再继续。没有强制结束进程，也不保证能消除所有应用自身崩溃。
- **单实例规则：**如果已通过旧入口启动，带参数的启动可能只是把窗口唤回，不会给旧进程换代理。先保存工作，从应用/托盘菜单**退出**，等 Store 桌面进程结束，再用专用入口冷启动。关闭窗口不等于退出。

## 4. 分别验收启动、模型和额度

保持规则模式、系统代理与 TUN 关闭，Clash 后台运行。逐项记录通过或未验证：

| 项目 | 判断依据 |
|---|---|
| 桌面启动 | 从专用入口启动或重开实际桌面窗口，窗口可响应，本次没有相同弹窗；若只唤回旧进程，不算代理继承验证 |
| 规则与进程代理 | 确认新 Store 进程带 scoped 参数并且 OpenAI 域名实际命中目标组；查看本机连接，仅记录域名、规则和结果 |
| 模型可用 | 已授权的最小通用测试请求获得模型回复；区分桌面 GUI 与 CLI/后端实测。未授权发测试时不能以 HTTP 探测冒充对话成功 |
| 额度可用 | 同一已登录账号的应用用量页或已安装额度工具在测试窗口内显示新鲜额度；确认刷新/时间变化，不把旧缓存当实时，也不安装额外工具或读取/导出凭据去查额度 |

额度工具是不同进程。若 Codex 已通而额度不刷新，单独检查额度工具自己的代理路径与账号状态；不要断言 Store 启动器能替其他进程代理。不要更换账号、复制凭据到第三方、关闭证书校验或绕过地区/服务限制。

## 5. 回退

只移除本次新建的快捷方式和本机启动器副本；改了订阅增强时，先核对当前文件仍是本次写入的版本，再从备份恢复原规则并重新激活。若有后续用户编辑，逐项比较，不整份覆盖。只恢复本次改变的 Clash 模式/开关，不重置其他设置，不删除会话、缓存或登录。额度工具没有被修改就不处理。
