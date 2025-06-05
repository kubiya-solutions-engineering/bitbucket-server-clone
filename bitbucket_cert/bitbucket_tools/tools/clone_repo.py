import os
import subprocess
import sys
import json
import tempfile
from pathlib import Path
from typing import Optional

# Import from our bitbucket functions (the file is still named github_funcs.py but contains bitbucket functions)
from github_funcs import (
    get_bitbucket_server_url,
    get_bitbucket_headers,
    setup_client_cert_files,
    test_bitbucket_connection,
    get_bitbucket_repo,
    list_bitbucket_projects,
    list_bitbucket_repos
)

def setup_git_with_certificates() -> tuple:
    """
    Set up git configuration to use client certificates for HTTPS authentication.
    Returns tuple of (cert_path, key_path) for cleanup later.
    """
    print("Setting up git with client certificates...")
    
    # Get certificate files
    cert_path, key_path = setup_client_cert_files()
    
    # Configure git to use the certificates
    # Note: This sets global git config, which might affect other git operations
    try:
        subprocess.run([
            "git", "config", "--global", "http.sslCert", cert_path
        ], check=True, capture_output=True, text=True)
        
        subprocess.run([
            "git", "config", "--global", "http.sslKey", key_path
        ], check=True, capture_output=True, text=True)
        
        # Disable SSL verification for the specific domain
        server_url = get_bitbucket_server_url()
        domain = server_url.replace("https://", "").replace("http://", "")
        subprocess.run([
            "git", "config", "--global", f"http.{server_url}.sslVerify", "false"
        ], check=True, capture_output=True, text=True)
        
        print(f"✅ Git configured to use certificates for {domain}")
        return cert_path, key_path
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to configure git: {e}")
        print(f"Error output: {e.stderr}")
        raise RuntimeError(f"Failed to configure git: {e}")

def cleanup_git_config():
    """Clean up git configuration"""
    try:
        print("Cleaning up git configuration...")
        subprocess.run([
            "git", "config", "--global", "--unset", "http.sslCert"
        ], capture_output=True, text=True)
        
        subprocess.run([
            "git", "config", "--global", "--unset", "http.sslKey"
        ], capture_output=True, text=True)
        
        # Clean up the SSL verification setting
        server_url = get_bitbucket_server_url()
        subprocess.run([
            "git", "config", "--global", "--unset", f"http.{server_url}.sslVerify"
        ], capture_output=True, text=True)
        
        print("✅ Git configuration cleaned up")
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Warning: Could not clean up git config: {e}")

def get_clone_url(project_key: str, repo_slug: str) -> str:
    """Get the HTTPS clone URL for a repository"""
    try:
        repo_data = get_bitbucket_repo(project_key, repo_slug)
        
        # Extract clone URLs from the repository data
        clone_links = repo_data.get('links', {}).get('clone', [])
        
        # Find the HTTPS clone URL
        https_url = None
        for link in clone_links:
            if link.get('name') == 'https':
                https_url = link.get('href')
                break
        
        if not https_url:
            # Fallback: construct URL manually
            server_url = get_bitbucket_server_url()
            https_url = f"{server_url}/scm/{project_key}/{repo_slug}.git"
        
        print(f"Clone URL: {https_url}")
        return https_url
        
    except Exception as e:
        print(f"⚠️ Could not get clone URL from API, using fallback: {e}")
        # Fallback: construct URL manually
        server_url = get_bitbucket_server_url()
        https_url = f"{server_url}/scm/{project_key}/{repo_slug}.git"
        print(f"Fallback clone URL: {https_url}")
        return https_url

