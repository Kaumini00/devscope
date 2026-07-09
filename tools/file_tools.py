
from pathlib import Path
from config import (
    is_path_allowed,
    is_extension_allowed,
    is_file_too_large,
    SKIP_DIRECTORIES,
    MAX_FILE_SIZE_MB,
)


# ── read_file ─────────────────────────────────────────────────────────────────


def read_file(path: str) -> dict:
    """
    Read the contents of a file.

    Safety checks:
    - Path must be within allowed directories
    - Extension must be in the allowed list
    - File must not exceed MAX_FILE_SIZE_MB
    """
    resolved = Path(path).resolve()

    if not resolved.exists():
        return {"error": f"File not found: {path}"}

    if not resolved.is_file():
        return {"error": f"Path is not a file: {path}"}

    if not is_path_allowed(str(resolved)):
        return {"error": f"Access denied: {path} is outside allowed directories"}

    if not is_extension_allowed(str(resolved)):
        return {"error": f"File type not allowed: {resolved.suffix}"}

    if is_file_too_large(str(resolved)):
        return {"error": f"File too large (limit: {MAX_FILE_SIZE_MB}MB): {path}"}

    try:
        content = resolved.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        return {
            "path": str(resolved),
            "extension": resolved.suffix,
            "lines": len(lines),
            "size_kb": round(resolved.stat().st_size / 1024, 2),
            "content": content,
        }
    except Exception as e:
        return {"error": f"Could not read file: {e}"}


# ── list_directory ────────────────────────────────────────────────────────────


def list_directory(path: str, depth: int = 2) -> dict:
    """
    List files and folders at a given path as a tree.

    Safety checks:
    - Path must be within allowed directories
    - Skips directories in SKIP_DIRECTORIES

    Args:
        path:  Directory to list
        depth: How many levels deep to traverse (default 2, max 5)
    """
    resolved = Path(path).resolve()

    if not resolved.exists():
        return {"error": f"Path not found: {path}"}

    if not resolved.is_dir():
        return {"error": f"Path is not a directory: {path}"}

    if not is_path_allowed(str(resolved)):
        return {"error": f"Access denied: {path} is outside allowed directories"}

    # Cap depth to prevent enormous trees
    depth = min(depth, 5)

    try:
        tree = _build_tree(resolved, depth=depth, current_depth=0)
        return {
            "path": str(resolved),
            "tree": tree,
            "summary": _summarize_tree(tree),
        }
    except Exception as e:
        return {"error": f"Could not list directory: {e}"}


def _build_tree(path: Path, depth: int, current_depth: int) -> list:
    """Recursively build a directory tree structure."""
    if current_depth >= depth:
        return []

    items = []

    try:
        entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return [{"name": "[permission denied]", "type": "error"}]

    for entry in entries:
        # Skip hidden files and blocked directories
        if entry.name.startswith(".") and entry.name not in (".env.example",):
            continue
        if entry.name in SKIP_DIRECTORIES:
            continue

        if entry.is_dir():
            items.append({
                "name": entry.name,
                "type": "directory",
                "children": _build_tree(entry, depth, current_depth + 1),
            })
        elif entry.is_file():
            if is_extension_allowed(entry.name):
                items.append({
                    "name": entry.name,
                    "type": "file",
                    "extension": entry.suffix,
                    "size_kb": round(entry.stat().st_size / 1024, 2),
                })

    return items


def _summarize_tree(tree: list) -> dict:
    """Count files and directories in the tree."""
    files = 0
    dirs = 0

    def _count(items):
        nonlocal files, dirs
        for item in items:
            if item["type"] == "file":
                files += 1
            elif item["type"] == "directory":
                dirs += 1
                _count(item.get("children", []))

    _count(tree)
    return {"total_files": files, "total_directories": dirs}