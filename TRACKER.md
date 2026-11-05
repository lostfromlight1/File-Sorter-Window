# Implementation tracker

Check an item when that feature or phase is finished. The agent updates this file and does not commit. You commit, so the author stays your git identity.

## Setup

- [x] V1 scope rule, move-safety rule, and project skill
- [x] Tracker and the commit handoff rule

## Next plan

- [ ] Implementation plan for the preview window. No app code until that plan is accepted.

## V1 app

- [ ] Project layout, pyproject, and a window that opens
- [ ] JSON categories for the default folders
- [ ] Scan top-level files and skip partial downloads and junk
- [ ] Classify by extension, with Others as the fallback
- [ ] Preview table with a checkbox on each row
- [ ] Move only confirmed rows, keeping both files on a name clash
- [ ] Undo log outside the sorted folder, and an Undo action
- [ ] Tests on a temporary folder: partial download, subfolder left alone, name clash, and undo

## Not in v1

Watching, tray, startup, subfolders, keyword rules, file contents, duplicates, photo dates, models, overwrite, and permanent delete.
