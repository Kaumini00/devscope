from pathlib import Path
from config import is_path_allowed, DEFAULT_GIT_LOG_LIMIT

try:
    import git
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


#  helpers 


def _get_repo(path: str):
    """Resolve and validate a git repo at the given path"""
    
    if not GIT_AVAILABLE:
        return None, {"error": "gitpython not installed"}

    resolved = Path(path).resolve()

    if not resolved.exists():
        return None, {"error": f"Path not found: {path}"}

    if not is_path_allowed(str(resolved)):
        return None, {"error": f"Access denied: {path}"}

    try:
        repo = git.Repo(str(resolved), search_parent_directories=True)
        # Test git is actually reachable
        _ = repo.git.version()
        return repo, None
    except git.InvalidGitRepositoryError:
        return None, {"error": f"Not a git repository: {path}"}
    except Exception as e:
        return None, {"error": f"Could not open repository: {e}"}
    

#  get_git_log 


def get_git_log(path: str, limit: int = DEFAULT_GIT_LOG_LIMIT) -> dict:
    """Return recent commit history for a git repository"""
    
    repo, error = _get_repo(path)
    if error:
        return error

    limit = min(limit, 100)

    try:
        commits = []
        for commit in repo.iter_commits(max_count=limit):
            # Changed files per commit
            changed_files = []
            if commit.parents:
                diffs = commit.parents[0].diff(commit)
                changed_files = [d.a_path or d.b_path for d in diffs]

            commits.append({
                "hash":          commit.hexsha[:8],
                "author":        commit.author.name,
                "date":          commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "message":       commit.message.strip(),
                "changed_files": changed_files,
                "files_count":   len(changed_files),
            })

        return {
            "repo": str(repo.working_dir),
            "branch": str(repo.active_branch),
            "total_returned": len(commits),
            "commits": commits,
        }

    except Exception as e:
        return {"error": f"Could not read git log: {e}"}


#  get_git_diff 


def get_git_diff(path: str, file_path: str = None) -> dict:
    """Return current uncommitted changes"""
    repo, error = _get_repo(path)
    if error:
        return error

    try:
        results = {
            "branch": str(repo.active_branch),
            "staged": [],
            "unstaged": [],
            "untracked": [],
            "summary": {}
        }

        #  Staged changes (index vs HEAD) 
        try:
            staged_diffs = repo.index.diff("HEAD")
        except Exception:
            # HEAD doesn't exist yet (empty repo / first commit)
            staged_diffs = repo.index.diff(None)

        for diff in staged_diffs:
            if file_path and diff.a_path != file_path and diff.b_path != file_path:
                continue
            results["staged"].append(_format_diff(diff))

        #  Unstaged changes (working tree vs index) 
        for diff in repo.index.diff(None):
            if file_path and diff.a_path != file_path and diff.b_path != file_path:
                continue
            results["unstaged"].append(_format_diff(diff))

        #  Untracked files 
        untracked = repo.untracked_files
        if file_path:
            untracked = [f for f in untracked if f == file_path]
        results["untracked"] = untracked

        #  Summary 
        results["summary"] = {
            "staged_files":    len(results["staged"]),
            "unstaged_files":  len(results["unstaged"]),
            "untracked_files": len(results["untracked"]),
            "has_changes":     bool(
                results["staged"] or
                results["unstaged"] or
                results["untracked"]
            ),
        }

        return results

    except Exception as e:
        return {"error": f"Could not get diff: {e}"}


#  get_git_status 


def get_git_status(path: str) -> dict:
    """Return a concise status overview of the repository"""
    
    repo, error = _get_repo(path)
    if error:
        return error

    try:
        # Last commit
        last_commit = None
        try:
            commit = next(repo.iter_commits(max_count=1))
            last_commit = {
                "hash":    commit.hexsha[:8],
                "message": commit.message.strip().splitlines()[0],
                "author":  commit.author.name,
                "date":    commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            }
        except StopIteration:
            pass  # Empty repo

        # Remote info
        remotes = [
            {"name": r.name, "url": r.url}
            for r in repo.remotes
        ]

        return {
            "branch":         str(repo.active_branch),
            "is_dirty":       repo.is_dirty(untracked_files=True),
            "staged_count":   len(repo.index.diff("HEAD")) if last_commit else 0,
            "unstaged_count": len(repo.index.diff(None)),
            "untracked_count":len(repo.untracked_files),
            "last_commit":    last_commit,
            "remotes":        remotes,
        }

    except Exception as e:
        return {"error": f"Could not get status: {e}"}


#  internal formatter 


def _format_diff(diff) -> dict:
    """Format a single diff object into a clean dict"""
    
    change_type_map = {
        "A": "added",
        "D": "deleted",
        "M": "modified",
        "R": "renamed",
        "C": "copied",
    }

    patch = ""
    try:
        patch = diff.diff.decode("utf-8", errors="ignore") if diff.diff else ""
    except Exception:
        patch = "[binary file or unreadable diff]"

    return {
        "file":        diff.b_path or diff.a_path,
        "change_type": change_type_map.get(diff.change_type, diff.change_type),
        "patch":       patch,
    }