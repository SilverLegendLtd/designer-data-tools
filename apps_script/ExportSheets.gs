/**
 * Export for games: writes every sheet tab listed in export_manifest.json as
 * "<spreadsheet> - <tab>.csv" into the Drive folder Design/exports.
 * Drive for desktop mirrors that folder to each machine; tools/import_data.py
 * (game-design repo) turns the CSVs into design/data JSON.
 *
 * Standalone script (not bound to one spreadsheet). Setup: apps_script/README.md.
 * Script property DESIGN_FOLDER_ID = the Drive id of ".../Surviving the Grey Legend/Design".
 */

var EXPORTS_FOLDER_NAME = 'exports';
var MANIFEST_NAME = 'export_manifest.json';
var LOG_NAME = 'export_log.json';

/** Exports every tab in the manifest. Run from the editor, the web app link, or the timer. */
function exportAll() {
  var design = DriveApp.getFolderById(designFolderId_());
  var exportsFolder = childFolder_(design, EXPORTS_FOLDER_NAME);
  var manifest = readManifest_(exportsFolder);
  var spreadsheets = {};
  var written = [];
  var problems = [];

  manifest.exports.forEach(function (entry) {
    var book = spreadsheets[entry.spreadsheet];
    if (book === undefined) {
      book = spreadsheets[entry.spreadsheet] = findSpreadsheet_(design, entry.spreadsheet);
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
    var name = entry.spreadsheet + ' - ' + entry.tab + '.csv';
    writeFile_(exportsFolder, name, toCsv_(sheet.getDataRange().getDisplayValues()));
    written.push(name);
  });

  var log = {exportedAt: new Date().toISOString(), by: Session.getActiveUser().getEmail(),
             files: written, problems: problems};
  writeFile_(exportsFolder, LOG_NAME, JSON.stringify(log, null, 2));
  if (problems.length) {
    throw new Error('Export finished with problems:\n' + problems.join('\n'));
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
                                      '.</p><pre>' + log.files.join('\n') + '</pre>');
}

/** Run once to export every hour as well. */
function installHourlyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'exportAll') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('exportAll').timeBased().everyHours(1).create();
}

function designFolderId_() {
  var id = PropertiesService.getScriptProperties().getProperty('DESIGN_FOLDER_ID');
  if (!id) throw new Error('Set the script property DESIGN_FOLDER_ID (see README).');
  return id;
}

function childFolder_(parent, name) {
  var it = parent.getFoldersByName(name);
  return it.hasNext() ? it.next() : parent.createFolder(name);
}

function readManifest_(exportsFolder) {
  var it = exportsFolder.getFilesByName(MANIFEST_NAME);
  if (!it.hasNext()) {
    throw new Error(MANIFEST_NAME + ' is missing from Design/exports. Run `python tools/import_data.py ' +
                    '--publish-manifest` in game-design, or upload tools/export_manifest.json there.');
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
