# Bitbucket Server API Functions
# This module provides functions to interact with Bitbucket Server using client certificate authentication
# Reuses the same JIRA_CLIENT_CERT and JIRA_CLIENT_KEY environment variables for certificate authentication

# NOTE: For this customer setup (Audi), REST API access is restricted. 
# Use Git HTTPS transport for repository operations instead.
# Only basic connection testing works via REST API.

import os
import logging
import requests
from requests.exceptions import HTTPError
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_bitbucket_server_url() -> str:
    """Get the Bitbucket server URL from environment (defaults to api.cip.audi.de/bitbucket for this customer)"""
    server_url = os.getenv("BITBUCKET_SERVER_URL", "https://api.cip.audi.de/bitbucket")
    url = server_url.rstrip('/')  # Remove trailing slash if present
    logger.info(f"Using Bitbucket server URL: {url}")
    return url

def get_bitbucket_headers() -> dict:
    """Get basic headers for Bitbucket API requests"""
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Bitbucket-Client-Cert-Tool"
    }

def setup_client_cert_files():
    """
    Gets client certificate and key from environment variables and writes them to files.
    Returns tuple of (cert_path, key_path).
    Reuses the same JIRA_CLIENT_CERT and JIRA_CLIENT_KEY environment variables.
    """
    logger.info("Setting up client certificate files for Bitbucket...")
    
    # Get certificate and key content from environment variables (same as Jira)
    CLIENT_CERT = os.getenv("JIRA_CLIENT_CERT")
    CLIENT_KEY = os.getenv("JIRA_CLIENT_KEY")

    if not CLIENT_CERT or not CLIENT_KEY:
        raise ValueError("JIRA_CLIENT_CERT and JIRA_CLIENT_KEY environment variables must be set")

    # Log certificate details (safely)
    logger.info("Certificate validation:")
    logger.info(f"Certificate length: {len(CLIENT_CERT)} characters")
    logger.info(f"Private key length: {len(CLIENT_KEY)} characters")
    logger.info(f"Certificate starts with: {CLIENT_CERT[:25]}...")
    logger.info(f"Private key starts with: {CLIENT_KEY[:25]}...")

    # Create temporary paths for the cert files
    cert_path = "/tmp/bitbucket_client.crt"
    key_path = "/tmp/bitbucket_client.key"

    # Write the certificates to files
    try:
        # Ensure the certificate content is properly formatted
        if "BEGIN CERTIFICATE" not in CLIENT_CERT:
            logger.info("Adding certificate markers")
            CLIENT_CERT = f"-----BEGIN CERTIFICATE-----\n{CLIENT_CERT}\n-----END CERTIFICATE-----"
        if "BEGIN PRIVATE KEY" not in CLIENT_KEY:
            logger.info("Adding private key markers")
            CLIENT_KEY = f"-----BEGIN PRIVATE KEY-----\n{CLIENT_KEY}\n-----END PRIVATE KEY-----"

        logger.info(f"Writing certificate to: {cert_path}")
        with open(cert_path, 'w') as f:
            f.write(CLIENT_CERT)
        
        logger.info(f"Writing private key to: {key_path}")
        with open(key_path, 'w') as f:
            f.write(CLIENT_KEY)

        # Set proper permissions
        os.chmod(cert_path, 0o644)
        os.chmod(key_path, 0o600)

        # Verify files exist and have content
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            raise ValueError("Certificate files were not created properly")
        
        cert_size = os.path.getsize(cert_path)
        key_size = os.path.getsize(key_path)
        logger.info(f"Certificate file size: {cert_size} bytes")
        logger.info(f"Private key file size: {key_size} bytes")
        
        if cert_size == 0 or key_size == 0:
            raise ValueError("Certificate files are empty")

        # Read back files to verify content
        with open(cert_path, 'r') as f:
            cert_content = f.read()
            logger.info(f"Certificate file contains BEGIN/END markers: {('BEGIN CERTIFICATE' in cert_content)} / {('END CERTIFICATE' in cert_content)}")
        
        with open(key_path, 'r') as f:
            key_content = f.read()
            logger.info(f"Key file contains BEGIN/END markers: {('BEGIN PRIVATE KEY' in key_content)} / {('END PRIVATE KEY' in key_content)}")

        return cert_path, key_path

    except Exception as e:
        logger.error(f"Error setting up certificate files: {str(e)}")
        raise

