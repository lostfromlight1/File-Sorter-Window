from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from file_sorter.rules import Rules, category_dir, category_for
from file_sorter.scan import STATUS_READY, scan_folder


@dataclass
class PreviewRow:
    source: Path
    destination: Path | None
    status: str
    checked: bool
    category: str = ""
    size_bytes: int | None = None
    modified: datetime | None = None

    @property
    def movable(self) -> bool:
        return self.status == STATUS_READY and self.destination is not None


@dataclass
class ApplyResult:
    moved: list[tuple[Path, Path]] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)


@dataclass
class UndoResult:
    restored: list[tuple[Path, Path]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def default_log_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "FileSorter" / "runs.json"


def path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def unique_destination(directory: Path, filename: str, reserved: set[str]) -> Path:
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = directory / filename
    if _is_free(candidate, reserved):
        return candidate
    number = 1
    while True:
        candidate = directory / f"{stem} ({number}){suffix}"
        if _is_free(candidate, reserved):
            return candidate
        number += 1


def build_preview(folder: Path, rules: Rules) -> list[PreviewRow]:
    reserved: set[str] = set()
    rows: list[PreviewRow] = []
    for item in scan_folder(folder):
        if item.status != STATUS_READY:
            rows.append(
                PreviewRow(
                    source=item.path,
                    destination=None,
                    status=item.status,
                    checked=False,
                    size_bytes=item.size_bytes,
                    modified=item.modified,
                )
            )
            continue
        category = category_for(rules, item.path.name)
        directory = category_dir(folder, category)
        destination = unique_destination(directory, item.path.name, reserved)
        reserved.add(path_key(destination))
        rows.append(
            PreviewRow(
                source=item.path,
                destination=destination,
                status=item.status,
                checked=True,
                category=category,
                size_bytes=item.size_bytes,
                modified=item.modified,
            )
        )
    return rows


def move_summary(rows: list[PreviewRow], folder: Path, category_order: list[str]) -> str:
    chosen = [
        row
        for row in rows
        if row.checked and row.movable and row.destination is not None
    ]
    counts: dict[str, int] = {}
    for row in chosen:
        counts[row.category] = counts.get(row.category, 0) + 1
    renamed = sum(
        1
        for row in chosen
        if row.destination is not None and row.destination.name != row.source.name
    )
    noun = "file" if len(chosen) == 1 else "files"
    lines = [f"Move {len(chosen)} {noun} into subfolders of {folder}?", ""]
    seen: set[str] = set()
    for category in category_order:
        count = counts.get(category, 0)
        if count:
            lines.append(f"{category}: {count}")
            seen.add(category)
    for category, count in counts.items():
        if category not in seen and count:
            lines.append(f"{category}: {count}")
    if renamed == 1:
        lines.append("1 file will be renamed because that name already exists.")
    elif renamed > 1:
        lines.append(
            f"{renamed} files will be renamed because that name already exists."
        )
    return "\n".join(lines)


_UNDO_NAME_LIMIT = 15


def undo_summary(log_path: Path) -> str:
    moves = _latest_moves(log_path)
    noun = "file" if len(moves) == 1 else "files"
    lines = [f"Put {len(moves)} {noun} back?"]
    if not moves:
        return lines[0]
    lines.append("")
    shown = moves[:_UNDO_NAME_LIMIT]
    for move in shown:
        source = Path(str(move["src"]))
        destination = Path(str(move["dest"]))
        lines.append(f"{destination.name} -> {source.name}")
    extra = len(moves) - len(shown)
    if extra:
        lines.append(f"and {extra} more")
    return "\n".join(lines)


def apply_preview(rows: list[PreviewRow], source_root: Path, log_path: Path) -> ApplyResult:
    result = ApplyResult()
    root = source_root.resolve()
    reserved: set[str] = set()
    moves: list[dict[str, str]] = []
    created_dirs: list[str] = []
    created_seen: set[str] = set()

    for row in rows:
        if not row.checked or not row.movable or row.destination is None:
            continue
        source = row.source
        new_dirs: list[Path] = []
        try:
            destination = _claim_for_move(row.destination, reserved)
            if path_key(destination) == path_key(source):
                raise OSError(f"{source.name} would move onto itself.")
            new_dirs = _ensure_parent(destination.parent, root)
            shutil.move(str(source), str(destination))
        except OSError as exc:
            _remove_empty_dirs([str(directory) for directory in new_dirs])
            result.errors.append((source, str(exc)))
            continue
        for directory in new_dirs:
            key = path_key(directory)
            if key not in created_seen:
                created_seen.add(key)
                created_dirs.append(str(directory))
        reserved.add(path_key(destination))
        moves.append({"src": str(source), "dest": str(destination)})
        result.moved.append((source, destination))

    if moves:
        runs = _read_runs(log_path)
        runs.append(
            {
                "id": datetime.now(timezone.utc).isoformat(),
                "source_root": str(root),
                "moves": moves,
                "created_dirs": created_dirs,
            }
        )
        _write_runs(log_path, runs)
    return result


def has_undo(log_path: Path) -> bool:
    return bool(_read_runs(log_path))


def latest_move_count(log_path: Path) -> int:
    runs = _read_runs(log_path)
    if not runs:
        return 0
    moves = runs[-1].get("moves", [])
    return len(moves) if isinstance(moves, list) else 0


def undo_latest(log_path: Path) -> UndoResult:
    result = UndoResult()
    runs = _read_runs(log_path)
    if not runs:
        return result
    run = runs[-1]
    remaining: list[dict[str, str]] = []
    reserved: set[str] = set()
    for move in run.get("moves", []):
        source = Path(move["src"])
        destination = Path(move["dest"])
        try:
            if not destination.exists():
                raise OSError(f"Missing {destination}")
            restored = source
            if source.exists() or path_key(source) in reserved:
                restored = unique_destination(source.parent, source.name, reserved)
            reserved.add(path_key(restored))
            restored.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(restored))
        except OSError as exc:
            remaining.append(move)
            result.errors.append(str(exc))
            continue
        result.restored.append((destination, restored))
    if remaining:
        run["moves"] = remaining
        runs[-1] = run
    else:
        runs.pop()
        _remove_empty_dirs(run.get("created_dirs", []))
    _write_runs(log_path, runs)
    return result


def _is_free(candidate: Path, reserved: set[str]) -> bool:
    return path_key(candidate) not in reserved and not candidate.exists()


def _claim_for_move(planned: Path, reserved: set[str]) -> Path:
    if _is_free(planned, reserved):
        return planned
    return unique_destination(planned.parent, planned.name, reserved)


def _ensure_parent(directory: Path, root: Path) -> list[Path]:
    directory = directory.resolve()
    root = root.resolve()
    missing: list[Path] = []
    current = directory
    while current != root and not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    directory.mkdir(parents=True, exist_ok=True)
    missing.reverse()
    return missing


def _latest_moves(log_path: Path) -> list[dict]:
    runs = _read_runs(log_path)
    if not runs:
        return []
    moves = runs[-1].get("moves", [])
    if not isinstance(moves, list):
        return []
    return [
        move
        for move in moves
        if isinstance(move, dict) and "src" in move and "dest" in move
    ]


def _read_runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    runs = payload.get("runs", [])
    return runs if isinstance(runs, list) else []


def _write_runs(path: Path, runs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"runs": runs}, indent=2), encoding="utf-8")
    temporary.replace(path)


def _remove_empty_dirs(directories: list[str]) -> None:
    paths = sorted(
        (Path(item) for item in directories),
        key=lambda directory: len(directory.parts),
        reverse=True,
    )
    for directory in paths:
        try:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        except OSError:
            continue
