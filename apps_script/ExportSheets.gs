/**
 * Export for games: writes every sheet tab listed in export_manifest.json as
 * "<spreadsheet> - <tab>.csv" into the Drive folder Design/exports, validates every
 * Tag cell against validation_rules.json, and sends a summary by email and Slack.
 * Drive for desktop mirrors the folder to each machine; tools/import_data.py
 * (game-design repo) turns the CSVs into design/data JSON.
 *
 * Standalone script (not bound to one spreadsheet). Setup: DATA_PIPELINE.md (game-design root).
 * Script properties:
 *   DESIGN_FOLDER_ID   the Drive id of ".../Surviving the Grey Legend/Design" (required)
 *   NOTIFY_EMAILS      comma-separated addresses for the summary (default: the script owner)
 *   SLACK_WEBHOOK_URL  a Slack incoming-webhook URL (optional)
 *   NOTIFY_WARNINGS    "true" = also notify when there are only warnings (default: errors only)
 *
 * The validation is a port of tools/sheet_rules.py: keep the two in step.
 */

var EXPORTS_FOLDER_NAME = 'exports';
var MANIFEST_NAME = 'export_manifest.json';
var RULES_NAME = 'validation_rules.json';
var LOG_NAME = 'export_log.json';
var CONVERSION_NAME = 'conversion_preview.json';

/** Exports and validates every tab in the manifest. Run from the editor, the web app link, or the timer. */
function exportAll() {
  var ctx = context_();
  var written = [];
  var problems = [];
  var exportProblems = [];

  eachTab_(ctx, exportProblems, function (sheetName, values) {
    writeFile_(ctx.exportsFolder, sheetName + '.csv', toCsv_(values));
    written.push(sheetName + '.csv');
    problems = problems.concat(validateRows_(sheetName, values[0], values.slice(1), ctx.reg, ctx.rules));
  });
  exportProblems.forEach(function (message) {
    problems.push({sheet: '(export)', cell: '', value: '', level: 'error', message: message});
  });

  var errors = problems.filter(function (p) { return p.level === 'error'; });
  var nameWarnings = problems.filter(function (p) { return p.level === 'warning' && /^display name/.test(p.message); });
  var otherWarnings = problems.filter(function (p) { return p.level === 'warning' && !/^display name/.test(p.message); });
  var log = {exportedAt: new Date().toISOString(), by: Session.getEffectiveUser().getEmail(), files: written,
             strict: ctx.rules.strict, errors: errors.length, warnings: nameWarnings.length + otherWarnings.length,
             problems: exportProblems, validation: errors.concat(otherWarnings).slice(0, 200)};
  writeFile_(ctx.exportsFolder, LOG_NAME, JSON.stringify(log, null, 2));
  notify_(log, errors, nameWarnings, otherWarnings);
  if (exportProblems.length) {
    throw new Error('Export finished with problems:\n' + exportProblems.join('\n'));
  }
  return log;
}

/** Web app entry: open the deployment URL to export now. */
function doGet() {
  var log;
  try {
    log = exportAll();
  } catch (e) {
    return HtmlService.createHtmlOutput('<pre>' + e.message + '</pre>');
  }
  return HtmlService.createHtmlOutput('<p>Exported ' + log.files.length + ' tabs at ' + log.exportedAt +
                                      '. Validation: ' + log.errors + ' errors, ' + log.warnings +
                                      ' warnings.</p><pre>' + log.files.join('\n') + '</pre>');
}

/** Run once: export + validate every day at 06:00 Helsinki time (Apps Script runs it within ~15 min). */
function installDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'exportAll') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('exportAll').timeBased().everyDays(1).atHour(6).nearMinute(0)
      .inTimezone('Europe/Helsinki').create();
}

/** Step 1 of the name->Tag conversion: lists every cell it would change, changes nothing.
 *  The list goes to the log, the email, and exports/conversion_preview.json. */
function previewConversion() {
  return convert_(false);
}

/** Step 2: rewrites the reference cells from display names to Tags (after you checked the preview).
 *  Identity columns (BuildingName, Work, Name, Activity) are never touched. Formula cells are skipped. */
function applyConversion() {
  return convert_(true);
}

// ---- conversion -------------------------------------------------------------