def test_bitbucket_connection():
    """Test the Bitbucket connection with current client certificate"""
    try:
        logger.info("\n=== Testing Bitbucket Connection ===")
        server_url = get_bitbucket_server_url()
        cert_path, key_path = setup_client_cert_files()
        
        # Try to access the application properties endpoint (basic info endpoint)
        test_url = f"{server_url}/rest/api/1.0/application-properties"
        logger.info(f"Testing connection to: {test_url}")
        
        headers = get_bitbucket_headers()
        logger.info(f"Request headers: {headers}")
        
        logger.info("Making test request...")
        response = requests.get(
            test_url,
            headers=headers,
            cert=(cert_path, key_path),
            verify=False  # Typically self-signed cert for internal Bitbucket
        )
        
        logger.info(f"Response status code: {response.status_code}")
        logger.info(f"Response headers: {dict(response.headers)}")
        
        if response.status_code == 401:
            logger.error("Authentication failed (401)")
            logger.error(f"Response body: {response.text}")
            try:
                error_details = response.json()
                logger.error(f"Error details: {json.dumps(error_details, indent=2)}")
            except:
                logger.error("Could not parse error response as JSON")
        
        if response.status_code == 200:
            logger.info("Successfully connected to Bitbucket!")
            try:
                app_data = response.json()
                logger.info(f"Bitbucket version: {app_data.get('version', 'N/A')}")
                logger.info(f"Display name: {app_data.get('displayName', 'N/A')}")
            except:
                logger.info("Connected but couldn't parse application properties")
            return True
        else:
            logger.error(f"Failed to connect. Status code: {response.status_code}")
            logger.error(f"Response body: {response.text}")
            return False
            
    except requests.exceptions.SSLError as e:
        logger.error("SSL Error occurred:")
        logger.error(str(e))
        if "certificate verify failed" in str(e):
            logger.error("Certificate verification failed. This might indicate an issue with the certificate format or content.")
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection Error occurred:")
        logger.error(str(e))
        return False
    except Exception as e:
        logger.error(f"Connection test failed with exception: {str(e)}")
        return False

# ============================================================================
# REST API FUNCTIONS (RESTRICTED FOR THIS CUSTOMER)
# ============================================================================
# The following functions use REST API endpoints that are restricted for this
# customer setup. They are kept for compatibility but will likely return 401 errors.
# Use Git HTTPS transport operations instead for actual repository work.

def get_bitbucket_user() -> dict:
    """Get the authenticated user information from Bitbucket 
    WARNING: REST API access is restricted for this customer"""
    server_url = get_bitbucket_server_url()
    user_url = f"{server_url}/rest/api/1.0/users?filter={{0}}"  # Get current user - will need to be adjusted based on auth
    cert_path, key_path = setup_client_cert_files()

    try:
        response = requests.get(
            f"{server_url}/rest/api/1.0/users",
            cert=(cert_path, key_path),
            headers=get_bitbucket_headers(),
            verify=False,  # Likely self-signed cert for internal server
            params={"limit": 1}  # Just get one user to test
        )
        response.raise_for_status()
        
        user_data = response.json()
        logger.info(f"Successfully retrieved user data")
        return user_data
            
    except HTTPError as e:
        logger.error(f"Failed to get user data: {e}")
        raise RuntimeError(f"Failed to get user data: {e}")

def list_bitbucket_projects() -> list:
    """List all projects from Bitbucket
    WARNING: REST API access is restricted for this customer"""
    server_url = get_bitbucket_server_url()
    cert_path, key_path = setup_client_cert_files()
    projects_url = f"{server_url}/rest/api/1.0/projects"

    try:
        response = requests.get(
            projects_url,
            cert=(cert_path, key_path),
            headers=get_bitbucket_headers(),
            verify=False
        )
        response.raise_for_status()
        
        projects_data = response.json()
        projects = projects_data.get('values', [])
        logger.info(f"Successfully retrieved {len(projects)} projects")
        return projects
            
    except HTTPError as e:
        logger.error(f"Failed to list projects: {e}")
        raise RuntimeError(f"Failed to list projects: {e}")

def list_bitbucket_repos(project_key: str = None) -> list:
    """List repositories from Bitbucket
    WARNING: REST API access is restricted for this customer"""
    server_url = get_bitbucket_server_url()
    cert_path, key_path = setup_client_cert_files()
    
    if project_key:
        repos_url = f"{server_url}/rest/api/1.0/projects/{project_key}/repos"
        logger.info(f"Listing repositories for project: {project_key}")
    else:
        repos_url = f"{server_url}/rest/api/1.0/repos"
        logger.info("Listing all repositories")

    try:
        response = requests.get(
            repos_url,
            cert=(cert_path, key_path),
            headers=get_bitbucket_headers(),
            verify=False
        )
        response.raise_for_status()
        
        repos_data = response.json()
        repos = repos_data.get('values', [])
        logger.info(f"Successfully retrieved {len(repos)} repositories")
        return repos
            
    except HTTPError as e:
        logger.error(f"Failed to list repositories: {e}")
        raise RuntimeError(f"Failed to list repositories: {e}")

