"""File-system tools: search, create, move/rename, copy, delete, zip/unzip.

All paths are resolved under the owner's home directory by default so the model can use
friendly locations like 'Desktop' or 'Downloads/report.pdf'.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

from .registry import tool

HOME = Path.home()


def _resolve(path: str) -> Path:
    """Resolve a user-supplied path. Relative paths are taken under the home directory."""
    p = Path(os.path.expanduser(path))
    if not p.is_absolute():
        p = HOME / p
    return p


@tool(
    name="find_files",
    description="Search for files/folders by name pattern under a directory (recursively).",
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. '*.pdf' or 'report*'.",
            },
            "directory": {
                "type": "string",
                "description": "Where to search. Defaults to the home directory.",
            },
        },
        "required": ["pattern"],
    },
)
def find_files(pattern: str, directory: str = "") -> str:
    base = _resolve(directory) if directory else HOME
    if not base.exists():
        return f"Directory not found: {base}"
    matches = list(base.rglob(pattern))[:50]
    if not matches:
        return f"No matches for '{pattern}' under {base}."
    listing = "\n".join(str(m) for m in matches)
    return f"Found {len(matches)} match(es) (max 50 shown):\n{listing}"


@tool(
    name="list_dir",
    description="List the contents of a directory.",
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "Directory to list (default: home)."},
        },
    },
)
def list_dir(directory: str = "") -> str:
    base = _resolve(directory) if directory else HOME
    if not base.is_dir():
        return f"Not a directory: {base}"
    entries = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    lines = [f"{'[dir] ' if e.is_dir() else '      '}{e.name}" for e in entries[:200]]
    return f"{base}:\n" + "\n".join(lines)


@tool(
    name="create_folder",
    description="Create a new folder (and any missing parent folders).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Folder path to create."},
        },
        "required": ["path"],
    },
)
def create_folder(path: str) -> str:
    p = _resolve(path)
    if p.exists():
        return f"Folder already exists: {p}"
    p.mkdir(parents=True)
    return f"Created folder: {p}"


@tool(
    name="move_file",
    description="Move or rename a file or folder.",
    parameters={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Existing path."},
            "destination": {"type": "string", "description": "New path."},
        },
        "required": ["source", "destination"],
    },
)
def move_file(source: str, destination: str) -> str:
    src, dst = _resolve(source), _resolve(destination)
    if not src.exists():
        return f"Source not found: {src}"
    shutil.move(str(src), str(dst))
    return f"Moved '{src}' -> '{dst}'."


@tool(
    name="copy_file",
    description="Copy a file or folder to a new location.",
    parameters={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Existing path."},
            "destination": {"type": "string", "description": "Destination path."},
        },
        "required": ["source", "destination"],
    },
)
def copy_file(source: str, destination: str) -> str:
    src, dst = _resolve(source), _resolve(destination)
    if not src.exists():
        return f"Source not found: {src}"
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return f"Copied '{src}' -> '{dst}'."


@tool(
    name="delete_file",
    description="Delete a file or folder. Destructive — requires owner confirmation.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to delete."},
        },
        "required": ["path"],
    },
    confirm=True,
)
def delete_file(path: str) -> str:
    p = _resolve(path)
    if not p.exists():
        return f"Nothing to delete; not found: {p}"
    if p.is_dir():
        shutil.rmtree(p)
        return f"Deleted folder: {p}"
    p.unlink()
    return f"Deleted file: {p}"


@tool(
    name="read_text_file",
    description="Read the contents of a text file (first ~8000 characters).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to a text file."},
        },
        "required": ["path"],
    },
)
def read_text_file(path: str) -> str:
    p = _resolve(path)
    if not p.is_file():
        return f"File not found: {p}"
    text = p.read_text(encoding="utf-8", errors="replace")
    return text[:8000] + ("\n...[truncated]" if len(text) > 8000 else "")


@tool(
    name="write_file",
    description=(
        "Create or overwrite a text file with the given content. Use for saving notes, code, or "
        "edits. Overwriting an existing file is destructive — confirm with the owner first."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path to write."},
            "content": {"type": "string", "description": "Full text content to write."},
        },
        "required": ["path", "content"],
    },
    confirm=True,
)
def write_file(path: str, content: str) -> str:
    p = _resolve(path)
    existed = p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    verb = "Overwrote" if existed else "Created"
    return f"{verb} {p} ({len(content)} chars)."


@tool(
    name="zip_files",
    description="Compress a file or folder into a .zip archive.",
    parameters={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "File or folder to compress."},
            "archive_path": {"type": "string", "description": "Output .zip path."},
        },
        "required": ["source", "archive_path"],
    },
)
def zip_files(source: str, archive_path: str) -> str:
    src = _resolve(source)
    dst = _resolve(archive_path)
    if not src.exists():
        return f"Source not found: {src}"
    if not dst.suffix:
        dst = dst.with_suffix(".zip")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        if src.is_file():
            zf.write(src, src.name)
        else:
            for file in src.rglob("*"):
                zf.write(file, file.relative_to(src.parent))
    return f"Created archive: {dst}"


@tool(
    name="unzip_file",
    description="Extract a .zip archive into a folder.",
    parameters={
        "type": "object",
        "properties": {
            "archive_path": {"type": "string", "description": "Path to the .zip file."},
            "destination": {"type": "string", "description": "Folder to extract into."},
        },
        "required": ["archive_path", "destination"],
    },
)
def unzip_file(archive_path: str, destination: str) -> str:
    src = _resolve(archive_path)
    dst = _resolve(destination)
    if not src.is_file():
        return f"Archive not found: {src}"
    with zipfile.ZipFile(src) as zf:
        zf.extractall(dst)
    return f"Extracted '{src}' -> '{dst}'."
