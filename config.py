import os
from pathlib import Path

# Allowed paths 
DEFAULT_ALLOWED_PATHS = [
    str(Path.home() / "Projects"),  
    "D:/Projects",                   
]

def get_allowed_paths() -> list[str]:
    """Get allowed paths from env variable or defaults."""
    env_paths = os.getenv("DEVSCOPE_ALLOWED_PATHS", "")
    if env_paths:
        return [p.strip() for p in env_paths.split(",") if p.strip()]
    return DEFAULT_ALLOWED_PATHS

# Blocked commands 
BLOCKED_COMMANDS = [
    "rm -rf",
    "rmdir /s",
    "del /f",
    "format",
    "mkfs",
    "dd if=",
    "shutdown",
    "reboot",
    ":(){:|:&};:",   # fork bomb
    "chmod 777",
    "sudo rm",
    "curl | bash",
    "wget | bash",
]

#  File settings  

MAX_FILE_SIZE_MB = 2

ALLOWED_EXTENSIONS = {
    # Code
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".h", ".cs",
    ".go", ".rs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".r",
    # Web
    ".html", ".css", ".scss", ".sass",
    # Config
    ".json", ".yaml", ".yml", ".toml",
    ".ini", ".env.example", ".cfg",
    # Docs
    ".md", ".txt", ".rst",
    # Shell
    ".sh", ".bash", ".zsh", ".ps1",
    # Data
    ".csv", ".xml", ".sql",
}

# Folders to skip
SKIP_DIRECTORIES = {
    ".venv", "venv", "env",
    "__pycache__", ".git",
    "node_modules", ".next",
    "dist", "build", ".cache",
    ".idea", ".vscode",
    "chroma_db", ".egg-info",
}

#  Shell settings  

# Set to True to completely disable run_command
READ_ONLY_MODE = False

# Max time a command is allowed to run
COMMAND_TIMEOUT_SECONDS = 30

#  Search settings  
MAX_SEARCH_RESULTS = 50

#  Git settings  
DEFAULT_GIT_LOG_LIMIT = 20

#  Safety helpers  

def is_path_allowed(path: str) -> bool:
    """Check if a given path is within the allowed paths"""
    resolved = str(Path(path).resolve())
    return any(
        resolved.startswith(str(Path(allowed).resolve()))
        for allowed in get_allowed_paths()
    )

def is_command_blocked(command: str) -> bool:
    """Check if a command contains any blocked patterns"""
    command_lower = command.lower()
    return any(blocked in command_lower for blocked in BLOCKED_COMMANDS)

def is_extension_allowed(path: str) -> bool:
    """Check if a file extension is in the allowed list"""
    return Path(path).suffix.lower() in ALLOWED_EXTENSIONS

def is_file_too_large(path: str) -> bool:
    """Check if a file exceeds the maximum allowed size"""
    try:
        size_mb = Path(path).stat().st_size / (1024 * 1024)
        return size_mb > MAX_FILE_SIZE_MB
    except Exception:
        return False