def get_bitbucket_repo(project_key: str, repo_slug: str) -> dict:
    """Get information about a specific Bitbucket repository
    WARNING: REST API access is restricted for this customer"""
    server_url = get_bitbucket_server_url()
    repo_url = f"{server_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}"
    cert_path, key_path = setup_client_cert_files()

    try:
        response = requests.get(
            repo_url,
            cert=(cert_path, key_path),
            headers=get_bitbucket_headers(),
            verify=False
        )
        response.raise_for_status()
        
        repo_data = response.json()
        logger.info(f"Successfully retrieved repository data for: {project_key}/{repo_slug}")
        return repo_data
            
    except HTTPError as e:
        logger.error(f"Failed to get repository data: {e}")
        raise RuntimeError(f"Failed to get repository data: {e}")

def get_bitbucket_branches(project_key: str, repo_slug: str) -> list:
    """Get branches for a specific Bitbucket repository
    WARNING: REST API access is restricted for this customer"""
    server_url = get_bitbucket_server_url()
    branches_url = f"{server_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/branches"
    cert_path, key_path = setup_client_cert_files()

    try:
        response = requests.get(
            branches_url,
            cert=(cert_path, key_path),
            headers=get_bitbucket_headers(),
            verify=False
        )
        response.raise_for_status()
        
        branches_data = response.json()
        branches = branches_data.get('values', [])
        logger.info(f"Successfully retrieved {len(branches)} branches for: {project_key}/{repo_slug}")
        return branches
            
    except HTTPError as e:
        logger.error(f"Failed to get branches: {e}")
        raise RuntimeError(f"Failed to get branches: {e}")

def get_bitbucket_commits(project_key: str, repo_slug: str, branch: str = "master", limit: int = 25) -> list:
    """Get commits for a specific Bitbucket repository branch
    WARNING: REST API access is restricted for this customer"""
    server_url = get_bitbucket_server_url()
    commits_url = f"{server_url}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/commits"
    cert_path, key_path = setup_client_cert_files()

    params = {
        "until": branch,
        "limit": limit
    }

    try:
        response = requests.get(
            commits_url,
            cert=(cert_path, key_path),
            headers=get_bitbucket_headers(),
            params=params,
            verify=False
        )
        response.raise_for_status()
        
        commits_data = response.json()
        commits = commits_data.get('values', [])
        logger.info(f"Successfully retrieved {len(commits)} commits for: {project_key}/{repo_slug} ({branch})")
        return commits
            
    except HTTPError as e:
        logger.error(f"Failed to get commits: {e}")
        raise RuntimeError(f"Failed to get commits: {e}")

# ============================================================================
# EXAMPLE USAGE (FOR REFERENCE ONLY)
# ============================================================================

def example_usage():
    """Example of how to use the Bitbucket functions (REST API functions likely won't work)"""
    try:
        # Test connection
        if not test_bitbucket_connection():
            logger.error("Bitbucket connection test failed")
            return
        
        # List projects (likely to fail with 401)
        projects = list_bitbucket_projects()
        print(f"Found {len(projects)} projects")
        for project in projects[:3]:  # Show first 3
            print(f"  - {project['key']}: {project['name']}")
            
            # List repos in this project
            repos = list_bitbucket_repos(project['key'])
            for repo in repos[:2]:  # Show first 2 repos per project
                print(f"    - {repo['slug']} ({repo['scmId']})")
        
    except Exception as e:
        logger.error(f"Example usage failed: {e}")

