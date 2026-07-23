import subprocess
import shlex
import os
from pathlib import Path
from config import (
    is_path_allowed,
    is_command_blocked,
    READ_ONLY_MODE,
    COMMAND_TIMEOUT_SECONDS,
)


#  run_command 


def run_command(
    command: str,
    working_directory: str = ".",
    timeout: int = COMMAND_TIMEOUT_SECONDS,
    environment: dict = None,
) -> dict:
    """Run a shell command and return its output"""
    
    #  Safety gates 

    if READ_ONLY_MODE:
        return {
            "error": "run_command is disabled — server is running in READ_ONLY_MODE"
        }

    if not command.strip():
        return {"error": "Command cannot be empty"}

    if is_command_blocked(command):
        return {
            "error": f"Command blocked by safety config: '{command}'",
            "hint":  "This command matches a blocked pattern. Edit BLOCKED_COMMANDS in config.py if you need to allow it."
        }

    #  Resolve working directory 

    resolved_dir = Path(working_directory).resolve()

    if not resolved_dir.exists():
        return {"error": f"Working directory not found: {working_directory}"}

    if not resolved_dir.is_dir():
        return {"error": f"Working directory is not a directory: {working_directory}"}

    if not is_path_allowed(str(resolved_dir)):
        return {
            "error": f"Access denied: {working_directory} is outside allowed directories"
        }

    #  Cap timeout 

    timeout = min(timeout, 120)

    #  Build environment 

    # Build environment with git in PATH
    env = os.environ.copy()
    
    # Ensure git is findable
    git_paths = [
        "C:\\Program Files\\Git\\cmd",
        "C:\\Program Files\\Git\\mingw64\\bin",
    ]
    current_path = env.get("PATH", "")
    extra = ";".join(p for p in git_paths if p not in current_path)
    if extra:
        env["PATH"] = extra + ";" + current_path

    if environment:
        env.update(environment)

    #  Execute 

    try:
        try:
            args = shlex.split(command)
        except ValueError:
            # fallback for commands shlex can't parse
            args = command.split()

        result = subprocess.run(
            args,
            shell=False,            
            cwd=str(resolved_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        return {
            "command":           command,
            "working_directory": str(resolved_dir),
            "exit_code":         result.returncode,
            "success":           result.returncode == 0,
            "stdout":            stdout,
            "stderr":            stderr,
            "output":            stdout or stderr,
            "timed_out":         False,
        }

    except FileNotFoundError:
        return {
            "command":   command,
            "exit_code": -1,
            "success":   False,
            "stdout":    "",
            "stderr":    f"Command not found: '{command.split()[0]}'",
            "output":    f"Command not found: '{command.split()[0]}'",
            "timed_out": False,
        }

    except subprocess.TimeoutExpired:
        return {
            "command":   command,
            "exit_code": -1,
            "success":   False,
            "stdout":    "",
            "stderr":    f"Command timed out after {timeout} seconds",
            "output":    f"Command timed out after {timeout} seconds",
            "timed_out": True,
        }

    except Exception as e:
        return {
            "command":   command,
            "exit_code": -1,
            "success":   False,
            "stdout":    "",
            "stderr":    str(e),
            "output":    str(e),
            "timed_out": False,
        }


#  run_tests 


def run_tests(path: str, framework: str = "auto") -> dict:
    """Run the test suite for a project and return structured results"""
    
    resolved = Path(path).resolve()

    if not resolved.exists():
        return {"error": f"Path not found: {path}"}

    if not is_path_allowed(str(resolved)):
        return {"error": f"Access denied: {path} is outside allowed directories"}

    #  Auto-detect framework 

    if framework == "auto":
        framework = _detect_test_framework(resolved)
        if not framework:
            return {
                "error": "Could not detect test framework",
                "hint":  "Pass framework='pytest', 'unittest', or 'npm' explicitly"
            }

    #  Build command 

    command_map = {
        "pytest":    "pytest --tb=short -q",
        "unittest":  "python -m unittest discover -v",
        "npm":       "npm test --if-present",
        "jest":      "npx jest --no-coverage",
    }

    command = command_map.get(framework.lower())
    if not command:
        return {"error": f"Unknown framework: {framework}. Use: {list(command_map.keys())}"}

    #  Run 

    raw = run_command(command, working_directory=str(resolved), timeout=60)

    if "error" in raw and "exit_code" not in raw:
        return raw

    return {
        "framework":         framework,
        "command":           raw.get("command"),
        "working_directory": raw.get("working_directory"),
        "success":           raw.get("success"),
        "exit_code":         raw.get("exit_code"),
        "output":            raw.get("output"),
        "stdout":            raw.get("stdout"),
        "stderr":            raw.get("stderr"),
        "timed_out":         raw.get("timed_out"),
        "summary":           _parse_test_summary(raw.get("output", ""), framework),
    }


#  get_environment 


def get_environment(path: str) -> dict:
    """Return environment info for a project directory"""
    
    resolved = Path(path).resolve()

    if not is_path_allowed(str(resolved)):
        return {"error": f"Access denied: {path} is outside allowed directories"}

    info = {}

    #  Python 
    py = run_command("python --version", working_directory=str(resolved))
    info["python"] = py.get("output", "not found") if py.get("success") else "not found"

    #  Node 
    node = run_command("node --version", working_directory=str(resolved))
    info["node"] = node.get("output", "not found") if node.get("success") else "not found"

    #  npm 
    npm = run_command("npm --version", working_directory=str(resolved))
    info["npm"] = npm.get("output", "not found") if npm.get("success") else "not found"

    #  Git 
    git_ver = run_command("git --version", working_directory=str(resolved))
    info["git"] = git_ver.get("output", "not found") if git_ver.get("success") else "not found"

    #  Virtual env 
    venv_path = os.environ.get("VIRTUAL_ENV", "")
    info["virtual_env"] = {
        "active":  bool(venv_path),
        "path":    venv_path or None,
    }

    #  Project type detection 
    info["project_type"] = _detect_project_type(resolved)

    return {
        "working_directory": str(resolved),
        "environment": info,
    }


#  internal helpers 


def _detect_test_framework(path: Path) -> str | None:
    """Detect the test framework from project files."""
    if (path / "pytest.ini").exists():        return "pytest"
    if (path / "setup.cfg").exists():         return "pytest"
    if (path / "pyproject.toml").exists():    return "pytest"
    if list(path.glob("test_*.py")):          return "pytest"
    if list(path.glob("tests/test_*.py")):    return "pytest"
    if (path / "package.json").exists():
        try:
            import json
            pkg = json.loads((path / "package.json").read_text())
            scripts = pkg.get("scripts", {})
            if "test" in scripts:
                test_cmd = scripts["test"].lower()
                if "jest" in test_cmd:     return "jest"
                return "npm"
        except Exception:
            return "npm"
    if list(path.glob("**/unittest*.py")):    return "unittest"
    return None


def _detect_project_type(path: Path) -> list[str]:
    """Detect what kind of project this is from its files."""
    types = []
    if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
        types.append("python")
    if (path / "package.json").exists():
        types.append("javascript/node")
    if (path / "Cargo.toml").exists():
        types.append("rust")
    if (path / "go.mod").exists():
        types.append("go")
    if (path / "pom.xml").exists():
        types.append("java/maven")
    if (path / "Dockerfile").exists():
        types.append("docker")
    if (path / "docker-compose.yml").exists() or (path / "docker-compose.yaml").exists():
        types.append("docker-compose")
    return types or ["unknown"]


def _parse_test_summary(output: str, framework: str) -> dict:
    """
    Extract a quick pass/fail summary from test runner output.
    Best-effort — returns raw output if parsing fails.
    """
    if not output:
        return {"parsed": False}

    summary = {"parsed": False, "raw_tail": output[-300:]}

    try:
        if framework == "pytest":
            # pytest summary line: "3 passed, 1 failed in 0.42s"
            for line in reversed(output.splitlines()):
                line = line.strip()
                if "passed" in line or "failed" in line or "error" in line:
                    summary["parsed"]  = True
                    summary["line"]    = line
                    summary["passed"]  = "passed" in line and "failed" not in line
                    break

        elif framework in ("npm", "jest"):
            # Jest: "Tests: 3 passed, 1 failed"
            for line in output.splitlines():
                if line.strip().startswith("Tests:"):
                    summary["parsed"] = True
                    summary["line"]   = line.strip()
                    summary["passed"] = "failed" not in line.lower()
                    break

    except Exception:
        pass

    return summary