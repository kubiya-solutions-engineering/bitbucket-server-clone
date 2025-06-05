#!/usr/bin/env python3
"""
Migrate repository from Bitbucket Server to GitHub.
Clones from https://api.cip.audi.de/bitbucket/scm/kubika2/kubikaos.git
and pushes to a new branch in https://github.com/kubiyabot/audi-qa.git
"""

import subprocess
import sys
import os
import shutil
import tempfile
from datetime import datetime
sys.path.append('/tmp')

from github_funcs import (
    get_bitbucket_server_url,
    setup_git_with_dual_auth,
    test_bitbucket_connection
)

# Hard-coded repository URLs
BITBUCKET_REPO = "https://api.cip.audi.de/bitbucket/scm/kubika2/kubikaos.git"
GITHUB_REPO = "https://github.com/kubiyabot/audi-qa.git"

def run_git_command(cmd, cwd=None, timeout=300):
    """Run a git command and return success status and output"""
    try:
        print(f"🔧 Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            print(f"❌ Command failed: {result.stderr}")
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out after {timeout}s")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Command error: {e}")
        return False, str(e)

def migrate_bitbucket_to_github():
    """
    Complete migration from Bitbucket to GitHub:
    1. Clone from Bitbucket (kubika2/kubikaos)
    2. Create new branch in GitHub (kubiyabot/audi-qa)
    3. Push all content to the new branch
    """
    print("🚀 Starting Bitbucket to GitHub Migration")
    print("=" * 50)
    print(f"📥 Source: {BITBUCKET_REPO}")
    print(f"📤 Target: {GITHUB_REPO}")
    print("=" * 50)
    
    # Test Bitbucket connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket")
        return False
    
    # Get GitHub token
    github_token = os.getenv("GH_KUBIYA_TOKEN")
    if not github_token:
        print("❌ GH_KUBIYA_TOKEN environment variable not set")
        return False
    
    print("✅ GitHub token available")
    
    # Create temporary directory for migration
    temp_dir = tempfile.mkdtemp(prefix="audi_migration_")
    repo_dir = os.path.join(temp_dir, "kubikaos")
    
    try:
        print(f"📁 Working directory: {temp_dir}")
        
        # Step 1: Set up dual authentication for Bitbucket
        print("\n🔐 Step 1: Setting up Bitbucket authentication...")
        cert_path, key_path, username, password = setup_git_with_dual_auth()
        
        if not username or not password:
            print("❌ Bitbucket credentials not available")
            return False
        
        print(f"✅ Bitbucket authentication ready for user: {username}")
        
        # Step 2: Clone from Bitbucket with authentication
        print("\n📥 Step 2: Cloning from Bitbucket...")
        
        # Create authenticated Bitbucket URL
        auth_bitbucket_url = BITBUCKET_REPO.replace(
            "https://", f"https://{username}:{password}@"
        )
        
        # Set up Git environment for Bitbucket
        git_env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_SSL_NO_VERIFY": "1",
            "GIT_SSL_CERT": cert_path,
            "GIT_SSL_KEY": key_path,
        }
        
        # Clone from Bitbucket
        success, output = run_git_command(
            ["git", "clone", auth_bitbucket_url, repo_dir],  # Regular clone, not --mirror
            timeout=600  # 10 minutes for large repos
        )
        
        if not success:
            print(f"❌ Failed to clone from Bitbucket: {output}")
            return False
        
        print("✅ Successfully cloned from Bitbucket")
        
        # Step 3: Configure for GitHub
        print("\n🔧 Step 3: Configuring for GitHub...")
        
        # Change to repo directory
        os.chdir(repo_dir)
        
        # Fetch all remote branches to make them available locally
        print("📡 Fetching all remote branches...")
        success, output = run_git_command(
            ["git", "fetch", "origin"]
        )
        
        # Get all remote branches and create local tracking branches
        success, branches_output = run_git_command(
            ["git", "branch", "-r"]
        )
        
        if success and branches_output:
            remote_branches = []
            for line in branches_output.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('origin/HEAD') and line.startswith('origin/'):
                    branch_name = line.replace('origin/', '')
                    if branch_name != 'HEAD':  # Skip HEAD reference
                        remote_branches.append(branch_name)
            
            print(f"📋 Found {len(remote_branches)} remote branches")
            
            # Get current local branches to avoid conflicts
            success, local_branches_output = run_git_command(
                ["git", "branch"]
            )
            
            local_branches = []
            if success and local_branches_output:
                for line in local_branches_output.strip().split('\n'):
                    branch = line.strip().replace('* ', '')
                    if branch:
                        local_branches.append(branch)
            
            # Create local tracking branches for remote branches that don't exist locally
            for branch in remote_branches:
                if branch not in local_branches:
                    print(f"   🌿 Creating local branch: {branch}")
                    success, output = run_git_command(
                        ["git", "checkout", "-b", branch, f"origin/{branch}"]
                    )
                    if not success:
                        print(f"   ⚠️ Could not create branch {branch}: {output}")
                else:
                    print(f"   ✅ Branch {branch} already exists locally")
        
        # Get current branch
        success, current_branch_output = run_git_command(
            ["git", "branch", "--show-current"]
        )
        
        if success and current_branch_output:
            current_branch = current_branch_output.strip()
            print(f"📍 Current branch: {current_branch}")
        else:
            print("⚠️ Could not determine current branch")
        
        # Create authenticated GitHub URL
        auth_github_url = GITHUB_REPO.replace(
            "https://", f"https://{github_token}@"
        )
        
        # Set up standard Git environment (no client certs for GitHub)
        github_git_env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
        }
        
        # Step 4: Add GitHub remote and fetch
        print("\n🌐 Step 4: Setting up GitHub remote...")
        
        # Add GitHub as origin remote
        success, output = run_git_command(
            ["git", "remote", "add", "github", auth_github_url]
        )
        
        if not success:
            print(f"❌ Failed to add GitHub remote: {output}")
            return False
        
        # Fetch from GitHub to get existing branches
        print("📡 Fetching from GitHub...")
        success, output = run_git_command(
            ["git", "fetch", "github"],
            timeout=300
        )
        
        if not success:
            print(f"⚠️ Could not fetch from GitHub (repo might be empty): {output}")
        
        # Step 5: Create migration branch
        print("\n🌿 Step 5: Creating migration branch...")
        
        # Generate unique branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        migration_branch = f"migration/kubikaos_{timestamp}"
        
        print(f"📋 Branch name: {migration_branch}")
        
        # Create and checkout the migration branch
        success, output = run_git_command(
            ["git", "checkout", "-b", migration_branch]
        )
        
        if not success:
            print(f"❌ Failed to create migration branch: {output}")
            return False
        
        print(f"✅ Created migration branch: {migration_branch}")
        
        # Step 6: Push to GitHub
        print("\n📤 Step 6: Pushing to GitHub...")
        
        # Push the migration branch to GitHub
        success, output = run_git_command(
            ["git", "push", "github", migration_branch],
            timeout=600  # 10 minutes for large pushes
        )
        
        if not success:
            print(f"❌ Failed to push to GitHub: {output}")
            return False
        
        print(f"✅ Successfully pushed to GitHub!")
        
        # Step 7: Push all other branches and tags
        print("\n🏷️ Step 7: Pushing all branches and tags...")
        
        # Get all local branches
        success, branches_output = run_git_command(
            ["git", "branch"]
        )
        
        if success and branches_output:
            branches = []
            for line in branches_output.strip().split('\n'):
                line = line.strip().replace('* ', '')  # Remove current branch indicator
                if line and line != migration_branch:  # Don't include migration branch
                    branches.append(line)
            
            print(f"📋 Found {len(branches)} branches to migrate")
            
            # Push each branch to GitHub
            for branch in branches:
                print(f"   📤 Pushing branch: {branch}")
                success, output = run_git_command(
                    ["git", "push", "github", f"{branch}:{branch}"]
                )
                
                if success:
                    print(f"   ✅ Pushed: {branch}")
                else:
                    print(f"   ⚠️ Failed to push {branch}: {output}")
        
        # Push all tags
        print("🏷️ Pushing tags...")
        success, output = run_git_command(
            ["git", "push", "github", "--tags"]
        )
        
        if success:
            print("✅ Tags pushed successfully")
        else:
            print(f"⚠️ Failed to push tags: {output}")
        
        # Step 8: Summary
        print("\n" + "=" * 50)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 50)
        print(f"📋 Migration Summary:")
        print(f"  - Source: kubika2/kubikaos (Bitbucket)")
        print(f"  - Target: kubiyabot/audi-qa (GitHub)")
        print(f"  - Primary branch: {migration_branch}")
        print(f"  - Repository URL: {GITHUB_REPO}")
        print(f"  - View at: https://github.com/kubiyabot/audi-qa/tree/{migration_branch}")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        return False
        
    finally:
        # Cleanup
        try:
            os.chdir("/tmp")
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                print(f"🧹 Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            print(f"⚠️ Could not clean up temporary directory: {e}")

def main():
    """Main function for the migration tool"""
    print("🚀 Audi Bitbucket to GitHub Migration Tool")
    print("=" * 50)
    
    success = migrate_bitbucket_to_github()
    
    if success:
        print("\n✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 