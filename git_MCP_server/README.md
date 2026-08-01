# Claude Workshop - GitHub MCP Server

A Python MCP (Model Context Protocol) server for GitHub integration. Provides Claude with tools to interact with GitHub repositories, issues, and pull requests.

## Quick Start

### 1. Setup Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Configure GitHub Token

```powershell
copy .env.example .env
```

Edit `.env` and add your GitHub personal access token:

```env
GITHUB_TOKEN=ghp_your_token_here
```

### 4. Run the Server

```powershell
python server.py
```

### 5. Test Connection

```powershell
python test_connection.py
```

## Available Tools

| Tool | Purpose |
|------|---------|
| `search_repositories(query, per_page)` | Search GitHub repositories |
| `get_repository(owner, repo)` | Get repository details |
| `list_issues(owner, repo, state, per_page)` | List repository issues |
| `create_issue(owner, repo, title, body)` | Create a new issue |

## Configuration

### Required Environment Variables

- `GITHUB_TOKEN`: Your GitHub personal access token

### Optional Variables

- `GITHUB_API_URL`: GitHub API endpoint (default: https://api.github.com)

## Claude Code Integration

```json
{
  "mcpServers": {
    "github": {
      "command": "python",
      "args": ["path/to/Claude_Workshop/server.py"],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Security

- `.env` is ignored by git - never commit credentials
- Use `.env.example` as a template
- Regenerate tokens if exposed
- Limit token permissions to required scopes

## References

- [MCP Documentation](https://modelcontextprotocol.io/)
- [GitHub REST API](https://docs.github.com/en/rest)
- [Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
