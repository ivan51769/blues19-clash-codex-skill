const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const skill = path.resolve(__dirname, '../skills/clash-codex-optimizer');
const source = fs.readFileSync(path.join(skill, 'assets/global-script.js'), 'utf8');
const countries = JSON.parse(fs.readFileSync(path.join(skill, 'assets/countries.json'), 'utf8'));
const plain = value => JSON.parse(JSON.stringify(value));
function engine(options = {}) {
  const sandbox = {};
  vm.createContext(sandbox);
  // Only the trusted bundled source is executed; vm is not a security boundary.
  vm.runInContext(source, sandbox, {timeout: 5000});
  for (const [key,value] of Object.entries(options)) vm.runInContext(`CODEX_OPTIONS[${JSON.stringify(key)}] = ${JSON.stringify(value)}`, sandbox);
  return sandbox;
}
function proxy(name) { return {name, type:'trojan', server:'example.invalid', port:443, password:'synthetic-placeholder'}; }
function fixture() {
  return {
    proxies: ['日本 0.5x', '日本 2x', '美国 1x', '新加坡 0.1x', '英国 0.5x', '香港 1x', '台湾 1x', '法国 1x', '套餐到期：长期有效'].map(proxy),
    'proxy-groups': [{name:'Original', type:'select', proxies:['日本 2x']}],
    rules: ['DOMAIN-SUFFIX,openai.com,Original', 'DOMAIN,example.invalid,DIRECT', 'MATCH,Original'],
    dns: {enable:true, nameserver:['https://dns.example.invalid/dns-query']}
  };
}
const passing = ['日本 0.1x', '日本 0.5倍', '日本 1x', '日本 x1', '日本 ×0.8', '日本 倍率:1', '日本 倍率：0.5', '日本 １ｘ', '日本 未标倍率', 'Japan 01|CTCU|0.5x', 'Japan Netflix4K', 'Japan 10Gbps'];
const failing = ['日本 1.01x', '日本 2倍', '日本 x3', '日本 ×5', '日本 倍率:2', '日本 倍率：1.5', '日本 ２ｘ', '日本 0.5x [2倍]', '日本 multiplier=2', '日本 rate:3', '剩余流量：999 GB', '套餐到期：长期有效'];
for (const name of passing) test(`eligible: ${name}`, () => assert.equal(engine().codexEligible(proxy(name)), true));
for (const name of failing) test(`excluded: ${name}`, () => assert.equal(engine().codexEligible(proxy(name)), false));
for (const [name, code] of [
  ['JP-01','JP'], ['JP01','JP'], ['Japan 02','JP'], ['东京01','JP'], ['香港01','HK'], ['Taiwan 01','TW'], ['美国洛杉矶01','US'], ['SG-01','SG'], ['🇩🇪香港中转 0.5x','DE'], ['UK-01','GB'], ['印度尼西亚01','ID'], ['白俄罗斯01','BY'], ['阿联酋01','AE'], ['🇨🇳台湾专线01','TW'], ['🇨🇳香港01','HK'], ['🇨🇳澳门01','MO'], ['Unlabeled relay 01','ZZ']
]) test(`country ${name}`, () => assert.equal(engine().codexCountry(name), code));
test('all 250 preset flags classify uniquely', () => {
  const e = engine();
  assert.equal(countries.length, 250);
  assert.equal(new Set(countries.map(row=>row[0])).size, 250);
  for (const [code] of countries) {
    const flag = [...code].map(c=>String.fromCodePoint(0x1f1e6+c.charCodeAt(0)-65)).join('');
    assert.equal(e.codexCountry(flag+' synthetic'), code, code);
  }
});
test('all bundled Chinese and English country labels classify correctly', () => {
  const e = engine();
  for (const [code, chinese, english] of countries) {
    assert.equal(e.codexCountry(chinese + ' synthetic 1x'), code, chinese);
    assert.equal(e.codexCountry(english + ' synthetic 1x'), code, english);
  }
});
test('repeated aliases inspect later word boundaries', () => assert.equal(engine().codexTextMatch('Tokyoish -> Tokyo', 'Tokyo'), true));
test('unmarked nodes are optional; DIRECT is never a node', () => {
  const e = engine({keepUnmarked:false});
  assert.equal(e.codexEligible(proxy('Japan plain')), false);
  assert.equal(e.codexEligible(proxy('Japan 0.5x')), true);
  assert.equal(e.codexEligible({name:'Japan 0.1x',type:'direct'}), false);
});
test('selector and country groups come first in requested order', () => {
  const output = plain(engine().main(fixture()));
  assert.deepEqual(output['proxy-groups'].slice(0,8).map(g=>g.name), ['Codex 代理','日本自动','美国自动','新加坡自动','英国自动','香港自动','台湾自动','法国自动']);
  assert.deepEqual(output['proxy-groups'][0].proxies, ['日本自动','美国自动','新加坡自动','英国自动','香港自动','台湾自动','法国自动']);
  assert.deepEqual(output['proxy-groups'][1].proxies, ['日本 0.5x']);
});
test('original groups, original rules and unrelated config remain unchanged', () => {
  const original = fixture();
  const before = plain(original);
  const result = plain(engine().main(original));
  assert.deepEqual(result['proxy-groups'].slice(-before['proxy-groups'].length), before['proxy-groups']);
  assert.deepEqual(result.rules.slice(6), before.rules);
  assert.deepEqual(result.proxies, before.proxies);
  assert.deepEqual(result.dns, before.dns);
  assert.equal(result.rules.filter(r=>r.startsWith('DOMAIN-SUFFIX,openai.com,')).length, 2);
});
test('repeat transform is idempotent', () => {
  const e = engine();
  const first = plain(e.main(fixture()));
  assert.deepEqual(plain(e.main(plain(first))), first);
});
test('managed groups removed when subscription node set changes', () => {
  const e = engine();
  const first = plain(e.main(fixture()));
  first.proxies = [proxy('美国 0.5x')];
  first['proxy-groups'].find(g=>g.name==='Original').proxies = ['美国 0.5x'];
  const changed = plain(e.main(first));
  assert.deepEqual(changed['proxy-groups'].map(g=>g.name), ['Codex 代理','美国自动','Original']);
  assert.deepEqual(changed['proxy-groups'][0].proxies, ['REJECT','美国自动']);
});
test('no eligible nodes and no JP default to REJECT, never DIRECT', () => {
  for (const proxies of [[], [proxy('日本 2x')], [proxy('美国 0.5x')]]) {
    const output = plain(engine().main({proxies}));
    assert.equal(output['proxy-groups'][0].proxies[0], 'REJECT');
    assert.equal(output['proxy-groups'][0].proxies.includes('DIRECT'), false);
  }
});
test('new preferred country is first', () => {
  const output = plain(engine({preferredCountry:'US'}).main(fixture()));
  assert.equal(output['proxy-groups'][0].proxies[0], '美国自动');
});
test('country group and selector collisions refuse without deleting originals', () => {
  for (const name of ['日本自动','Codex 代理']) {
    const input = fixture();
    input['proxy-groups'].push({name,type:'select',proxies:['日本 2x']});
    const before = plain(input);
    assert.throws(()=>engine().main(input), /collid/);
    assert.deepEqual(input,before);
  }
});
test('collision with proxy name also refuses', () => {
  const input = fixture();
  input.proxies.push(proxy('日本自动'));
  assert.throws(()=>engine().main(input), /collid/);
});
test('edited managed group or rule prefix refuses to discard edits', () => {
  const e = engine();
  const input = plain(e.main(fixture()));
  input['proxy-groups'][1].tolerance = 123;
  assert.throws(()=>e.main(input), /changed/);
  const next = plain(e.main(fixture()));
  next.rules[0] = 'MATCH,DIRECT';
  assert.throws(()=>e.main(next), /changed/);
});
test('routing scopes may be disabled explicitly', () => {
  const input = fixture();
  const output = plain(engine({routeDomains:false,routeProcess:false}).main(input));
  assert.deepEqual(output.rules, fixture().rules);
});
test('provider-only, malformed and duplicate input fails explicitly', () => {
  assert.throws(()=>engine().main({'proxy-providers':{example:{type:'http'}}}), /Provider-only/);
  for (const input of [null, [], {proxies:{}}, {rules:[{}]}, {proxies:[proxy('same'),proxy('same')]}]) assert.throws(()=>engine().main(input));
  for (const options of [{maxMultiplier:2},{maxMultiplier:-1},{keepUnmarked:'yes'},{preferredCountry:'BAD'},{countryPriority:['BAD']},{interval:1},{tolerance:-1},{testUrl:'http://example.invalid'},{routeDomains:1}]) assert.throws(()=>engine(options).main(fixture()));
});
