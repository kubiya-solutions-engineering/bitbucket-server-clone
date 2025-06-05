#!/usr/bin/env python3
"""
Clone repository from Bitbucket Server using client certificate authentication.
Updated to handle dual authentication (client certificates + basic auth).
"""

import subprocess
import sys
import os
import shutil
sys.path.append('/tmp')

from github_funcs import (
    get_bitbucket_server_url,
    setup_git_with_dual_auth,
    test_bitbucket_connection
)

def clone_repository(project_key: str, repo_slug: str, destination: str = None, branch: str = None) -> bool:
    """
    Clone a repository from Bitbucket Server using dual authentication.
    
    Args:
        project_key: The project key (e.g., kubika2)
        repo_slug: The repository slug (e.g., kubikaos)
        destination: Local directory to clone into (defaults to repo_slug)
        branch: Specific branch to clone (optional)
    
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"🔄 Cloning {project_key}/{repo_slug} from Bitbucket...")
    
    # Test connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket")
        return False
    
    try:
        # Set up dual authentication
        cert_path, key_path, username, password = setup_git_with_dual_auth()
        
        # Construct Git URL
        server_url = get_bitbucket_server_url()
        git_url = f"{server_url}/scm/{project_key}/{repo_slug}.git"
        
        # If we have username/password, embed them in the URL for authentication
        if username and password:
            print(f"🔐 Using dual authentication: client certificates + basic auth")
            auth_git_url = git_url.replace("https://", f"https://{username}:{password}@")
        else:
            print(f"⚠️ Using client certificates only (may fail if server requires basic auth)")
            auth_git_url = git_url
        
        # Set destination directory
        if not destination:
            destination = repo_slug
        
        # Clean up existing directory if it exists
        if os.path.exists(destination):
            print(f"🧹 Removing existing directory: {destination}")
            shutil.rmtree(destination)
        
        # Prepare environment for Git
        git_env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_SSL_NO_VERIFY": "1",
            "GIT_SSL_CERT": cert_path,
            "GIT_SSL_KEY": key_path,
        }
        
        # Build git clone command
        clone_cmd = ["git", "clone"]
        
        if branch:
            clone_cmd.extend(["--branch", branch])
            print(f"📋 Cloning specific branch: {branch}")
        
        clone_cmd.extend([auth_git_url, destination])
        
        print(f"📥 Executing: git clone {git_url} {destination}")
        if branch:
            print(f"   Branch: {branch}")
        
        # Execute clone
        result = subprocess.run(
            clone_cmd,
            env=git_env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for large repos
        )
        
        if result.returncode == 0:
            print(f"✅ Successfully cloned to: {destination}")
            
            # Get some info about the cloned repository
            try:
                # Count files (excluding .git)
                file_count = 0
                for root, dirs, files in os.walk(destination):
                    if '.git' not in root:
                        file_count += len(files)
                
                print(f"📊 Repository contains approximately {file_count} files")
                
                # Get current branch
                branch_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=destination,
                    capture_output=True,
                    text=True
                )
                
                if branch_result.returncode == 0:
                    current_branch = branch_result.stdout.strip()
                    print(f"📍 Current branch: {current_branch}")
                
            except Exception as e:
                print(f"⚠️ Could not get repository info: {e}")
            
            return True
        else:
            print(f"❌ Clone failed!")
            print(f"Error: {result.stderr}")
            
            # Provide helpful error diagnosis
            if "401" in result.stderr:
                print("💡 Authentication failed - this indicates:")
                if username and password:
                    print("   - Client certificates work but credentials may be incorrect")
                    print("   - Check JIRA_USER_CREDS format: 'username:password'")
                else:
                    print("   - Server requires username/password in addition to client certificates")
                    print("   - Set JIRA_USER_CREDS environment variable")
            elif "timeout" in result.stderr.lower():
                print("💡 Operation timed out - the repository may be very large")
            elif "not found" in result.stderr.lower():
                print("💡 Repository not found - check project key and repository slug")
            
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Clone operation timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"❌ Clone failed with error: {e}")
        return False

def main():
    """Main function for command-line usage"""
    if len(sys.argv) < 3:
        print("Usage: clone_repo.py <project_key> <repo_slug> [--destination=<path>] [--branch=<branch>]")
        print("Example: clone_repo.py kubika2 kubikaos --destination=/tmp/kubikaos --branch=main")
        sys.exit(1)
    
    project_key = sys.argv[1]
    repo_slug = sys.argv[2]
    
    # Parse optional arguments
    destination = None
    branch = None
    
    for arg in sys.argv[3:]:
        if arg.startswith("--destination="):
            destination = arg.split("=", 1)[1]
            if destination == "<no value>":
                destination = None
        elif arg.startswith("--branch="):
            branch = arg.split("=", 1)[1]
            if branch == "<no value>":
                branch = None
    
    print("🚀 Bitbucket Repository Cloning Tool")
    print("=" * 40)
    print(f"Project: {project_key}")
    print(f"Repository: {repo_slug}")
    if destination:
        print(f"Destination: {destination}")
    if branch:
        print(f"Branch: {branch}")
    print("=" * 40)
    
    success = clone_repository(project_key, repo_slug, destination, branch)
    
    if success:
        print("\n🎉 Clone completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Clone failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 