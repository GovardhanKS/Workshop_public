import os
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")

if not GITHUB_TOKEN:
    raise RuntimeError("Missing GITHUB_TOKEN in .env")

mcp = FastMCP("github-mcp-server")


def github_request(
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.request(
            method=method,
            url=f"{GITHUB_API_URL}{path}",
            headers=headers,
            json=json_body,
            params=params,
        )

    response.raise_for_status()
    return response.json()


@mcp.tool()
def search_repositories(query: str, per_page: int = 10) -> str:
    """Search GitHub repositories by query."""
    per_page = max(1, min(per_page, 50))
    data = github_request(
        "GET", "/search/repositories", params={"q": query, "per_page": per_page}
    )

    items = data.get("items", [])
    if not items:
        return "No repositories found."

    lines = [
        f"{repo['full_name']} | stars: {repo['stargazers_count']} | {repo['html_url']}"
        for repo in items
    ]
    return "\n".join(lines)


@mcp.tool()
def get_repository(owner: str, repo: str) -> dict[str, Any]:
    """Get repository details by owner and repo name."""
    data = github_request("GET", f"/repos/{owner}/{repo}")
    return {
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "open_issues": data.get("open_issues_count"),
        "default_branch": data.get("default_branch"),
        "url": data.get("html_url"),
    }


@mcp.tool()
def list_issues(owner: str, repo: str, state: str = "open", per_page: int = 10) -> str:
    """List issues for a repository. state can be open, closed, or all."""
    if state not in {"open", "closed", "all"}:
        raise ValueError("state must be one of: open, closed, all")

    per_page = max(1, min(per_page, 50))
    data = github_request(
        "GET",
        f"/repos/{owner}/{repo}/issues",
        params={"state": state, "per_page": per_page},
    )

    issues = [item for item in data if "pull_request" not in item]
    if not issues:
        return "No issues found."

    lines = [
        f"#{issue['number']} [{issue['state']}] {issue['title']} | {issue['html_url']}"
        for issue in issues
    ]
    return "\n".join(lines)


@mcp.tool()
def create_issue(owner: str, repo: str, title: str, body: str = "") -> str:
    """Create a new issue in a repository."""
    payload = {"title": title, "body": body}
    data = github_request("POST", f"/repos/{owner}/{repo}/issues", json_body=payload)
    return f"Created issue #{data['number']}: {data['html_url']}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
