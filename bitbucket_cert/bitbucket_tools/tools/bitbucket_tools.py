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

# Debug API permissions tool
debug_api_tool = BitBucketCertTool(
    name="debug_bitbucket_api",
    description="Debug Bitbucket API endpoints to check permissions and access",
    content="python /tmp/debug_bitbucket_api.py",
    args=[],
    with_files=[
        FileSpec(
            destination="/tmp/debug_bitbucket_api.py",
            content="""#!/usr/bin/env python3
import sys
import requests
import json
sys.path.append('/tmp')

from github_funcs import (
    get_bitbucket_server_url,
    get_bitbucket_headers,
    setup_client_cert_files,
    test_bitbucket_connection
)

def test_endpoint(endpoint_path, description):
    \"\"\"Test a specific API endpoint\"\"\"
    server_url = get_bitbucket_server_url()
    cert_path, key_path = setup_client_cert_files()
    full_url = f"{server_url}{endpoint_path}"
    
    print(f"\\n🔍 Testing {description}")
    print(f"URL: {full_url}")
    
    try:
        response = requests.get(
            full_url,
            cert=(cert_path, key_path),
            headers=get_bitbucket_headers(),
            verify=False
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, dict):
                    if 'values' in data:
                        print(f"✅ Success - Found {len(data['values'])} items")
                        # Show first few items
                        for i, item in enumerate(data['values'][:3]):
                            if isinstance(item, dict):
                                key = item.get('key', item.get('slug', item.get('name', f'Item {i+1}')))
                                name = item.get('name', '')
                                print(f"  - {key}: {name}")
                    else:
                        print(f"✅ Success - Response keys: {list(data.keys())}")
                elif isinstance(data, list):
                    print(f"✅ Success - Found {len(data)} items")
                else:
                    print(f"✅ Success - Response type: {type(data)}")
            except:
                print(f"✅ Success - Response length: {len(response.text)} chars")
        elif response.status_code == 401:
            print("❌ 401 Unauthorized - Certificate may not have permission for this endpoint")
        elif response.status_code == 403:
            print("❌ 403 Forbidden - Access denied")
        elif response.status_code == 404:
            print("❌ 404 Not Found - Endpoint doesn't exist")
        else:
            print(f"❌ {response.status_code} - {response.reason}")
            
        # Show error details if available
        if response.status_code >= 400:
            try:
                error_data = response.json()
                if 'errors' in error_data:
                    for error in error_data['errors']:
                        print(f"  Error: {error.get('message', error)}")
            except:
                pass
                
    except Exception as e:
        print(f"❌ Request failed: {e}")

def main():
    print("🔧 Bitbucket API Permissions Debug Tool")
    print("=" * 50)
    
    # Test connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    print("\\n✅ Basic connection works. Testing specific endpoints...")
    
    # Test various endpoints to understand permissions
    endpoints_to_test = [
        ("/rest/api/1.0/projects", "List all projects"),
        ("/rest/api/1.0/repos", "List all repositories"),
        ("/rest/api/1.0/projects/kubika2", "Get kubika2 project details"),
        ("/rest/api/1.0/projects/kubika2/repos", "List repos in kubika2 project"),
        ("/rest/api/1.0/projects/kubika2/repos/kubikaos", "Get kubikaos repository details"),
        ("/rest/api/1.0/projects/kubika2/repos/kubikaos/branches", "Get kubikaos branches"),
        ("/rest/api/1.0/users", "List users (limited test)"),
        ("/rest/api/1.0/admin/users", "Admin users endpoint (may be restricted)"),
    ]
    
    for endpoint, description in endpoints_to_test:
        test_endpoint(endpoint, description)
    
    print("\\n" + "=" * 50)
    print("🎯 Summary:")
    print("- If kubika2/kubikaos endpoints work, we can proceed with migration")
    print("- If general listing endpoints fail, it's likely a permissions issue")
    print("- The migration should still work if the specific repo endpoints work")

if __name__ == "__main__":
    main()
""",
        ),
        FileSpec(
            destination="/tmp/github_funcs.py",
            content=inspect.getsource(github_funcs),
        )
    ])

