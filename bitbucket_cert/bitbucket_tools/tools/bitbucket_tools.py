import inspect
from typing import List
from kubiya_sdk.tools import Arg, FileSpec
from ..base import BitBucketCertTool, register_bitbucket_tool
from . import clone_repo, github_funcs

# Clone repository tool
clone_repo_tool = BitBucketCertTool(
    name="clone_repo",
    description="Clone a repository from Bitbucket Server using client certificate authentication",
    content="""python /tmp/clone_repo.py "{{ .project_key }}" "{{ .repo_slug }}" --destination="{{ .destination }}" --branch="{{ .branch }}" """,
    args=[
        Arg(name="project_key", type="str", description="Project key (e.g., EOCCJPA)", required=True),
        Arg(name="repo_slug", type="str", description="Repository slug (e.g., kubikaos)", required=True),
        Arg(name="destination", type="str", description="Local directory to clone into (defaults to repo name)", required=False),
        Arg(name="branch", type="str", description="Specific branch to clone", required=False),
    ],
    with_files=[
        FileSpec(
            destination="/tmp/clone_repo.py",
            content=inspect.getsource(clone_repo),
        ),
        FileSpec(
            destination="/tmp/github_funcs.py",
            content=inspect.getsource(github_funcs),
        )
    ])

# List repositories tool
list_repos_tool = BitBucketCertTool(
    name="list_bitbucket_repos",
    description="List available repositories in Bitbucket Server",
    content="""python /tmp/list_bitbucket_repos.py "{{ .project_key }}" """,
    args=[
        Arg(name="project_key", type="str", description="Project key to list repos for (leave empty to list all projects)", required=False),
    ],
    with_files=[
        FileSpec(
            destination="/tmp/list_bitbucket_repos.py",
            content="""#!/usr/bin/env python3
import sys
import os
sys.path.append('/tmp')

from github_funcs import (
    list_bitbucket_projects,
    list_bitbucket_repos,
    test_bitbucket_connection
)

def main():
    project_key = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "<no value>" else None
    
    # Test connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    try:
        if project_key:
            print(f"Repositories in project {project_key}:")
            repos = list_bitbucket_repos(project_key)
            if not repos:
                print(f"No repositories found in project {project_key}")
                return
                
            for repo in repos:
                private_str = "private" if repo.get('public', True) == False else "public"
                print(f"  - {repo['slug']} ({repo['name']}) - {private_str}")
                if 'links' in repo and 'clone' in repo['links']:
                    clone_links = repo['links']['clone']
                    for link in clone_links:
                        if link.get('name') == 'https':
                            print(f"    Clone URL: {link['href']}")
                            break
        else:
            print("Available projects and their repositories:")
            projects = list_bitbucket_projects()
            if not projects:
                print("No projects found")
                return
                
            for project in projects[:10]:  # Limit to first 10 projects
                print(f"\\n📁 {project['key']}: {project['name']}")
                
                try:
                    repos = list_bitbucket_repos(project['key'])
                    if repos:
                        for repo in repos[:5]:  # Show first 5 repos per project
                            private_str = "private" if repo.get('public', True) == False else "public"
                            print(f"    - {repo['slug']} ({repo['name']}) - {private_str}")
                        if len(repos) > 5:
                            print(f"    ... and {len(repos) - 5} more repositories")
                    else:
                        print("    (No repositories)")
                except Exception as e:
                    print(f"    (Could not list repos: {e})")
                    
    except Exception as e:
        print(f"❌ Failed to list repositories: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
""",
        ),
        FileSpec(
            destination="/tmp/github_funcs.py",
            content=inspect.getsource(github_funcs),
        )
    ])

# Test Bitbucket connection tool
test_bitbucket_tool = BitBucketCertTool(
    name="test_bitbucket_connection",
    description="Test connection to Bitbucket Server with client certificates",
    content="python /tmp/test_bitbucket.py",
    args=[],
    with_files=[
        FileSpec(
            destination="/tmp/test_bitbucket.py",
            content="""#!/usr/bin/env python3
import sys
sys.path.append('/tmp')

from github_funcs import test_bitbucket_connection

def main():
    success = test_bitbucket_connection()
    if success:
        print("✅ Bitbucket connection test successful!")
        sys.exit(0)
    else:
        print("❌ Bitbucket connection test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
""",
        ),
        FileSpec(
            destination="/tmp/github_funcs.py",
            content=inspect.getsource(github_funcs),
        )
    ])

