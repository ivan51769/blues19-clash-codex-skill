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
const CODEX_COUNTRIES = [["AD","安道尔","Andorra"],["AE","阿联酋","United Arab Emirates"],["AF","阿富汗","Afghanistan"],["AG","安提瓜和巴布达","Antigua & Barbuda"],["AI","安圭拉","Anguilla"],["AL","阿尔巴尼亚","Albania"],["AM","亚美尼亚","Armenia"],["AO","安哥拉","Angola"],["AQ","南极洲","Antarctica"],["AR","阿根廷","Argentina"],["AS","美属萨摩亚","American Samoa"],["AT","奥地利","Austria"],["AU","澳大利亚","Australia"],["AW","阿鲁巴","Aruba"],["AX","奥兰群岛","Åland Islands"],["AZ","阿塞拜疆","Azerbaijan"],["BA","波斯尼亚和黑塞哥维那","Bosnia & Herzegovina"],["BB","巴巴多斯","Barbados"],["BD","孟加拉国","Bangladesh"],["BE","比利时","Belgium"],["BF","布基纳法索","Burkina Faso"],["BG","保加利亚","Bulgaria"],["BH","巴林","Bahrain"],["BI","布隆迪","Burundi"],["BJ","贝宁","Benin"],["BL","圣巴泰勒米","St. Barthélemy"],["BM","百慕大","Bermuda"],["BN","文莱","Brunei"],["BO","玻利维亚","Bolivia"],["BQ","荷属加勒比区","Caribbean Netherlands"],["BR","巴西","Brazil"],["BS","巴哈马","Bahamas"],["BT","不丹","Bhutan"],["BV","布韦岛","Bouvet Island"],["BW","博茨瓦纳","Botswana"],["BY","白俄罗斯","Belarus"],["BZ","伯利兹","Belize"],["CA","加拿大","Canada"],["CC","科科斯（基林）群岛","Cocos (Keeling) Islands"],["CD","刚果（金）","Congo - Kinshasa"],["CF","中非共和国","Central African Republic"],["CG","刚果（布）","Congo - Brazzaville"],["CH","瑞士","Switzerland"],["CI","科特迪瓦","Côte d’Ivoire"],["CK","库克群岛","Cook Islands"],["CL","智利","Chile"],["CM","喀麦隆","Cameroon"],["CN","中国","China"],["CO","哥伦比亚","Colombia"],["CR","哥斯达黎加","Costa Rica"],["CU","古巴","Cuba"],["CV","佛得角","Cape Verde"],["CW","库拉索","Curaçao"],["CX","圣诞岛","Christmas Island"],["CY","塞浦路斯","Cyprus"],["CZ","捷克","Czechia"],["DE","德国","Germany"],["DJ","吉布提","Djibouti"],["DK","丹麦","Denmark"],["DM","多米尼克","Dominica"],["DO","多米尼加共和国","Dominican Republic"],["DZ","阿尔及利亚","Algeria"],["EC","厄瓜多尔","Ecuador"],["EE","爱沙尼亚","Estonia"],["EG","埃及","Egypt"],["EH","西撒哈拉","Western Sahara"],["ER","厄立特里亚","Eritrea"],["ES","西班牙","Spain"],["ET","埃塞俄比亚","Ethiopia"],["FI","芬兰","Finland"],["FJ","斐济","Fiji"],["FK","福克兰群岛","Falkland Islands"],["FM","密克罗尼西亚","Micronesia"],["FO","法罗群岛","Faroe Islands"],["FR","法国","France"],["GA","加蓬","Gabon"],["GB","英国","United Kingdom"],["GD","格林纳达","Grenada"],["GE","格鲁吉亚","Georgia"],["GF","法属圭亚那","French Guiana"],["GG","根西岛","Guernsey"],["GH","加纳","Ghana"],["GI","直布罗陀","Gibraltar"],["GL","格陵兰","Greenland"],["GM","冈比亚","Gambia"],["GN","几内亚","Guinea"],["GP","瓜德罗普","Guadeloupe"],["GQ","赤道几内亚","Equatorial Guinea"],["GR","希腊","Greece"],["GS","南乔治亚和南桑威奇群岛","South Georgia & South Sandwich Islands"],["GT","危地马拉","Guatemala"],["GU","关岛","Guam"],["GW","几内亚比绍","Guinea-Bissau"],["GY","圭亚那","Guyana"],["HK","香港","Hong Kong SAR China"],["HM","赫德岛和麦克唐纳群岛","Heard & McDonald Islands"],["HN","洪都拉斯","Honduras"],["HR","克罗地亚","Croatia"],["HT","海地","Haiti"],["HU","匈牙利","Hungary"],["ID","印度尼西亚","Indonesia"],["IE","爱尔兰","Ireland"],["IL","以色列","Israel"],["IM","马恩岛","Isle of Man"],["IN","印度","India"],["IO","英属印度洋领地","British Indian Ocean Territory"],["IQ","伊拉克","Iraq"],["IR","伊朗","Iran"],["IS","冰岛","Iceland"],["IT","意大利","Italy"],["JE","泽西岛","Jersey"],["JM","牙买加","Jamaica"],["JO","约旦","Jordan"],["JP","日本","Japan"],["KE","肯尼亚","Kenya"],["KG","吉尔吉斯斯坦","Kyrgyzstan"],["KH","柬埔寨","Cambodia"],["KI","基里巴斯","Kiribati"],["KM","科摩罗","Comoros"],["KN","圣基茨和尼维斯","St. Kitts & Nevis"],["KP","朝鲜","North Korea"],["KR","韩国","South Korea"],["KW","科威特","Kuwait"],["KY","开曼群岛","Cayman Islands"],["KZ","哈萨克斯坦","Kazakhstan"],["LA","老挝","Laos"],["LB","黎巴嫩","Lebanon"],["LC","圣卢西亚","St. Lucia"],["LI","列支敦士登","Liechtenstein"],["LK","斯里兰卡","Sri Lanka"],["LR","利比里亚","Liberia"],["LS","莱索托","Lesotho"],["LT","立陶宛","Lithuania"],["LU","卢森堡","Luxembourg"],["LV","拉脱维亚","Latvia"],["LY","利比亚","Libya"],["MA","摩洛哥","Morocco"],["MC","摩纳哥","Monaco"],["MD","摩尔多瓦","Moldova"],["ME","黑山","Montenegro"],["MF","法属圣马丁","St. Martin"],["MG","马达加斯加","Madagascar"],["MH","马绍尔群岛","Marshall Islands"],["MK","北马其顿","North Macedonia"],["ML","马里","Mali"],["MM","缅甸","Myanmar (Burma)"],["MN","蒙古","Mongolia"],["MO","澳门","Macao SAR China"],["MP","北马里亚纳群岛","Northern Mariana Islands"],["MQ","马提尼克","Martinique"],["MR","毛里塔尼亚","Mauritania"],["MS","蒙特塞拉特","Montserrat"],["MT","马耳他","Malta"],["MU","毛里求斯","Mauritius"],["MV","马尔代夫","Maldives"],["MW","马拉维","Malawi"],["MX","墨西哥","Mexico"],["MY","马来西亚","Malaysia"],["MZ","莫桑比克","Mozambique"],["NA","纳米比亚","Namibia"],["NC","新喀里多尼亚","New Caledonia"],["NE","尼日尔","Niger"],["NF","诺福克岛","Norfolk Island"],["NG","尼日利亚","Nigeria"],["NI","尼加拉瓜","Nicaragua"],["NL","荷兰","Netherlands"],["NO","挪威","Norway"],["NP","尼泊尔","Nepal"],["NR","瑙鲁","Nauru"],["NU","纽埃","Niue"],["NZ","新西兰","New Zealand"],["OM","阿曼","Oman"],["PA","巴拿马","Panama"],["PE","秘鲁","Peru"],["PF","法属波利尼西亚","French Polynesia"],["PG","巴布亚新几内亚","Papua New Guinea"],["PH","菲律宾","Philippines"],["PK","巴基斯坦","Pakistan"],["PL","波兰","Poland"],["PM","圣皮埃尔和密克隆群岛","St. Pierre & Miquelon"],["PN","皮特凯恩群岛","Pitcairn Islands"],["PR","波多黎各","Puerto Rico"],["PS","巴勒斯坦领土","Palestinian Territories"],["PT","葡萄牙","Portugal"],["PW","帕劳","Palau"],["PY","巴拉圭","Paraguay"],["QA","卡塔尔","Qatar"],["RE","留尼汪","Réunion"],["RO","罗马尼亚","Romania"],["RS","塞尔维亚","Serbia"],["RU","俄罗斯","Russia"],["RW","卢旺达","Rwanda"],["SA","沙特阿拉伯","Saudi Arabia"],["SB","所罗门群岛","Solomon Islands"],["SC","塞舌尔","Seychelles"],["SD","苏丹","Sudan"],["SE","瑞典","Sweden"],["SG","新加坡","Singapore"],["SH","圣赫勒拿","St. Helena"],["SI","斯洛文尼亚","Slovenia"],["SJ","斯瓦尔巴和扬马延","Svalbard & Jan Mayen"],["SK","斯洛伐克","Slovakia"],["SL","塞拉利昂","Sierra Leone"],["SM","圣马力诺","San Marino"],["SN","塞内加尔","Senegal"],["SO","索马里","Somalia"],["SR","苏里南","Suriname"],["SS","南苏丹","South Sudan"],["ST","圣多美和普林西比","São Tomé & Príncipe"],["SV","萨尔瓦多","El Salvador"],["SX","荷属圣马丁","Sint Maarten"],["SY","叙利亚","Syria"],["SZ","斯威士兰","Eswatini"],["TC","特克斯和凯科斯群岛","Turks & Caicos Islands"],["TD","乍得","Chad"],["TF","法属南部领地","French Southern Territories"],["TG","多哥","Togo"],["TH","泰国","Thailand"],["TJ","塔吉克斯坦","Tajikistan"],["TK","托克劳","Tokelau"],["TL","东帝汶","Timor-Leste"],["TM","土库曼斯坦","Turkmenistan"],["TN","突尼斯","Tunisia"],["TO","汤加","Tonga"],["TR","土耳其","Türkiye"],["TT","特立尼达和多巴哥","Trinidad & Tobago"],["TV","图瓦卢","Tuvalu"],["TW","台湾","Taiwan"],["TZ","坦桑尼亚","Tanzania"],["UA","乌克兰","Ukraine"],["UG","乌干达","Uganda"],["UM","美国本土外小岛屿","U.S. Outlying Islands"],["US","美国","United States"],["UY","乌拉圭","Uruguay"],["UZ","乌兹别克斯坦","Uzbekistan"],["VA","梵蒂冈","Vatican City"],["VC","圣文森特和格林纳丁斯","St. Vincent & Grenadines"],["VE","委内瑞拉","Venezuela"],["VG","英属维尔京群岛","British Virgin Islands"],["VI","美属维尔京群岛","U.S. Virgin Islands"],["VN","越南","Vietnam"],["VU","瓦努阿图","Vanuatu"],["WF","瓦利斯和富图纳","Wallis & Futuna"],["WS","萨摩亚","Samoa"],["YE","也门","Yemen"],["YT","马约特","Mayotte"],["ZA","南非","South Africa"],["ZM","赞比亚","Zambia"],["ZW","津巴布韦","Zimbabwe"],["XK","科索沃","Kosovo"]];
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