def clone_repository(project_key: str, repo_slug: str, destination: str = None, branch: str = None) -> bool:
    """
    Clone a repository from Bitbucket Server using client certificate authentication.
    
    Args:
        project_key: The project key (e.g., 'kubika2')
        repo_slug: The repository slug (e.g., 'kubikaos')
        destination: Local directory to clone into (optional)
        branch: Specific branch to clone (optional)
    
    Returns:
        bool: True if successful, False otherwise
    """
    
    # Test connection first
    if not test_bitbucket_connection():
        print("❌ Failed to establish connection to Bitbucket. Please check your configuration.")
        return False
    
    cert_path = None
    key_path = None
    
    try:
        # Verify the repository exists
        print(f"Checking if repository {project_key}/{repo_slug} exists...")
        repo_data = get_bitbucket_repo(project_key, repo_slug)
        print(f"✅ Repository found: {repo_data.get('name', repo_slug)}")
        
        # Set up git with certificates
        cert_path, key_path = setup_git_with_certificates()
        
        # Get clone URL
        clone_url = get_clone_url(project_key, repo_slug)
        
        # Determine destination directory
        if not destination:
            destination = repo_slug
        
        # Check if destination already exists
        if os.path.exists(destination):
            print(f"⚠️ Directory '{destination}' already exists")
            response = input("Do you want to remove it and continue? (y/N): ")
            if response.lower() != 'y':
                print("❌ Clone cancelled")
                return False
            
            # Remove existing directory
            import shutil
            shutil.rmtree(destination)
            print(f"✅ Removed existing directory: {destination}")
        
        # Prepare git clone command
        clone_cmd = ["git", "clone"]
        
        if branch:
            clone_cmd.extend(["--branch", branch])
        
        clone_cmd.extend([clone_url, destination])
        
        print(f"Cloning repository...")
        print(f"Command: {' '.join(clone_cmd)}")
        
        # Execute git clone
        result = subprocess.run(
            clone_cmd,
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            print(f"✅ Repository cloned successfully to: {os.path.abspath(destination)}")
            
            # Show some basic info about the cloned repo
            try:
                repo_path = os.path.abspath(destination)
                result = subprocess.run(
                    ["git", "log", "--oneline", "-5"],
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                if result.returncode == 0:
                    print(f"\nLast 5 commits:")
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            print(f"  {line}")
                
                # Show current branch
                result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    cwd=repo_path
                )
                if result.returncode == 0:
                    current_branch = result.stdout.strip()
                    print(f"\nCurrent branch: {current_branch}")
                    
            except Exception as e:
                print(f"⚠️ Could not get repository info: {e}")
            
            return True
        else:
            print(f"❌ Git clone failed with return code: {result.returncode}")
            print(f"Error output: {result.stderr}")
            print(f"Standard output: {result.stdout}")
            return False
            
    except Exception as e:
        print(f"❌ Clone operation failed: {str(e)}")
        return False
    
    finally:
        # Always clean up git configuration
        cleanup_git_config()
        
        # Clean up certificate files
        if cert_path and os.path.exists(cert_path):
            try:
                os.remove(cert_path)
                print(f"✅ Cleaned up certificate file: {cert_path}")
            except Exception as e:
                print(f"⚠️ Could not remove certificate file: {e}")
        
        if key_path and os.path.exists(key_path):
            try:
                os.remove(key_path)
                print(f"✅ Cleaned up key file: {key_path}")
            except Exception as e:
                print(f"⚠️ Could not remove key file: {e}")

def list_available_repos(project_key: str = None):
    """List available repositories for cloning"""
    try:
        if project_key:
            print(f"Repositories in project {project_key}:")
            repos = list_bitbucket_repos(project_key)
            for repo in repos:
                print(f"  - {repo['slug']} ({repo['name']})")
        else:
            print("Available projects:")
            projects = list_bitbucket_projects()
            for project in projects[:10]:  # Limit to first 10 projects
                print(f"  - {project['key']}: {project['name']}")
                
                # Show a few repos from each project
                try:
                    repos = list_bitbucket_repos(project['key'])
                    for repo in repos[:3]:  # Show first 3 repos
                        print(f"    - {repo['slug']}")
                    if len(repos) > 3:
                        print(f"    ... and {len(repos) - 3} more")
                except Exception as e:
                    print(f"    (Could not list repos: {e})")
                    
    except Exception as e:
        print(f"❌ Failed to list repositories: {e}")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clone repository from Bitbucket Server")
    parser.add_argument("project_key", help="Project key (e.g., EOCCJPA)")
    parser.add_argument("repo_slug", help="Repository slug (e.g., kubikaos)")
    parser.add_argument("--destination", "-d", help="Local directory to clone into (defaults to repo name)")
    parser.add_argument("--branch", "-b", help="Specific branch to clone")
    parser.add_argument("--list", "-l", action="store_true", help="List available repositories")
    
    args = parser.parse_args()
    
    if args.list:
        list_available_repos(args.project_key if args.project_key != "." else None)
        return
    
    # Validate required arguments
    if not args.project_key or not args.repo_slug:
        print("❌ Both project_key and repo_slug are required")
        parser.print_help()
        sys.exit(1)
    
    print(f"Cloning repository: {args.project_key}/{args.repo_slug}")
    if args.destination:
        print(f"Destination: {args.destination}")
    if args.branch:
        print(f"Branch: {args.branch}")
    
    success = clone_repository(
        project_key=args.project_key,
        repo_slug=args.repo_slug,
        destination=args.destination,
        branch=args.branch
    )
    
    if not success:
        print("❌ Clone operation failed")
        sys.exit(1)
    
    print("✅ Clone operation completed successfully")

if __name__ == "__main__":
    main() 