function convert_(apply) {
  var ctx = context_();
  var changes = [];
  var exportProblems = [];
  eachTab_(ctx, exportProblems, function (sheetName, values, sheet) {
    var header = values[0];
    var rows = values.slice(1).map(function (r) { return r.slice(); });
    var tabChanges = convertRows_(sheetName, header, rows, ctx.reg);
    if (!tabChanges.length) return;
    var formulas = sheet.getDataRange().getFormulas();
    tabChanges.forEach(function (c) {
      c.sheet = sheetName;
      if (formulas[c.row - 1][c.col]) {
        c.skipped = 'formula';
      } else if (apply) {
        sheet.getRange(c.row, c.col + 1).setValue(c['new']);
      }
      changes.push(c);
    });
  });
  var report = {at: new Date().toISOString(), applied: apply, count: changes.length,
                changes: changes.map(function (c) {
                  return {sheet: c.sheet, cell: c.cell, old: c.old, 'new': c['new'], skipped: c.skipped || null};
                })};
  writeFile_(ctx.exportsFolder, CONVERSION_NAME, JSON.stringify(report, null, 2));
  var lines = changes.slice(0, 300).map(function (c) {
    return c.sheet + ' ' + c.cell + ': ' + c.old + '  ->  ' + c['new'] + (c.skipped ? '  (skipped: ' + c.skipped + ')' : '');
  });
  var title = (apply ? 'Converted ' : 'Conversion preview: ') + changes.length + ' cells to Tags';
  Logger.log(title + '\n' + lines.join('\n'));
  MailApp.sendEmail(notifyEmails_(), '[Export for games] ' + title,
                    title + (changes.length > 300 ? ' (first 300 shown; all in exports/' + CONVERSION_NAME + ')' : '') +
                    '\n\n' + lines.join('\n'));
  return report;
}

function convertCell_(value, rule, reg) {
  function tagOf(name) {
    var m = match_(reg, rule.kinds, name.trim());
    return m.how ? m.tag : name.trim();
  }
  if (rule.format === 'single') return tagOf(value);
  if (rule.format === 'outcome') {
    var o = /^(\d+)\s+(.+)$/.exec(value);
    return o ? o[1] + ' ' + tagOf(o[2]) : value;
  }
  var items = splitList_(value);
  if (rule.format === 'list') return items.map(tagOf).join(', ');
  return items.map(function (item) {  // quantities
    var q = /^(.*?)\s+(\d+)$/.exec(item);
    return q ? tagOf(q[1]) + ' ' + q[2] : tagOf(item);
  }).join(', ');
}

function convertRows_(sheetName, header, rows, reg) {
  var changes = [];
  forEachRuleCell_(sheetName, header, rows, function (rule, col, rowIndex, value) {
    if (rule.role !== 'ref') return;
    var converted = convertCell_(value, rule, reg);
    if (converted !== value) {
      changes.push({cell: a1_(col, rowIndex + 2), row: rowIndex + 2, col: col, old: value, 'new': converted});
    }
  });
  return changes;
}

// ---- validation (port of tools/sheet_rules.py) ------------------------------

function validateRows_(sheetName, header, rows, reg, rules) {
  var sheetRules = rules.sheets[sheetName];
  if (!sheetRules) return [];
  var problems = [];
  function add(level, col, row, value, message) {
    problems.push({sheet: sheetName, cell: a1_(col, row), value: value, level: level, message: message});
  }
  var headerKinds = sheetRules.header_kinds || {};
  header.forEach(function (title, col) {
    Object.keys(headerKinds).forEach(function (prefix) {
      if (title.indexOf(prefix) === 0) {
        var tag = title.substring(prefix.length);
        if (match_(reg, [headerKinds[prefix]], tag).how !== 'tag') {
          add(sheetRules.header_level || 'error', col, 1, title, 'header: ' + tag + ' is not a ' + headerKinds[prefix] + ' Tag');
        }
      }
    });
  });
  Object.keys(sheetRules.columns).forEach(function (title) {
    if (header.indexOf(title) < 0) add('error', 0, 1, title, 'column "' + title + '" is missing');
  });
  forEachRuleCell_(sheetName, header, rows, function (rule, col, rowIndex, value) {
    var parsed = parts_(value, rule.format);
    parsed.problems.forEach(function (m) { add('error', col, rowIndex + 2, value, m); });
    parsed.names.forEach(function (name) {
      var m = match_(reg, rule.kinds, name);
      if (!m.how) {
        add('error', col, rowIndex + 2, name, '"' + name + '" is not a known ' + rule.kinds.join('/'));
      } else if (m.how === 'name' && rule.role === 'ref') {
        add(rules.strict ? 'error' : 'warning', col, rowIndex + 2, name, 'display name: use the Tag ' + m.tag);
      }
    });
  });
  return problems;
}

