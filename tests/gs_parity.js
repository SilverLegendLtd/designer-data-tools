// Test helper (tests/test_sheet_rules.py): runs apps_script/ExportSheets.gs validation + conversion under Node.
const fs = require('fs'), path = require('path'), vm = require('vm');
const [gsPath, exportsDir] = process.argv.slice(2);
const ctx = {}; vm.createContext(ctx); vm.runInContext(fs.readFileSync(gsPath, 'utf8'), ctx);
function parseCsv(text) {  // RFC4180
  const rows = []; let row = [], f = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true; else if (c === ',') { row.push(f); f = ''; }
    else if (c === '\n' || c === '\r') { if (c === '\r' && text[i + 1] === '\n') i++; row.push(f); rows.push(row); row = []; f = ''; }
    else f += c;
  }
  if (f || row.length) { row.push(f); rows.push(row); }
  return rows;
}
const rules = JSON.parse(fs.readFileSync(path.join(exportsDir, 'validation_rules.json'), 'utf8'));
ctx.RULES_ = rules; const reg = ctx.registries_(rules.kinds);
const out = {};
for (const sheet of Object.keys(rules.sheets)) {
  const rows = parseCsv(fs.readFileSync(path.join(exportsDir, sheet + '.csv'), 'utf8').replace(/^\uFEFF/, ''));
  const p = ctx.validateRows_(sheet, rows[0], rows.slice(1), reg, rules);
  const c = ctx.convertRows_(sheet, rows[0], rows.slice(1).map(r => r.slice()), reg);
  out[sheet] = {errors: p.filter(x => x.level === 'error').length, warnings: p.filter(x => x.level === 'warning').length, conversions: c.length};
}
console.log(JSON.stringify(out));
