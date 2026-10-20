const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assets = path.resolve(__dirname, '../assets');
const countries = JSON.parse(fs.readFileSync(path.join(assets, 'countries.json'), 'utf8'));
if (countries.length !== 250 || new Set(countries.map(row => row[0])).size !== 250 || countries.some(row => row.length !== 3 || !/^[A-Z]{2}$/.test(row[0]) || !row[1] || !row[2])) {
  throw new Error('Expected 250 unique country/region rows');
}
const template = fs.readFileSync(path.join(assets, 'global-script.template.js'), 'utf8');
if (template.split('__COUNTRIES__').length !== 2) throw new Error('Expected one country data placeholder');
const source = template.replace('__COUNTRIES__', JSON.stringify(countries));
const target = path.join(assets, 'global-script.js');
if (process.argv.includes('--check')) {
  if (fs.readFileSync(target, 'utf8') !== source) throw new Error('Generated script is stale; run build.cjs');
  console.log('Generated asset matches template and country table');
} else {
  fs.writeFileSync(target, source);
  console.log('Built global script:', crypto.createHash('sha256').update(source).digest('hex'));
}
