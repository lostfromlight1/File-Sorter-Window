# File Sorter

A Windows app that previews where the top-level files in a chosen folder would move, moves only the rows you confirm, and can undo that run.

It looks only at files sitting directly in the folder. Files inside subfolders stay where they are. Nothing moves until you confirm.

## Use the app

You need Windows. The setup file already contains the app, so Python and this repository are not required.

1. Get `FileSorter-Setup.exe` from the person who built it.
2. Run it. Windows may show a SmartScreen warning the first time because the setup is not signed.
3. Leave the folder as offered, or pick another. A desktop shortcut is optional.
4. Open **File Sorter** from the Start menu.

The first launch takes a few seconds while the app unpacks.

The folder box starts at your Downloads folder. Change it or click **Browse**, then:

1. **Scan** lists each top-level file, its size, modified time, destination, and whether it can move.
2. Use a category checkbox to include or leave out every file in that category. Uncheck a single row to leave that file in place. **Hide skipped** hides partial downloads and junk in the table. Those rows stay unmoved.
3. **Move** lists how many files go to each category, and how many will be renamed, then moves only the checked rows after you confirm.
4. **Undo** lists the files it will put back, then restores the last run, including files that were renamed because the destination name already existed, and removes empty folders that run created.

Partial downloads (`.crdownload`, `.part`, `.tmp`, `.download`) and junk (`desktop.ini`, `thumbs.db`, `~$*`, dotfiles) are skipped and are not movable.

If a destination name already exists, both files are kept. The new one is named `name (1).ext`, then `name (2).ext`, and so on.

The undo log is stored outside the folder you sort, at `%LOCALAPPDATA%\FileSorter\runs.json`. Uninstalling the app leaves that log on disk.

Uninstall from **Settings**, **Apps**, **Installed apps**.

`FileSorter.exe` is the same app as one portable file. It has no Start menu entry and no uninstall step. Close it by closing the window.

A clone of this repository does not include either file. The `dist` folder is created on the machine that builds them.

## Work on the code

- Windows
- Python 3.12 or newer
- [Inno Setup 6](https://jrsoftware.org/isinfo.php), only when building the setup file

From this folder, in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

`".[dev]"` installs the app plus pytest. Use `python -m pip install -e .` if you only want to run the window.

If activation is blocked, run this once, then activate again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

With the virtual environment activated:

```powershell
file-sorter
```

The same window opens with:

```powershell
python -m file_sorter
```

Extension mappings live in `src/file_sorter/data/default_rules.json`. Edit that file to add a folder or an extension, then scan again. An extension that is not listed goes to `Others`.

Tests use a temporary folder. They do not touch Downloads.

```powershell
python -m pytest
```

## Build the setup

With the virtual environment activated:

```powershell
python -m pip install -e ".[exe]"
pyinstaller --noconfirm file-sorter.spec
$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
& $iscc FileSorter.iss
```

`pyinstaller` writes `dist\FileSorter.exe`. The Inno Setup command writes `dist\FileSorter-Setup.exe`. Hand that setup file to the people who will use the app. The category rules are packed inside it, so edit `src/file_sorter/data/default_rules.json` and run both commands again when those change.