/** Calls fn(rule, col, rowIndex, value) for every non-empty cell a rule applies to (skip_blank, when, except). */
function forEachRuleCell_(sheetName, header, rows, fn) {
  var rules = RULES_.sheets[sheetName];
  if (!rules) return;
  var skip = rules.skip_blank ? header.indexOf(rules.skip_blank) : -1;
  var typeCol = header.indexOf('Type');
  Object.keys(rules.columns).forEach(function (title) {
    var rule = rules.columns[title];
    var col = header.indexOf(title);
    if (col < 0) return;
    rows.forEach(function (row, i) {
      var cell = function (c) { return c >= 0 && c < row.length ? String(row[c]).trim() : ''; };
      var value = cell(col);
      if (!value) return;
      if (skip >= 0 && !cell(skip)) return;
      if (rule.when && rule.when.indexOf(cell(typeCol)) < 0) return;
      if ((rule['except'] || []).indexOf(value) >= 0) return;
      if (rule.kinds.length === 1 && rule.kinds[0] === 'Stat' && value.toLowerCase() === 'none') return;
      fn(rule, col, i, value);
    });
  });
}

function parts_(value, format) {
  if (format === 'single') return {names: [value], problems: []};
  if (format === 'outcome') {
    var o = /^(\d+)\s+(.+)$/.exec(value);
    return o ? {names: [o[2]], problems: []} : {names: [], problems: ['"' + value + '" is not "<quantity> <item>"']};
  }
  var items = splitList_(value);
  if (format === 'list') return {names: items, problems: []};
  var names = [], pending = [];
  items.forEach(function (item) {  // quantities
    var q = /^(.*?)\s+(\d+)$/.exec(item);
    if (!q) { pending.push(item); return; }
    names = names.concat(pending, [q[1]]);
    pending = [];
  });
  return {names: names, problems: pending.length ? ['"' + value + '": no quantity after ' + pending.join(', ')] : []};
}

function registries_(kinds) {
  var reg = {byTag: {}, byName: {}};
  Object.keys(kinds).forEach(function (kind) {
    reg.byTag[kind] = {};
    reg.byName[kind] = {};
    kinds[kind].forEach(function (e) {
      reg.byTag[kind][e.Tag] = true;
      [e.Name].concat(e.Aliases || []).forEach(function (name) {
        var key = norm_(name);
        if (!(key in reg.byName[kind])) reg.byName[kind][key] = e.Tag;
      });
    });
  });
  return reg;
}

function match_(reg, kinds, value) {
  for (var i = 0; i < kinds.length; i++) {
    if (reg.byTag[kinds[i]] && reg.byTag[kinds[i]][value]) return {how: 'tag', tag: value};
  }
  for (var j = 0; j < kinds.length; j++) {
    var tag = reg.byName[kinds[j]] && reg.byName[kinds[j]][norm_(value)];
    if (tag) return {how: 'name', tag: tag};
  }
  return {how: null, tag: null};
}

function norm_(text) { return String(text).toLowerCase().replace(/[^a-z0-9]/g, ''); }

function splitList_(value) {
  return value.split(',').map(function (p) { return p.trim(); }).filter(function (p) { return p; });
}

function a1_(col, row) {
  var letters = '';
  col += 1;
  while (col > 0) {
    var rem = (col - 1) % 26;
    letters = String.fromCharCode(65 + rem) + letters;
    col = Math.floor((col - 1) / 26);
  }
  return letters + row;
}

// ---- notifications ----------------------------------------------------------