def setup_git_with_dual_auth():
    """
    Set up Git to handle dual authentication: client certificates + basic auth.
    This addresses the specific issue where Bitbucket requires both SSL client certificates
    and username/password authentication.
    """
    import subprocess
    import tempfile
    import os
    
    # Set up client certificates
    cert_path, key_path = setup_client_cert_files()
    server_url = get_bitbucket_server_url()
    domain = "api.cip.audi.de"
    
    # Try to get user credentials from environment
    user_email = os.getenv("KUBIYA_USER_EMAIL", "")
    user_creds = os.getenv("JIRA_USER_CREDS", "")  # Format: "username:password"
    
    logger.info("Setting up Git with dual authentication (client cert + basic auth)")
    logger.info(f"User email from env: {user_email}")
    logger.info(f"User credentials available: {bool(user_creds)}")
    
    # Parse user credentials if available
    username, password = "", ""
    if user_creds and ":" in user_creds:
        try:
            username, password = user_creds.split(":", 1)
            logger.info(f"Parsed username: {username}")
        except:
            logger.warning("Could not parse JIRA_USER_CREDS")
    elif user_email:
        # Use email as username if no explicit credentials
        username = user_email.split("@")[0] if "@" in user_email else user_email
        logger.info(f"Using email-derived username: {username}")
    
    # Configure Git with client certificates
    git_configs = [
        # Global SSL certificate configuration
        ["git", "config", "--global", "http.sslCert", cert_path],
        ["git", "config", "--global", "http.sslKey", key_path],
        ["git", "config", "--global", "http.sslVerify", "false"],
        ["git", "config", "--global", "http.sslCertPasswordProtected", "false"],
        
        # Domain-specific configuration
        ["git", "config", "--global", f"http.https://{domain}/.sslCert", cert_path],
        ["git", "config", "--global", f"http.https://{domain}/.sslKey", key_path],
        ["git", "config", "--global", f"http.https://{domain}/.sslVerify", "false"],
        
        # Server-specific configuration  
        ["git", "config", "--global", f"http.{server_url}.sslCert", cert_path],
        ["git", "config", "--global", f"http.{server_url}.sslKey", key_path],
        ["git", "config", "--global", f"http.{server_url}.sslVerify", "false"],
        
        # HTTP settings
        ["git", "config", "--global", "http.followRedirects", "true"],
        ["git", "config", "--global", "http.userAgent", "git/kubiya-dual-auth"],
    ]
    
    for cmd in git_configs:
        subprocess.run(cmd, capture_output=True, text=True)
    
    # Create a credential helper if we have username/password
    if username and password:
        logger.info("Creating credential helper for basic authentication")
        
        # Create credential helper script
        credential_helper_content = f"""#!/bin/bash
# Credential helper for Bitbucket dual authentication
if [ "$1" = "get" ]; then
    echo "username={username}"
    echo "password={password}"
fi
"""
        
        credential_helper_path = "/tmp/git-credential-bitbucket"
        with open(credential_helper_path, 'w') as f:
            f.write(credential_helper_content)
        os.chmod(credential_helper_path, 0o755)
        
        # Configure Git to use the credential helper
        subprocess.run([
            "git", "config", "--global", "credential.helper", 
            f"!{credential_helper_path}"
        ], capture_output=True, text=True)
        
        logger.info("Credential helper configured")
        return cert_path, key_path, username, password
    else:
        logger.warning("No username/password available - Git may fail with 401")
        return cert_path, key_path, None, None

def test_git_dual_auth(project_key, repo_slug):
    """
    Test Git access with dual authentication setup
    """
    server_url = get_bitbucket_server_url()
    git_url = f"{server_url}/scm/{project_key}/{repo_slug}.git"
    
    logger.info(f"Testing Git dual authentication for {project_key}/{repo_slug}")
    logger.info(f"Git URL: {git_url}")
    
    try:
        # Set up dual authentication
        cert_path, key_path, username, password = setup_git_with_dual_auth()
        
        # Prepare environment
        git_env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_SSL_NO_VERIFY": "1",
            "GIT_SSL_CERT": cert_path,
            "GIT_SSL_KEY": key_path,
        }
        
        if username and password:
            # Add credentials to URL for this test
            auth_url = git_url.replace("https://", f"https://{username}:{password}@")
            logger.info("Testing with embedded credentials in URL")
            
            result = subprocess.run(
                ["git", "ls-remote", "--heads", auth_url],
                capture_output=True,
                text=True,
                timeout=30,
                env=git_env
            )
        else:
            logger.info("Testing without credentials (will likely fail)")
            result = subprocess.run(
                ["git", "ls-remote", "--heads", git_url],
                capture_output=True,
                text=True,
                timeout=30,
                env=git_env
            )
        
        if result.returncode == 0:
            branches = result.stdout.strip().split('\n') if result.stdout.strip() else []
            logger.info(f"Success! Found {len(branches)} branches")
            return True, branches
        else:
            logger.error(f"Git failed: {result.stderr}")
            if "401" in result.stderr:
                logger.error("Still receiving 401 - check credentials or server configuration")
            return False, []
            
    except Exception as e:
        logger.error(f"Git dual auth test failed: {e}")
        return False, []

if __name__ == "__main__":
    example_usage() 