# Get repository info tool
get_repo_info_tool = BitBucketCertTool(
    name="get_bitbucket_repo_info",
    description="Get detailed information about a specific Bitbucket repository",
    content="""python /tmp/get_repo_info.py "{{ .project_key }}" "{{ .repo_slug }}" """,
    args=[
        Arg(name="project_key", type="str", description="Project key (e.g., EOCCJPA)", required=True),
        Arg(name="repo_slug", type="str", description="Repository slug (e.g., kubikaos)", required=True),
    ],
    with_files=[
        FileSpec(
            destination="/tmp/get_repo_info.py",
            content="""#!/usr/bin/env python3
import sys
import json
sys.path.append('/tmp')

from github_funcs import (
    get_bitbucket_repo,
    get_bitbucket_branches,
    get_bitbucket_commits,
    test_bitbucket_connection
)

def main():
    if len(sys.argv) < 3:
        print("❌ Project key and repository slug are required")
        sys.exit(1)
        
    project_key = sys.argv[1]
    repo_slug = sys.argv[2]
    
    # Test connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    try:
        # Get repository info
        print(f"Repository Information: {project_key}/{repo_slug}")
        print("=" * 50)
        
        repo_data = get_bitbucket_repo(project_key, repo_slug)
        
        print(f"Name: {repo_data.get('name', 'N/A')}")
        print(f"Description: {repo_data.get('description', 'No description')}")
        print(f"Public: {'Yes' if repo_data.get('public', False) else 'No'}")
        print(f"Fork: {'Yes' if repo_data.get('forkable', False) else 'No'}")
        print(f"SCM: {repo_data.get('scmId', 'N/A')}")
        
        # Show clone URLs
        if 'links' in repo_data and 'clone' in repo_data['links']:
            print("\\nClone URLs:")
            for link in repo_data['links']['clone']:
                print(f"  {link['name']}: {link['href']}")
        
        # Get branches
        try:
            print("\\nBranches:")
            branches = get_bitbucket_branches(project_key, repo_slug)
            for branch in branches[:10]:  # Show first 10 branches
                default_marker = " (default)" if branch.get('isDefault', False) else ""
                print(f"  - {branch['displayId']}{default_marker}")
            if len(branches) > 10:
                print(f"  ... and {len(branches) - 10} more branches")
        except Exception as e:
            print(f"  Could not retrieve branches: {e}")
        
        # Get recent commits from default branch
        try:
            print("\\nRecent Commits:")
            commits = get_bitbucket_commits(project_key, repo_slug, "master", 5)
            for commit in commits:
                author = commit.get('author', {}).get('name', 'Unknown')
                message = commit.get('message', 'No message').split('\\n')[0][:60]
                commit_id = commit.get('id', '')[:8]
                print(f"  {commit_id} - {message} ({author})")
        except Exception as e:
            print(f"  Could not retrieve commits: {e}")
            
    except Exception as e:
        print(f"❌ Failed to get repository information: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
""",
        ),
        FileSpec(
            destination="/tmp/github_funcs.py",
            content=inspect.getsource(github_funcs),
        )
    ])

# List projects tool
list_projects_tool = BitBucketCertTool(
    name="list_bitbucket_projects",
    description="List all accessible Bitbucket projects",
    content="python /tmp/list_bitbucket_projects.py",
    args=[],
    with_files=[
        FileSpec(
            destination="/tmp/list_bitbucket_projects.py",
            content="""#!/usr/bin/env python3
import sys
sys.path.append('/tmp')

from github_funcs import list_bitbucket_projects, test_bitbucket_connection

def main():
    # Test connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    try:
        print("Available Bitbucket Projects:")
        print("=" * 40)
        
        projects = list_bitbucket_projects()
        if not projects:
            print("No projects found")
            return
            
        for project in projects:
            print(f"📁 {project['key']}: {project['name']}")
            if 'description' in project and project['description']:
                print(f"   Description: {project['description']}")
            print(f"   Public: {'Yes' if project.get('public', False) else 'No'}")
            print()
            
    except Exception as e:
        print(f"❌ Failed to list projects: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
""",
        ),
        FileSpec(
            destination="/tmp/github_funcs.py",
            content=inspect.getsource(github_funcs),
        )
    ])

# Register all tools
[
    register_bitbucket_tool(tool) for tool in [
        clone_repo_tool,
        list_repos_tool,
        test_bitbucket_tool,
        get_repo_info_tool,
        list_projects_tool
    ]
] 