# Migrate repository tool - Clone from Bitbucket and push to GitHub
migrate_repo_tool = BitBucketCertTool(
    name="migrate_bitbucket_to_github",
    description="Clone a repository from Bitbucket and migrate it to GitHub",
    content="""python /tmp/migrate_repo.py "{{ .project_key }}" "{{ .repo_slug }}" "{{ .github_repo_url }}" "{{ .github_token }}" --temp-dir="{{ .temp_dir }}" --branch="{{ .branch }}" """,
    args=[
        Arg(name="project_key", type="str", description="Bitbucket project key (e.g., kubika2)", required=True),
        Arg(name="repo_slug", type="str", description="Bitbucket repository slug (e.g., kubikaos)", required=True),
        Arg(name="github_repo_url", type="str", description="Destination GitHub repository URL where the Bitbucket repo will be migrated to (e.g., https://github.com/kubiyabot/audi-qa)", required=True),
        Arg(name="github_token", type="str", description="GitHub personal access token for authentication", required=True),
        Arg(name="temp_dir", type="str", description="Temporary directory for cloning (defaults to /tmp/migration)", required=False),
        Arg(name="branch", type="str", description="Specific branch to migrate (defaults to all branches)", required=False),
    ],
    with_files=[
        FileSpec(
            destination="/tmp/migrate_repo.py",
            content="""#!/usr/bin/env python3
import sys
import os
import subprocess
import shutil
import tempfile
sys.path.append('/tmp')

from github_funcs import test_bitbucket_connection
from clone_repo import clone_repository

def run_command(cmd, cwd=None, capture_output=False):
    \"\"\"Run a shell command and handle errors\"\"\"
    print(f"Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()
        else:
            subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, check=True)
            return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        if capture_output and e.stdout:
            print(f"stdout: {e.stdout}")
        if capture_output and e.stderr:
            print(f"stderr: {e.stderr}")
        return False

def main():
    if len(sys.argv) < 5:
        print("❌ Project key, repo slug, GitHub repo URL, and GitHub token are required")
        print("Usage: migrate_repo.py <project_key> <repo_slug> <github_repo_url> <github_token> [--temp-dir=<dir>] [--branch=<branch>]")
        sys.exit(1)
    
    project_key = sys.argv[1]
    repo_slug = sys.argv[2]
    github_repo_url = sys.argv[3]
    github_token = sys.argv[4]
    
    # Parse optional arguments
    temp_dir = "/tmp/migration"
    branch = None
    
    for arg in sys.argv[5:]:
        if arg.startswith("--temp-dir="):
            temp_dir = arg.split("=", 1)[1]
            if temp_dir == "<no value>":
                temp_dir = "/tmp/migration"
        elif arg.startswith("--branch="):
            branch = arg.split("=", 1)[1]
            if branch == "<no value>":
                branch = None
    
    print(f"🚀 Starting migration: {project_key}/{repo_slug} -> {github_repo_url}")
    print("=" * 60)
    
    # Test Bitbucket connection
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    # Create temporary directory
    if os.path.exists(temp_dir):
        print(f"🧹 Cleaning up existing directory: {temp_dir}")
        shutil.rmtree(temp_dir)
    
    os.makedirs(temp_dir, exist_ok=True)
    repo_dir = os.path.join(temp_dir, repo_slug)
    
    try:
        print(f"📥 Step 1: Cloning from Bitbucket...")
        
        # Use the existing clone_repository function
        success = clone_repository(project_key, repo_slug, destination=repo_dir, branch=branch)
        if not success:
            print("❌ Failed to clone repository from Bitbucket")
            sys.exit(1)
        
        print("✅ Successfully cloned from Bitbucket")
        
        # Change to repository directory
        os.chdir(repo_dir)
        
        print(f"🔧 Step 2: Configuring Git remotes...")
        
        # Remove existing origin remote
        run_command(["git", "remote", "remove", "origin"])
        
        # Add GitHub remote with token authentication
        if github_token and not github_repo_url.startswith("https://"):
            print("❌ GitHub repo URL must start with https://")
            sys.exit(1)
        
        # Insert token into GitHub URL
        if "github.com" in github_repo_url:
            github_auth_url = github_repo_url.replace("https://", f"https://{github_token}@")
        else:
            print("❌ Only GitHub.com repositories are supported")
            sys.exit(1)
        
        run_command(["git", "remote", "add", "origin", github_auth_url])
        
        print("✅ Git remotes configured")
        
        print(f"📤 Step 3: Pushing to GitHub...")
        
        # Get all branches
        if branch:
            # Push specific branch
            run_command(["git", "push", "-u", "origin", branch])
            print(f"✅ Pushed branch: {branch}")
        else:
            # Push all branches
            branches_output = run_command(["git", "branch", "-r"], capture_output=True)
            if branches_output:
                remote_branches = []
                for line in branches_output.split('\\n'):
                    line = line.strip()
                    if line and not line.startswith('origin/HEAD') and line.startswith('origin/'):
                        branch_name = line.replace('origin/', '')
                        remote_branches.append(branch_name)
                
                print(f"Found {len(remote_branches)} branches to push")
                
                # Push each branch
                for branch_name in remote_branches:
                    print(f"Pushing branch: {branch_name}")
                    run_command(["git", "checkout", "-b", branch_name, f"origin/{branch_name}"])
                    run_command(["git", "push", "-u", "origin", branch_name])
            
            # Push all tags
            run_command(["git", "push", "origin", "--tags"])
            print("✅ Pushed all branches and tags")
        
        print(f"🎉 Step 4: Migration completed successfully!")
        print(f"Repository migrated from Bitbucket to: {github_repo_url}")
        
        # Clean up temporary directory
        os.chdir("/tmp")
        shutil.rmtree(temp_dir)
        print(f"🧹 Cleaned up temporary directory: {temp_dir}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        # Clean up on failure
        try:
            os.chdir("/tmp")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
""",
        ),
        FileSpec(
            destination="/tmp/clone_repo.py",
            content=inspect.getsource(clone_repo),
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
        list_projects_tool,
        debug_api_tool,
        migrate_repo_tool
    ]
] 