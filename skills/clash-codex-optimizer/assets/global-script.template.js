// Managed by blues19-clash-codex-skill
// Version: 1.0.0
// Global Clash Verge extension. No subscriptions, credentials or controller access.
const CODEX_OPTIONS = {
  maxMultiplier: 1,
  keepUnmarked: true,
  preferredCountry: "JP",
  countryPriority: ["JP", "US", "SG", "GB", "HK", "TW"],
  interval: 300,
  tolerance: 50,
  testUrl: "https://www.gstatic.com/generate_204",
  routeDomains: true,
  routeProcess: true
};

// Generated from the checked-in, versioned country table. Do not edit this line.
const CODEX_COUNTRIES = __COUNTRIES__;
const CODEX_STATE_KEY = "x-blues19-clash-codex";
const CODEX_ALIASES = {
  JP: ["日本", "东京", "大阪", "埼玉", "名古屋", "福冈", "Tokyo", "Osaka", "Saitama", "Nagoya", "Fukuoka"],
  US: ["美国", "美國", "洛杉矶", "洛杉磯", "硅谷", "西雅图", "纽约", "圣何塞", "Los Angeles", "Seattle", "New York", "San Jose", "Silicon Valley", "USA"],
  SG: ["新加坡", "狮城", "獅城"],
  HK: ["香港", "Hong Kong"],
  TW: ["台湾", "台灣", "台北", "新北", "Taiwan", "Taipei"],
  KR: ["韩国", "韓國", "首尔", "首爾", "South Korea", "Seoul"],
  GB: ["英国", "英國", "伦敦", "倫敦", "United Kingdom", "London", "UK"],
  DE: ["德国", "德國", "法兰克福", "Germany", "Frankfurt"],
  FR: ["法国", "法國", "巴黎", "France", "Paris"],
  CA: ["加拿大", "多伦多", "温哥华", "Canada", "Toronto", "Vancouver"],
  AU: ["澳大利亚", "澳洲", "悉尼", "墨尔本", "Australia", "Sydney", "Melbourne"],
  NL: ["荷兰", "荷蘭", "阿姆斯特丹", "Netherlands", "Amsterdam"],
  RU: ["俄罗斯", "俄羅斯", "莫斯科", "Russia", "Moscow"],
  MO: ["澳门", "澳門", "Macao", "Macau"],
  TR: ["土耳其", "Turkey", "Türkiye"],
  VN: ["越南", "Vietnam"],
  LA: ["老挝", "Laos"],
  IR: ["伊朗", "Iran"],
  CZ: ["捷克", "Czech", "Czechia"],
  AE: ["阿联酋", "阿聯酋", "迪拜", "Dubai", "UAE"],
  IN: ["印度", "孟买", "Mumbai", "India"],
  MY: ["马来西亚", "馬來西亞", "吉隆坡", "Malaysia", "Kuala Lumpur"],
  TH: ["泰国", "泰國", "曼谷", "Thailand", "Bangkok"]
};

function codexNormalized(name) {
  return typeof name.normalize === "function" ? name.normalize("NFKC") : name;
}

function codexEligible(proxy) {
  if (!proxy || typeof proxy.name !== "string" || !proxy.server) return false;
  if (["direct", "reject", "pass", "dns"].indexOf(String(proxy.type).toLowerCase()) !== -1) return false;
  const name = codexNormalized(proxy.name);
  if (/剩余|剩餘|流量[：:]|套餐|到期|过期|過期|重置|订阅|訂閱|官网|官網|公告|有效期|expire|traffic\s*left|remaining|reset\s*date/i.test(name)) return false;
  const values = [];
  const patterns = [
    /(\d+(?:\.\d+)?)\s*(?:倍|[x×✕](?![a-z0-9]))/gi,
    /(?:^|[^a-z0-9])[x×✕]\s*(\d+(?:\.\d+)?)(?![\d.])/gi,
    /(?:^|[^a-z])(?:倍率|流量倍率|倍速|multiplier|rate)\s*[:=]?\s*(\d+(?:\.\d+)?)/gi
  ];
  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(name)) !== null) values.push(Number(match[1]));
  }
  if (values.some(function (value) { return value > CODEX_OPTIONS.maxMultiplier; })) return false;
  return values.length > 0 || CODEX_OPTIONS.keepUnmarked;
}

