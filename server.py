import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from tools.file_tools import read_file, list_directory
from tools.git_tools import get_git_log, get_git_diff, get_git_status
from tools.search_tools import search_code, find_definition
from tools.shell_tools import run_command, run_tests, get_environment

# ── Create server ─────────────────────────────────────────────────────────────

app = Server("devscope")

# ── Tool registry ─────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Tell the AI client what tools are available."""
    return [

        # ── File tools ────────────────────────────────────────────────────────

        types.Tool(
            name="read_file",
            description="Read the contents of a file. Use this to inspect specific files in the project.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file"
                    }
                },
                "required": ["path"]
            }
        ),

        types.Tool(
            name="list_directory",
            description="List files and folders at a path as a tree. Use this first to understand the project structure before reading specific files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "How many levels deep to traverse (default 2, max 5)",
                        "default": 2
                    }
                },
                "required": ["path"]
            }
        ),

        # ── Git tools ─────────────────────────────────────────────────────────

        types.Tool(
            name="get_git_status",
            description="Get a quick status overview of a git repository — current branch, last commit, and change counts. Call this before get_git_log or get_git_diff to orient yourself.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the git repository or any folder inside it"
                    }
                },
                "required": ["path"]
            }
        ),

        types.Tool(
            name="get_git_log",
            description="Get the recent commit history of a git repository with changed files per commit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the git repository or any folder inside it"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of commits to return (default 20, max 100)",
                        "default": 20
                    }
                },
                "required": ["path"]
            }
        ),

        types.Tool(
            name="get_git_diff",
            description="Get current uncommitted changes (staged and unstaged) in a git repository. Use this to see what is being worked on right now.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the git repository or any folder inside it"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Optional — filter diff to a specific file only"
                    }
                },
                "required": ["path"]
            }
        ),

        # ── Search tools ──────────────────────────────────────────────────────

        types.Tool(
            name="search_code",
            description="Search across all files in a directory for a keyword or pattern. Returns matches with surrounding context lines. Use this to find where something is used across the codebase.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory to search"
                    },
                    "query": {
                        "type": "string",
                        "description": "Keyword or regex pattern to search for"
                    },
                    "extension": {
                        "type": "string",
                        "description": "Optional file extension filter e.g. '.py' or '.js'"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search is case sensitive (default false)",
                        "default": False
                    },
                    "use_regex": {
                        "type": "boolean",
                        "description": "Treat query as a regex pattern (default false)",
                        "default": False
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of lines to show around each match (default 2)",
                        "default": 2
                    }
                },
                "required": ["path", "query"]
            }
        ),

        types.Tool(
            name="find_definition",
            description="Find where a function, class, or variable is defined in the codebase. More targeted than search_code — use this when you want to jump straight to a definition.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory to search"
                    },
                    "name": {
                        "type": "string",
                        "description": "Function, class, or variable name to find"
                    },
                    "language": {
                        "type": "string",
                        "description": "Language hint: 'python', 'javascript', or 'typescript' (default 'python')",
                        "default": "python"
                    }
                },
                "required": ["path", "name"]
            }
        ),

        # ── Shell tools ───────────────────────────────────────────────────────

        types.Tool(
            name="get_environment",
            description="Get environment info for a project — Python version, Node version, virtual env status, and project type. Call this before suggesting or running commands.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project directory to inspect"
                    }
                },
                "required": ["path"]
            }
        ),

        types.Tool(
            name="run_command",
            description="Run a shell command in a given directory and return its output. Always call get_environment first to understand the runtime. Never run destructive commands.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": "Directory to run the command in (default: current dir)",
                        "default": "."
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max seconds to wait (default 30, max 120)",
                        "default": 30
                    }
                },
                "required": ["command"]
            }
        ),

        types.Tool(
            name="run_tests",
            description="Run the test suite for a project. Auto-detects pytest, unittest, Jest, or npm test from the project structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the project root"
                    },
                    "framework": {
                        "type": "string",
                        "description": "Test framework: 'pytest', 'unittest', 'npm', 'jest', or 'auto' (default 'auto')",
                        "default": "auto"
                    }
                },
                "required": ["path"]
            }
        ),
    ]


# ── Tool executor ─────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Execute the tool the AI requested and return the result."""

    try:
        result = await asyncio.to_thread(_dispatch, name, arguments)
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": f"Tool execution failed: {str(e)}"})
        )]


def _dispatch(name: str, arguments: dict):
    """Route tool name to the correct function."""

    # ── File tools ────────────────────────────────────────────────────────────

    if name == "read_file":
        return read_file(
            path=arguments["path"]
        )

    elif name == "list_directory":
        return list_directory(
            path=arguments["path"],
            depth=arguments.get("depth", 2)
        )

    # ── Git tools ─────────────────────────────────────────────────────────────

    elif name == "get_git_status":
        return get_git_status(
            path=arguments["path"]
        )

    elif name == "get_git_log":
        return get_git_log(
            path=arguments["path"],
            limit=arguments.get("limit", 20)
        )

    elif name == "get_git_diff":
        return get_git_diff(
            path=arguments["path"],
            file_path=arguments.get("file_path")
        )

    # ── Search tools ──────────────────────────────────────────────────────────

    elif name == "search_code":
        return search_code(
            path=arguments["path"],
            query=arguments["query"],
            extension=arguments.get("extension"),
            case_sensitive=arguments.get("case_sensitive", False),
            use_regex=arguments.get("use_regex", False),
            context_lines=arguments.get("context_lines", 2)
        )

    elif name == "find_definition":
        return find_definition(
            path=arguments["path"],
            name=arguments["name"],
            language=arguments.get("language", "python")
        )

    # ── Shell tools ───────────────────────────────────────────────────────────

    elif name == "get_environment":
        return get_environment(
            path=arguments["path"]
        )

    elif name == "run_command":
        return run_command(
            command=arguments["command"],
            working_directory=arguments.get("working_directory", "."),
            timeout=arguments.get("timeout", 30)
        )

    elif name == "run_tests":
        return run_tests(
            path=arguments["path"],
            framework=arguments.get("framework", "auto")
        )

    # ── Unknown ───────────────────────────────────────────────────────────────

    else:
        return {"error": f"Unknown tool: {name}"}


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())