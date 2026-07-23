import re
from pathlib import Path
from config import (
    is_path_allowed,
    is_extension_allowed,
    SKIP_DIRECTORIES,
    MAX_SEARCH_RESULTS,
)


#  search_code 

def search_code(
    path: str,
    query: str,
    extension: str = None,
    case_sensitive: bool = False,
    context_lines: int = 2,
) -> dict:
    """Search across all files in a directory for a keyword or pattern"""
    
    resolved = Path(path).resolve()

    if not resolved.exists():
        return {"error": f"Path not found: {path}"}

    if not resolved.is_dir():
        return {"error": f"Path is not a directory: {path}"}

    if not is_path_allowed(str(resolved)):
        return {"error": f"Access denied: {path} is outside allowed directories"}

    if not query.strip():
        return {"error": "Search query cannot be empty"}

    # Normalize extension filter
    if extension and not extension.startswith("."):
        extension = f".{extension}"

    matches = []
    files_searched = 0
    files_skipped = 0

    for file_path in _walk_files(resolved, extension):
        files_searched += 1

        file_matches = _search_file(
            file_path=file_path,
            query=query,
            case_sensitive=case_sensitive,
            context_lines=context_lines,
        )

        if file_matches:
            matches.append({
                "file": str(file_path),
                "relative_path": str(file_path.relative_to(resolved)),
                "match_count": len(file_matches),
                "matches": file_matches,
            })

        # Stop if we've hit the result limit
        total_matches = sum(m["match_count"] for m in matches)
        if total_matches >= MAX_SEARCH_RESULTS:
            files_skipped = 0  
            break

    total_matches = sum(m["match_count"] for m in matches)

    return {
        "query":              query,
        "total_matches":      total_matches,
        "files_with_matches": len(matches),
        "results":            matches,
    }


#  find_definition 


def find_definition(path: str, name: str, language: str = "python") -> dict:
    """Find where a function, class, or variable is defined in the codebase"""
    
    resolved = Path(path).resolve()

    if not resolved.exists():
        return {"error": f"Path not found: {path}"}

    if not is_path_allowed(str(resolved)):
        return {"error": f"Access denied: {path} is outside allowed directories"}

    patterns = _get_definition_patterns(name, language)

    if not patterns:
        return {"error": f"Unsupported language: {language}"}

    definitions = []

    for file_path in _walk_files(resolved, extension=_lang_to_extension(language)):
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        for line_num, line in enumerate(lines, start=1):
            for pattern in patterns:
                if pattern.search(line):
                    definitions.append({
                        "file":         str(file_path),
                        "relative_path": str(file_path.relative_to(resolved)),
                        "line_number":  line_num,
                        "line":         line.strip(),
                        "kind":         _infer_kind(line, language),
                    })
                    break   # Don't double-match the same line

    return {
        "name":             name,
        "language":         language,
        "path":             str(resolved),
        "definition_count": len(definitions),
        "definitions":      definitions,
    }


#  internal helpers 


def _walk_files(root: Path, extension: str = None):
    """Yield all allowed files under root, skipping blocked directories."""
    
    for item in sorted(root.rglob("*")):
        # Skip blocked directories
        if any(skip in item.parts for skip in SKIP_DIRECTORIES):
            continue
        if not item.is_file():
            continue
        if not is_extension_allowed(item.name):
            continue
        if extension and item.suffix.lower() != extension.lower():
            continue
        yield item


def _search_file(
    file_path: Path,
    query: str,
    case_sensitive: bool,
    context_lines: int,
) -> list:
    """Search a single file and return all matches with context."""
    try:
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []

    matches = []

    for line_num, line in enumerate(lines, start=1):
        hit = False

        if case_sensitive:
            hit = query in line
        else:
            hit = query.lower() in line.lower()

        if hit:
            # Gather surrounding context lines
            start = max(0, line_num - 1 - context_lines)
            end   = min(len(lines), line_num + context_lines)
            context = [
                {
                    "line_number": i + 1,
                    "content":     lines[i],
                    "is_match":    (i + 1 == line_num),
                }
                for i in range(start, end)
            ]

            matches.append({
                "line_number": line_num,
                "line":        line.strip(),
                "context":     context,
            })

    return matches

def _get_definition_patterns(name: str, language: str) -> list:
    """Return compiled regex patterns that match definitions for the given language."""
    escaped = re.escape(name)

    patterns_map = {
        "python": [
            re.compile(rf"^\s*def\s+{escaped}\s*\("),
            re.compile(rf"^\s*class\s+{escaped}\s*[\(:]"),
            re.compile(rf"^\s*{escaped}\s*="),
        ],
        "javascript": [
            re.compile(rf"function\s+{escaped}\s*\("),
            re.compile(rf"const\s+{escaped}\s*="),
            re.compile(rf"let\s+{escaped}\s*="),
            re.compile(rf"var\s+{escaped}\s*="),
            re.compile(rf"class\s+{escaped}\s*{{"),
        ],
        "typescript": [
            re.compile(rf"function\s+{escaped}\s*[\(<]"),
            re.compile(rf"const\s+{escaped}\s*[:=]"),
            re.compile(rf"class\s+{escaped}\s*{{"),
            re.compile(rf"interface\s+{escaped}\s*{{"),
            re.compile(rf"type\s+{escaped}\s*="),
        ],
    }

    return patterns_map.get(language.lower(), [])


def _lang_to_extension(language: str) -> str | None:
    """Map language name to file extension."""
    mapping = {
        "python":     ".py",
        "javascript": ".js",
        "typescript": ".ts",
    }
    return mapping.get(language.lower())


def _infer_kind(line: str, language: str) -> str:
    """Infer whether a definition line is a function, class, or variable."""
    stripped = line.strip()

    if language == "python":
        if stripped.startswith("def "):
            return "function"
        if stripped.startswith("class "):
            return "class"
        return "variable"

    if language in ("javascript", "typescript"):
        if "function " in stripped:
            return "function"
        if "class " in stripped:
            return "class"
        if "interface " in stripped:
            return "interface"
        if "type " in stripped:
            return "type"
        return "variable"

    return "unknown"