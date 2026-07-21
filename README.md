# 🔭 devscope

A local MCP server that gives AI assistants real-time access to your development environment without you having to copy-paste anything.

## How it works

```
You ask Claude a question about your project
        ↓
Claude calls devscope tools autonomously
        ↓
devscope reads your local files, git, or runs a command
        ↓
Claude answers with full, accurate context
```

Without devscope, you manually copy files into the chat. With devscope, Claude navigates your project itself.

## Tools

### File Tools
| Tool | Description |
|------|-------------|
| `read_file` | Read the contents of any file |
| `list_directory` | List files and folders as a tree |

### Git Tools
| Tool | Description |
|------|-------------|
| `get_git_status` | Branch, last commit, and change counts at a glance |
| `get_git_log` | Recent commit history with changed files per commit |
| `get_git_diff` | Current staged and unstaged changes |

### Search Tools
| Tool | Description |
|------|-------------|
| `search_code` | Search across files for a keyword or regex pattern |
| `find_definition` | Jump to where a function, class, or variable is defined |

### Shell Tools
| Tool | Description |
|------|-------------|
| `get_environment` | Python version, Node version, virtual env status |
| `run_command` | Run a shell command and return its output |
| `run_tests` | Run the test suite |

## Safety

Every tool runs through a safety layer before executing:

- **Path allowlist** — only directories you explicitly allow can be accessed
- **Command blocklist** — destructive commands (`rm -rf`, `format`, `shutdown` etc.) are blocked at all times
- **Extension filter** — only source code and config files can be read (no binaries, no `.env`)
- **File size limit** — files over 2MB are not read
- **Read-only mode** — single toggle in `config.py` to disable `run_command` entirely
- **Timeout** — commands are killed after 30 seconds

Configure all of this in `config.py`.