function codexTextMatch(name, alias) {
  name = codexNormalized(name);
  alias = codexNormalized(alias);
  const lower = name.toLowerCase();
  const target = alias.toLowerCase();
  let from = 0;
  let index;
  while ((index = lower.indexOf(target, from)) !== -1) {
    if (/[^\x00-\x7f]/.test(alias)) return true;
    const before = index === 0 ? "" : name.charAt(index - 1);
    const after = name.charAt(index + alias.length);
    if (!/[a-z]/i.test(before) && !/[a-z]/i.test(after)) return true;
    from = index + 1;
  }
  return false;
}

function codexCountry(name) {
  name = codexNormalized(name);
  const flag = name.match(/[\uD83C][\uDDE6-\uDDFF][\uD83C][\uDDE6-\uDDFF]/);
  if (flag) {
    const code = String.fromCharCode(flag[0].codePointAt(0) - 0x1f1e6 + 65) +
      String.fromCharCode(flag[0].codePointAt(2) - 0x1f1e6 + 65);
    if (code === "CN") {
      for (const region of ["TW", "HK", "MO"]) {
        if (CODEX_ALIASES[region].some(function (alias) { return codexTextMatch(name, alias); })) return region;
      }
    }
    if (CODEX_COUNTRIES.some(function (country) { return country[0] === code; })) return code;
  }
  const matches = [];
  for (const country of CODEX_COUNTRIES) {
    const aliases = (CODEX_ALIASES[country[0]] || []).concat([country[1], country[2]]);
    for (const alias of aliases) {
      if (codexTextMatch(name, alias)) matches.push({ code: country[0], length: alias.length });
    }
  }
  matches.sort(function (a, b) { return b.length - a.length; });
  if (matches.length) return matches[0].code;
  const tokens = name.toUpperCase().match(/(?:^|[^A-Z0-9])([A-Z]{2})(?=$|[^A-Z])/g) || [];
  for (const token of tokens) {
    const cleaned = token.replace(/[^A-Z]/g, "");
    const found = cleaned === "UK" ? "GB" : cleaned;
    if (CODEX_COUNTRIES.some(function (country) { return country[0] === found; })) return found;
  }
  return "ZZ";
}

function codexStable(value) {
  if (Array.isArray(value)) return "[" + value.map(codexStable).join(",") + "]";
  if (value && typeof value === "object") {
    return "{" + Object.keys(value).sort().map(function (key) {
      return JSON.stringify(key) + ":" + codexStable(value[key]);
    }).join(",") + "}";
  }
  return JSON.stringify(value);
}