function notify_(log, errors, nameWarnings, otherWarnings) {
  var props = PropertiesService.getScriptProperties();
  var warningsOnly = !errors.length && (nameWarnings.length || otherWarnings.length);
  if (!errors.length && !log.problems.length && !(warningsOnly && props.getProperty('NOTIFY_WARNINGS') === 'true')) {
    return;
  }
  var status = errors.length ? errors.length + ' errors' : 'no errors';
  var title = '[Export for games] ' + log.files.length + ' tabs exported, ' + status + ', ' +
              (nameWarnings.length + otherWarnings.length) + ' warnings';
  var lines = errors.concat(otherWarnings).slice(0, 40).map(function (p) {
    return (p.level === 'error' ? 'ERROR ' : 'warning ') + p.sheet + ' ' + p.cell + ': ' + p.message;
  });
  if (nameWarnings.length) {
    lines.push(nameWarnings.length + ' cells still hold a display name where a Tag belongs' +
               (log.strict ? '' : ' (warnings until strict_tags is on; run previewConversion / applyConversion)'));
  }
  var body = lines.join('\n') + '\n\nFull list: Design/exports/' + LOG_NAME;

  MailApp.sendEmail(notifyEmails_(), title, body);
  var webhook = props.getProperty('SLACK_WEBHOOK_URL');
  if (webhook) {
    UrlFetchApp.fetch(webhook, {method: 'post', contentType: 'application/json',
                                payload: JSON.stringify({text: '*' + title + '*\n```' + body + '```'})});
  }
}

function notifyEmails_() {
  return PropertiesService.getScriptProperties().getProperty('NOTIFY_EMAILS') || Session.getEffectiveUser().getEmail();
}

// ---- Drive / sheets plumbing ------------------------------------------------

var RULES_ = null;

function context_() {
  var design = DriveApp.getFolderById(designFolderId_());
  var exportsFolder = childFolder_(design, EXPORTS_FOLDER_NAME);
  var rules = readJson_(exportsFolder, RULES_NAME);
  RULES_ = rules;
  return {design: design, exportsFolder: exportsFolder, manifest: readJson_(exportsFolder, MANIFEST_NAME),
          rules: rules, reg: registries_(rules.kinds), books: {}};
}

/** Calls fn(sheetName, displayValues, sheet) for every manifest tab; problems collects what was not found. */
function eachTab_(ctx, problems, fn) {
  ctx.manifest.exports.forEach(function (entry) {
    var book = ctx.books[entry.spreadsheet];
    if (book === undefined) {
      book = ctx.books[entry.spreadsheet] = findSpreadsheet_(ctx.design, entry.spreadsheet);
    }
    if (!book) {
      problems.push('spreadsheet not found under Design: ' + entry.spreadsheet);
      return;
    }
    var sheet = book.getSheetByName(entry.tab);
    if (!sheet) {
      problems.push('tab not found: ' + entry.spreadsheet + ' / ' + entry.tab);
      return;
    }
    fn(entry.spreadsheet + ' - ' + entry.tab, sheet.getDataRange().getDisplayValues(), sheet);
  });
}

function designFolderId_() {
  var id = PropertiesService.getScriptProperties().getProperty('DESIGN_FOLDER_ID');
  if (!id) throw new Error('Set the script property DESIGN_FOLDER_ID (see DATA_PIPELINE.md).');
  return id;
}

function childFolder_(parent, name) {
  var it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}

function readJson_(folder, name) {
  var it = folder.getFilesByName(name);
  if (!it.hasNext()) {
    throw new Error(name + ' is missing from Design/exports. Run `python tools/import_data.py ' +
                    '--publish-manifest` in game-design (it writes ' + MANIFEST_NAME + ' and ' + RULES_NAME + ').');
  }
  return JSON.parse(it.next().getBlob().getDataAsString('UTF-8'));
}

/** Finds a Google Sheet by exact title anywhere under the Design folder (skips exports/). */
function findSpreadsheet_(folder, title) {
  var files = folder.getFilesByName(title);
  while (files.hasNext()) {
    var f = files.next();
    if (f.getMimeType() === MimeType.GOOGLE_SHEETS) return SpreadsheetApp.openById(f.getId());
  }
  var subs = folder.getFolders();
  while (subs.hasNext()) {
    var sub = subs.next();
    if (sub.getName() === EXPORTS_FOLDER_NAME) continue;
    var found = findSpreadsheet_(sub, title);
    if (found) return found;
  }
  return null;
}

/** Same quoting as Sheets' File > Download > CSV: quote fields with , " or newlines. */
function toCsv_(rows) {
  return rows.map(function (row) {
    return row.map(function (cell) {
      var s = String(cell);
      return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    }).join(',');
  }).join('\r\n');
}

/** Overwrites in place (keeps the file id, so Drive for desktop syncs an update, not a new file). */
function writeFile_(folder, name, content) {
  var it = folder.getFilesByName(name);
  if (it.hasNext()) {
    it.next().setContent(content);
  } else {
    folder.createFile(name, content, MimeType.CSV);
  }
}
