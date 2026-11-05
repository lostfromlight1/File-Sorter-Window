---
name: file-sorter
description: >
  Builds and changes the Windows Downloads sorter: scan top-level files,
  preview destinations, move confirmed rows, and undo that run. Use when
  the user mentions sort, preview, move, undo, Downloads, a category,
  or an extension folder.
---

# File sorter

## Pipeline

Do the work in this order. Do not skip ahead to a move.

1. Scan files sitting directly in the chosen folder.
2. Skip partial downloads and junk. They are not rows the user can move.
3. Match the extension to a category in the JSON rules. Unknown extensions go to Others.
4. Show one preview row per file, checked by default, with the destination path visible.
5. On confirm, move only checked rows. Write source and destination, including any `name (1)` rename, to the undo log.
6. Undo reads that log, puts the files back, and removes empty folders that run created.

## Categories

The JSON rules file is the only place a category or extension mapping is defined. The window reads it. Do not hardcode extension lists in the UI.

Default folders:

- Images — jpg, jpeg, png, gif, webp, heic, bmp
- Documents/Word — doc, docx, rtf, odt
- Documents/Excel — xls, xlsx, csv, ods
- Documents/PDF — pdf
- Documents/Slides — ppt, pptx, odp
- Installers — exe, msi
- Archives — zip, rar, 7z, iso
- Video — mp4, mkv, mov, avi, webm
- Audio — mp3, wav, flac, m4a
- Others — no matching extension

Adding a category means editing that JSON, then checking the preview against a temporary folder.

## Progress

When a feature or phase is finished, check it off in `TRACKER.md` in the same change. Follow `.cursor/rules/progress-and-commits.mdc`. Do not run git. Hand over the PowerShell commit command and leave the author as Kaung's existing git identity.

## When the contract changes

If a change alters what this version does (what is scanned, what can move, where a category goes, or what undo restores), update `.cursor/rules/v1-scope.mdc` or `.cursor/rules/move-safety.mdc` in the same change. Update this skill when the pipeline or the category list changes.

## Tests

Create a temporary directory. Put a few top-level files in it, one file inside a subfolder, and one `file.crdownload`. Assert:

- The subfolder file and the partial download are not moved.
- A known extension lands in the matching folder.
- An unknown extension lands in Others.
- A name clash becomes `name (1).ext`.
- Undo puts the files back.

Never use the real Downloads folder as the test fixture.
