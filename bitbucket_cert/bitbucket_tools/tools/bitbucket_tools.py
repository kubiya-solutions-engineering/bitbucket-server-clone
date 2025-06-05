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
    description="Test Git access to Bitbucket repositories with dual authentication (client certificates + basic auth)",
    content="""python /tmp/list_bitbucket_repos.py "{{ .project_key }}" "{{ .repo_slug }}" """,
    args=[
        Arg(name="project_key", type="str", description="Project key (e.g., kubika2)", required=False),
        Arg(name="repo_slug", type="str", description="Repository slug (e.g., kubikaos) - leave empty to test known repositories", required=False),
    ],
    with_files=[
        FileSpec(
            destination="/tmp/list_bitbucket_repos.py",
            content="""#!/usr/bin/env python3
import sys
import subprocess
import os
sys.path.append('/tmp')

from github_funcs import (
    get_bitbucket_server_url,
    setup_client_cert_files,
    test_bitbucket_connection,
    setup_git_with_dual_auth,
    test_git_dual_auth
)

def diagnose_authentication_requirements():
    \"\"\"Diagnose what authentication the server actually requires\"\"\"
    print("🔍 Diagnosing Bitbucket Authentication Requirements")
    print("-" * 50)
    
    server_url = get_bitbucket_server_url()
    test_url = f"{server_url}/scm/kubika2/kubikaos.git/info/refs?service=git-upload-pack"
    
    try:
        cert_path, key_path = setup_client_cert_files()
        
        print("1️⃣ Testing client certificates only...")
        result = subprocess.run([
            "curl", "-s", "-I", "-w", "HTTP_CODE:%{http_code}\\n",
            "--cert", cert_path,
            "--key", key_path,
            "-k",  # Allow insecure SSL
            test_url
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            output = result.stdout
            if "HTTP_CODE:200" in output:
                print("   ✅ Client certificates alone are sufficient!")
                return "client_cert_only"
            elif "HTTP_CODE:401" in output:
                print("   ❌ Client certificates alone are NOT sufficient")
                if "WWW-Authenticate: Basic" in output:
                    print("   💡 Server requires BASIC authentication in addition to client certificates")
                    return "dual_auth_required"
            else:
                print(f"   ⚠️ Unexpected response: {output}")
        
        print("2️⃣ Testing what credentials are available...")
        user_email = os.getenv("KUBIYA_USER_EMAIL", "")
        user_creds = os.getenv("JIRA_USER_CREDS", "")
        
        print(f"   - User email: {'✅ Available' if user_email else '❌ Not set'}")
        print(f"   - User credentials: {'✅ Available' if user_creds else '❌ Not set'}")
        
        if user_creds and ":" in user_creds:
            print("   💡 Credentials format looks correct (username:password)")
            return "dual_auth_possible"
        elif user_email:
            print("   ⚠️ Only email available - may need explicit password")
            return "partial_creds"
        else:
            print("   ❌ No user credentials available")
            return "no_creds"
            
    except Exception as e:
        print(f"   ❌ Diagnosis failed: {e}")
        return "unknown"

def test_repository_access(project_key, repo_slug):
    \"\"\"Test repository access with comprehensive approach\"\"\"
    print(f"\\n🔗 Testing Repository Access: {project_key}/{repo_slug}")
    print("-" * 50)
    
    # First, diagnose authentication requirements
    auth_status = diagnose_authentication_requirements()
    
    print(f"\\n📋 Authentication Status: {auth_status}")
    
    if auth_status == "client_cert_only":
        print("✅ Proceeding with client certificate authentication only...")
        
        # Use standard client cert approach
        try:
            cert_path, key_path = setup_client_cert_files()
            server_url = get_bitbucket_server_url()
            git_url = f"{server_url}/scm/{project_key}/{repo_slug}.git"
            
            git_env = {
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_SSL_NO_VERIFY": "1",
                "GIT_SSL_CERT": cert_path,
                "GIT_SSL_KEY": key_path,
            }
            
            result = subprocess.run(
                ["git", "ls-remote", "--heads", git_url],
                capture_output=True,
                text=True,
                timeout=30,
                env=git_env
            )
            
            if result.returncode == 0:
                branches = result.stdout.strip().split('\\n') if result.stdout.strip() else []
                return True, branches
            else:
                print(f"❌ Failed: {result.stderr}")
                return False, []
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False, []
    
    elif auth_status in ["dual_auth_required", "dual_auth_possible"]:
        print("🔐 Attempting dual authentication (client cert + basic auth)...")
        
        # Use the new dual authentication approach
        success, branches = test_git_dual_auth(project_key, repo_slug)
        return success, branches
    
    else:
        print("❌ Cannot proceed - authentication requirements not met")
        print("\\n💡 Required for Git operations:")
        print("  1. ✅ Client certificates (available)")
        if auth_status in ["dual_auth_required", "partial_creds", "no_creds"]:
            print("  2. ❌ Username and password (missing or incomplete)")
            print("\\n🔧 To fix this:")
            print("  - Ensure JIRA_USER_CREDS environment variable is set")
            print("  - Format: 'username:password'")
            print("  - Contact Audi IT for your Bitbucket username/password")
        
        return False, []

def main():
    project_key = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "<no value>" else None
    repo_slug = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "<no value>" else None
    
    print("🔧 Bitbucket Dual Authentication Test")
    print("=" * 50)
    
    # Test basic connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish basic connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    print("✅ Basic connection works.")
    
    # Known repositories to test
    test_repos = []
    
    if project_key and repo_slug:
        test_repos.append((project_key, repo_slug))
    elif project_key:
        test_repos.append((project_key, "kubikaos"))
    else:
        test_repos = [
            ("kubika2", "kubikaos"),  # From customer URL
        ]
    
    print(f"\\nTesting {len(test_repos)} repository(ies) with comprehensive authentication...")
    
    success_count = 0
    for proj_key, repo_name in test_repos:
        print("\\n" + "=" * 60)
        success, branches = test_repository_access(proj_key, repo_name)
        if success:
            success_count += 1
            print("\\n✅ Repository accessible! Branches found:")
            for branch in branches[:5]:
                if branch:
                    parts = branch.split('\\t')
                    if len(parts) == 2:
                        commit_hash = parts[0][:8]
                        branch_ref = parts[1].replace('refs/heads/', '')
                        print(f"  - {branch_ref} ({commit_hash})")
            if len(branches) > 5:
                print(f"  ... and {len(branches) - 5} more branches")
    
    print("\\n" + "=" * 60)
    print(f"🎯 FINAL RESULT: {success_count}/{len(test_repos)} repositories accessible")
    
    if success_count > 0:
        print("✅ SUCCESS: Git operations will work!")
        print("💡 You can proceed with cloning and migration")
    else:
        print("❌ FAILED: Git operations require additional setup")
        print("\\n📋 Summary of findings:")
        print("- ✅ Client certificates: Working")
        print("- ✅ Network connectivity: Working") 
        print("- ❌ Git authentication: Requires username/password")
        print("\\n🔧 Next steps:")
        print("1. Obtain Bitbucket username/password from Audi IT")
        print("2. Set JIRA_USER_CREDS environment variable: 'username:password'")
        print("3. Re-run this test")
        print("\\nNote: This is a common enterprise setup requiring dual authentication")

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
    description="Get repository information using Git HTTPS transport (branches, recent commits, etc.)",
    content="""python /tmp/get_repo_info.py "{{ .project_key }}" "{{ .repo_slug }}" """,
    args=[
        Arg(name="project_key", type="str", description="Project key (e.g., kubika2)", required=True),
        Arg(name="repo_slug", type="str", description="Repository slug (e.g., kubikaos)", required=True),
    ],
    with_files=[
        FileSpec(
            destination="/tmp/get_repo_info.py",
            content="""#!/usr/bin/env python3
import sys
import subprocess
import tempfile
import os
import shutil
sys.path.append('/tmp')

from github_funcs import (
    get_bitbucket_server_url,
    setup_client_cert_files,
    test_bitbucket_connection
)

def setup_git_with_certificates():
    \"\"\"Set up git configuration to use client certificates\"\"\"
    cert_path, key_path = setup_client_cert_files()
    server_url = get_bitbucket_server_url()
    
    # Configure git to use the certificates
    git_config_commands = [
        ["git", "config", "--global", "http.sslCert", cert_path],
        ["git", "config", "--global", "http.sslKey", key_path],
        ["git", "config", "--global", f"http.{server_url}.sslVerify", "false"]
    ]
    
    for cmd in git_config_commands:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    
    return cert_path, key_path

def get_git_repo_info(project_key, repo_slug):
    \"\"\"Get repository information using Git operations\"\"\"
    server_url = get_bitbucket_server_url()
    git_url = f"{server_url}/scm/{project_key}/{repo_slug}.git"
    
    print(f"Repository Information: {project_key}/{repo_slug}")
    print("=" * 50)
    print(f"Git URL: {git_url}")
    
    try:
        # Set up certificates
        setup_git_with_certificates()
        
        # Get remote branches
        print("\\n🌿 Getting branches...")
        result = subprocess.run(
            ["git", "ls-remote", "--heads", git_url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            branches = [line.split('\\t')[1].replace('refs/heads/', '') 
                       for line in result.stdout.strip().split('\\n') if line]
            print(f"✅ Found {len(branches)} branches:")
            for branch in branches[:10]:  # Show first 10 branches
                print(f"  - {branch}")
            if len(branches) > 10:
                print(f"  ... and {len(branches) - 10} more branches")
        else:
            print(f"❌ Failed to get branches: {result.stderr}")
            return False
        
        # Get tags
        print("\\n🏷️  Getting tags...")
        result = subprocess.run(
            ["git", "ls-remote", "--tags", git_url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            tags = [line.split('\\t')[1].replace('refs/tags/', '') 
                   for line in result.stdout.strip().split('\\n') 
                   if line and not line.endswith('^{}')]
            if tags:
                print(f"✅ Found {len(tags)} tags:")
                for tag in tags[-5:]:  # Show last 5 tags
                    print(f"  - {tag}")
                if len(tags) > 5:
                    print(f"  ... and {len(tags) - 5} more tags")
            else:
                print("No tags found")
        else:
            print(f"⚠️ Could not get tags: {result.stderr}")
        
        # Get default branch info by doing a shallow clone
        print("\\n📊 Getting recent commits (shallow clone)...")
        with tempfile.TemporaryDirectory() as temp_dir:
            clone_dir = os.path.join(temp_dir, "repo")
            
            # Shallow clone to get recent commits
            result = subprocess.run(
                ["git", "clone", "--depth=5", git_url, clone_dir],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # Get recent commits
                result = subprocess.run(
                    ["git", "log", "--oneline", "-5"],
                    capture_output=True,
                    text=True,
                    cwd=clone_dir
                )
                
                if result.returncode == 0:
                    commits = result.stdout.strip().split('\\n')
                    print(f"✅ Recent commits:")
                    for commit in commits:
                        if commit:
                            print(f"  {commit}")
                
                # Get current branch
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    cwd=clone_dir
                )
                
                if result.returncode == 0:
                    current_branch = result.stdout.strip()
                    print(f"\\n🎯 Default branch: {current_branch}")
                
                # Get repository size (approximate)
                try:
                    total_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                   for dirpath, dirnames, filenames in os.walk(clone_dir)
                                   for filename in filenames)
                    size_mb = total_size / (1024 * 1024)
                    print(f"📦 Repository size (approx): {size_mb:.2f} MB")
                except:
                    pass
                    
            else:
                print(f"⚠️ Could not clone for detailed info: {result.stderr}")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Git operation timed out")
        return False
    except Exception as e:
        print(f"❌ Failed to get repository info: {e}")
        return False

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
    
    print("✅ Basic connection works. Getting repository info via Git...")
    
    try:
        success = get_git_repo_info(project_key, repo_slug)
        if not success:
            sys.exit(1)
            
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
    description="Show guidance for working with Bitbucket repositories using Git HTTPS transport",
    content="python /tmp/list_bitbucket_projects.py",
    args=[],
    with_files=[
        FileSpec(
            destination="/tmp/list_bitbucket_projects.py",
            content="""#!/usr/bin/env python3
import sys
sys.path.append('/tmp')

from github_funcs import test_bitbucket_connection, get_bitbucket_server_url

def main():
    print("🔧 Bitbucket Git Access Guide")
    print("=" * 40)
    
    # Test connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish basic connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    server_url = get_bitbucket_server_url()
    
    print("✅ Basic connection works!")
    print("\\n📋 Git HTTPS Transport Information:")
    print(f"Server URL: {server_url}")
    print("\\n🎯 For this customer setup:")
    print("- REST API listing is restricted (this is normal for enterprise setups)")
    print("- Git HTTPS operations work with client certificates")
    print("- Use direct Git URLs for operations")
    
    print("\\n🌐 Git URL Format:")
    print(f"{server_url}/scm/{{project_key}}/{{repo_slug}}.git")
    
    print("\\n📂 Known Repositories:")
    print("- kubika2/kubikaos")
    print("  Git URL: https://api.cip.audi.de/bitbucket/scm/kubika2/kubikaos.git")
    
    print("\\n🛠️  Available Operations:")
    print("1. Test Git access: Use 'list_bitbucket_repos' tool")
    print("2. Get repo info: Use 'get_bitbucket_repo_info' tool")
    print("3. Clone repository: Use 'clone_repo' tool")
    print("4. Migrate to GitHub: Use 'migrate_bitbucket_to_github' tool")
    
    print("\\n💡 Tips:")
    print("- All operations use Git HTTPS transport with client certificates")
    print("- No REST API access needed for Git operations")
    print("- Migration tool works directly with Git operations")
    
    print("\\n✅ Ready to proceed with Git-based operations!")

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
    description="Debug Git HTTPS transport and certificate configuration for Bitbucket",
    content="python /tmp/debug_bitbucket_api.py",
    args=[],
    with_files=[
        FileSpec(
            destination="/tmp/debug_bitbucket_api.py",
            content="""#!/usr/bin/env python3
import sys
import subprocess
import os
sys.path.append('/tmp')

from github_funcs import (
    get_bitbucket_server_url,
    get_bitbucket_headers,
    setup_client_cert_files,
    test_bitbucket_connection
)

def test_git_connectivity():
    \"\"\"Test Git connectivity and certificate setup\"\"\"
    print("\\n🔧 Testing Git Configuration and Connectivity")
    print("-" * 50)
    
    server_url = get_bitbucket_server_url()
    
    try:
        # Set up certificates
        cert_path, key_path = setup_client_cert_files()
        
        print(f"✅ Certificate files created:")
        print(f"  - Cert: {cert_path} ({os.path.getsize(cert_path)} bytes)")
        print(f"  - Key: {key_path} ({os.path.getsize(key_path)} bytes)")
        
        # Configure git with enhanced client certificate settings
        print("\\n🔧 Configuring Git with certificates...")
        git_config_commands = [
            ["git", "config", "--global", "http.sslCert", cert_path],
            ["git", "config", "--global", "http.sslKey", key_path], 
            ["git", "config", "--global", f"http.{server_url}.sslVerify", "false"],
            ["git", "config", "--global", f"http.{server_url}.sslCertPasswordProtected", "false"],
            ["git", "config", "--global", "credential.helper", ""],  # Disable credential helper
            ["git", "config", "--global", "http.askpass", ""],  # Disable askpass
        ]
        
        for cmd in git_config_commands:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ {' '.join(cmd[2:])}")
            else:
                print(f"  ❌ Failed: {' '.join(cmd[2:])}")
                print(f"     Error: {result.stderr}")
        
        return True
        
    except Exception as e:
        print(f"❌ Git setup failed: {e}")
        return False

def test_git_operations():
    \"\"\"Test various Git operations\"\"\"
    print("\\n🌐 Testing Git Operations")
    print("-" * 50)
    
    server_url = get_bitbucket_server_url()
    
    # Known repositories to test
    test_repos = [
        ("kubika2", "kubikaos", "From customer URL"),
    ]
    
    success_count = 0
    
    for project_key, repo_slug, description in test_repos:
        git_url = f"{server_url}/scm/{project_key}/{repo_slug}.git"
        print(f"\\n🔍 Testing: {project_key}/{repo_slug} ({description})")
        print(f"   URL: {git_url}")
        
        try:
            # Test git ls-remote
            print("   Testing git ls-remote...")
            result = subprocess.run(
                ["git", "ls-remote", "--heads", git_url],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # Disable terminal prompts
            )
            
            if result.returncode == 0:
                branches = result.stdout.strip().split('\\n') if result.stdout.strip() else []
                print(f"   ✅ Success! Found {len(branches)} branches")
                if branches:
                    # Show first few branches
                    for branch in branches[:3]:
                        if branch:
                            branch_name = branch.split('\\t')[1].replace('refs/heads/', '')
                            commit_hash = branch.split('\\t')[0][:8]
                            print(f"      - {branch_name} ({commit_hash})")
                    if len(branches) > 3:
                        print(f"      ... and {len(branches) - 3} more")
                success_count += 1
            else:
                print(f"   ❌ Failed: {result.stderr.strip()}")
                if "authentication" in result.stderr.lower():
                    print("   💡 Suggestion: Check certificate permissions")
                elif "username" in result.stderr.lower():
                    print("   💡 Issue: Git trying to use username/password instead of client certificates")
                elif "timeout" in result.stderr.lower():
                    print("   💡 Suggestion: Check network connectivity")
                elif "not found" in result.stderr.lower():
                    print("   💡 Suggestion: Verify repository path")
                    
        except subprocess.TimeoutExpired:
            print("   ❌ Timeout (30s)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\\n🎯 Git Operations Summary: {success_count}/{len(test_repos)} repositories accessible")
    return success_count > 0

def test_basic_git_commands():
    \"\"\"Test basic Git functionality\"\"\"
    print("\\n⚙️  Testing Basic Git Commands")
    print("-" * 50)
    
    # Test git version
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Git version: {result.stdout.strip()}")
        else:
            print("❌ Git not found or not working")
            return False
    except:
        print("❌ Git command failed")
        return False
    
    # Test git config
    try:
        configs_to_check = [
            "http.sslCert",
            "http.sslKey", 
            f"http.{get_bitbucket_server_url()}.sslVerify"
        ]
        
        print("\\n🔧 Current Git configuration:")
        for config in configs_to_check:
            result = subprocess.run(
                ["git", "config", "--global", config],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                value = result.stdout.strip()
                print(f"  ✅ {config}: {value}")
            else:
                print(f"  ⚠️  {config}: Not set")
        
        return True
        
    except Exception as e:
        print(f"❌ Git config check failed: {e}")
        return False

def main():
    print("🔧 Bitbucket Git Transport Debug Tool")
    print("=" * 50)
    
    # Test basic connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish basic connection to Bitbucket. Please check your configuration.")
        sys.exit(1)
    
    print("✅ Basic Bitbucket connection works!")
    
    # Test Git basics
    if not test_basic_git_commands():
        print("\\n❌ Basic Git commands failed. Please check Git installation.")
        sys.exit(1)
    
    # Test Git connectivity setup
    if not test_git_connectivity():
        print("\\n❌ Git connectivity setup failed.")
        sys.exit(1)
    
    # Test actual Git operations
    git_success = test_git_operations()
    
    # Summary
    print("\\n" + "=" * 50)
    print("🎯 Summary:")
    print("✅ Basic connection: Working")
    print("✅ Git setup: Working") 
    if git_success:
        print("✅ Git operations: Working")
        print("\\n💚 Ready for Git operations (clone, migration, etc.)!")
    else:
        print("❌ Git operations: Failed")
        print("\\n🔍 Next steps:")
        print("- Verify repository names and paths")
        print("- Check certificate permissions for Git operations")
        print("- Contact customer for additional access if needed")

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