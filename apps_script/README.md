# Sheets export (Apps Script)

`ExportSheets.gs` writes every tab listed in `tools/export_manifest.json` to the Drive folder
`Games/Surviving the Grey Legend/Design/exports/` as `<spreadsheet> - <tab>.csv`. Drive for desktop
mirrors that folder to `G:\Shared drives\Games\Surviving the Grey Legend\Design\exports`, where
`tools/import_data.py` reads it.

## One-time setup (about 5 minutes)

1. Open https://script.google.com → **New project**, name it `Export for games`.
2. Replace `Code.gs` with the contents of `ExportSheets.gs`.
3. **Project Settings → Script properties → Add**: `DESIGN_FOLDER_ID` = the id of the Drive folder
   `Surviving the Grey Legend/Design` (the part after `/folders/` in its URL).
4. Put the manifest in Drive: from the game-design repo run `python tools/import_data.py --publish-manifest`
   (copies `tools/export_manifest.json` into the exports folder via `G:\`). The script creates
   `exports/` itself on the first run if it does not exist yet; in that case run step 4 after step 5.
5. In the editor run `exportAll` once and accept the permissions (Drive + Sheets, your account).
6. Optional:
   - run `installHourlyTrigger` to export every hour;
   - **Deploy → New deployment → Web app** (execute as: me, access: your organisation) and bookmark
     the URL: opening it exports immediately ("Export now" button for designers).

## Adding a tab

Add a row to `tools/export_manifest.json` (`spreadsheet` = exact sheet title, `tab` = exact tab name),
run `python tools/import_data.py --publish-manifest`, then add the converter for the new CSV.

## Checks

The script throws (and writes the problems to `exports/export_log.json`) if a spreadsheet or tab is
not found. `import_data.py` prints the `exportedAt` time from that log, so a stale export is visible.
