#!/usr/bin/env python
"""Test GitHub MCP Server connection and authentication."""

from server import github_request
import json

print("=" * 60)
print("GitHub MCP Server - Connection Test")
print("=" * 60)

try:
    # Test 1: Authenticate and get user info
    print("\n[Test 1] Testing GitHub API Authentication...")
    result = github_request('GET', '/user')
    username = result.get('login')
    print(f"[OK] Authenticated as: {username}")
    print(f"[OK] Name: {result.get('name')}")
    print(f"[OK] GitHub URL: {result.get('html_url')}")

    # Test 2: Search repositories
    print("\n[Test 2] Testing Repository Search...")
    search_result = github_request(
        'GET',
        '/search/repositories',
        params={'q': 'python mcp', 'per_page': 3}
    )
    count = len(search_result.get('items', []))
    print(f"[OK] Found {count} repositories matching 'python mcp'")
    if count > 0:
        first_repo = search_result['items'][0]
        print(f"     - {first_repo['full_name']}")

    print("\n" + "=" * 60)
    print("SUCCESS: All Tests Passed!")
    print("=" * 60)
    print("\nMCP Server is ready to use with these tools:")
    print("  1. search_repositories(query, per_page)")
    print("  2. get_repository(owner, repo)")
    print("  3. list_issues(owner, repo, state, per_page)")
    print("  4. create_issue(owner, repo, title, body)")

except Exception as e:
    print(f"\nERROR: Connection Test Failed!")
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()