function codexValidate(config) {
  if (!config || typeof config !== "object" || Array.isArray(config)) throw new Error("Expected a Clash configuration object");
  for (const key of ["proxies", "proxy-groups", "rules"]) {
    if (config[key] !== undefined && !Array.isArray(config[key])) throw new Error("Expected array: " + key);
  }
  if (config["proxy-providers"] && Object.keys(config["proxy-providers"]).length && !(config.proxies || []).length) {
    throw new Error("Provider-only subscriptions are unsupported; use an inline-proxy subscription or manual integration");
  }
  if (!Number.isFinite(CODEX_OPTIONS.maxMultiplier) || CODEX_OPTIONS.maxMultiplier < 0 || CODEX_OPTIONS.maxMultiplier > 1) throw new Error("maxMultiplier must be between 0 and 1");
  if (typeof CODEX_OPTIONS.keepUnmarked !== "boolean") throw new Error("keepUnmarked must be boolean");
  if (!CODEX_COUNTRIES.some(function (country) { return country[0] === CODEX_OPTIONS.preferredCountry; })) throw new Error("Unknown preferred country code");
  if (!Array.isArray(CODEX_OPTIONS.countryPriority) || CODEX_OPTIONS.countryPriority.some(function (code) { return !CODEX_COUNTRIES.some(function (country) { return country[0] === code; }); })) throw new Error("Invalid countryPriority");
  if (!Number.isInteger(CODEX_OPTIONS.interval) || CODEX_OPTIONS.interval < 60 || !Number.isFinite(CODEX_OPTIONS.tolerance) || CODEX_OPTIONS.tolerance < 0) throw new Error("Invalid interval/tolerance");
  if (typeof CODEX_OPTIONS.testUrl !== "string" || !/^https:\/\//.test(CODEX_OPTIONS.testUrl)) throw new Error("testUrl must use HTTPS");
  if (typeof CODEX_OPTIONS.routeDomains !== "boolean" || typeof CODEX_OPTIONS.routeProcess !== "boolean") throw new Error("Routing flags must be boolean");
}

function main(config, profileName) {
  codexValidate(config);
  let groups = (config["proxy-groups"] || []).slice();
  let rules = (config.rules || []).slice();
  const previous = config[CODEX_STATE_KEY];
  if (previous !== undefined) {
    if (!previous || previous.owner !== "blues19-clash-codex-skill" || previous.version !== 1 || !Array.isArray(previous.groups) || !Array.isArray(previous.rules)) throw new Error("Unrecognized optimizer ownership metadata; refusing to overwrite");
    for (const owned of previous.groups) {
      const existing = groups.filter(function (group) { return group.name === owned.name; });
      if (existing.length !== 1 || codexStable(existing[0]) !== codexStable(owned)) throw new Error("Managed group changed; refusing to discard edits");
    }
    if (codexStable(rules.slice(0, previous.rules.length)) !== codexStable(previous.rules)) throw new Error("Managed rule prefix changed; refusing to discard edits");
    const ownedNames = previous.groups.map(function (group) { return group.name; });
    groups = groups.filter(function (group) { return ownedNames.indexOf(group.name) === -1; });
    rules = rules.slice(previous.rules.length);
  }
  if (rules.some(function (rule) { return typeof rule !== "string"; })) throw new Error("Rules must be strings");
  const occupied = Object.create(null);
  for (const entry of (config.proxies || []).concat(groups)) {
    if (!entry || typeof entry.name !== "string" || !entry.name || occupied[entry.name]) throw new Error("Missing or duplicate proxy/group name");
    occupied[entry.name] = true;
  }
  const byCountry = {};
  for (const proxy of config.proxies || []) {
    if (!codexEligible(proxy)) continue;
    const code = codexCountry(proxy.name);
    if (!byCountry[code]) byCountry[code] = [];
    byCountry[code].push(proxy.name);
  }
  const generated = [];
  const choices = [];
  const countries = CODEX_COUNTRIES.concat([["ZZ", "其他地区", "Other"]]);
  const priority = [CODEX_OPTIONS.preferredCountry].concat(CODEX_OPTIONS.countryPriority);
  countries.sort(function (a, b) {
    const ai = priority.indexOf(a[0]);
    const bi = priority.indexOf(b[0]);
    return (ai === -1 ? priority.length : ai) - (bi === -1 ? priority.length : bi);
  });
  for (const country of countries) {
    const nodes = byCountry[country[0]];
    if (!nodes || !nodes.length) continue;
    const name = country[1] + "自动";
    if (occupied[name]) throw new Error("Optimizer country group collides with an existing name; integrate manually");
    choices.push(name);
    generated.push({name: name, type: "url-test", proxies: nodes, url: CODEX_OPTIONS.testUrl, interval: CODEX_OPTIONS.interval, tolerance: CODEX_OPTIONS.tolerance, lazy: true});
  }
  if (occupied["Codex 代理"]) throw new Error("Codex selector collides with an existing name; integrate manually");
  // Never default to another country, high-rate node, or DIRECT when JP is missing.
  if (!byCountry[CODEX_OPTIONS.preferredCountry]) choices.unshift("REJECT");
  generated.unshift({name: "Codex 代理", type: "select", proxies: choices});
  const managedRules = [];
  if (CODEX_OPTIONS.routeDomains) {
    for (const domain of ["chatgpt.com", "openai.com", "oaistatic.com", "oaiusercontent.com"]) managedRules.push("DOMAIN-SUFFIX," + domain + ",Codex 代理");
  }
  if (CODEX_OPTIONS.routeProcess) managedRules.push("PROCESS-NAME,codex.exe,Codex 代理", "PROCESS-NAME,Codex.exe,Codex 代理");
  config["proxy-groups"] = generated.concat(groups);
  config.rules = managedRules.concat(rules);
  config[CODEX_STATE_KEY] = {owner: "blues19-clash-codex-skill", version: 1, groups: JSON.parse(JSON.stringify(generated)), rules: managedRules.slice()};
  return config;
}
