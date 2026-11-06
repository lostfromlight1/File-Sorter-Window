# Implementation tracker

Check an item when that feature or phase is finished. The agent updates this file and does not commit. You commit, so the author stays your git identity.

## Setup

- [x] V1 scope rule, move-safety rule, and project skill
- [x] Tracker and the commit handoff rule

## Next plan

- [x] Implementation plan for the preview window. No app code until that plan is accepted.

## V1 app

- [x] Project layout, pyproject, and a window that opens
- [x] JSON categories for the default folders
- [x] Scan top-level files and skip partial downloads and junk
- [x] Classify by extension, with Others as the fallback
- [x] Preview table with a checkbox on each row
- [x] Move only confirmed rows, keeping both files on a name clash
- [x] Undo log outside the sorted folder, and an Undo action
- [x] Tests on a temporary folder: partial download, subfolder left alone, name clash, and undo

## Review pass

- [x] Size and modified time on each scanned file
- [x] Category, size, and modified time on each preview row
- [x] Category checkboxes and a hide-skipped filter on the preview table
- [x] Move and Undo dialogs describe the files before acting
- [x] Tests for size, category, summaries, and the table filter

## Windows exe

- [x] Windowed FileSorter.exe with the category rules packed inside
- [x] Per-user setup exe with a Start menu shortcut and an uninstall entry

## Not in v1

Watching, tray, startup, subfolders, keyword rules, file contents, duplicates, photo dates, models, overwrite, and permanent delete.
