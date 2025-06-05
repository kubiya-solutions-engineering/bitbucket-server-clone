# Bitbucket Server API Functions
# This module provides functions to interact with Bitbucket Server using client certificate authentication
# Reuses the same JIRA_CLIENT_CERT and JIRA_CLIENT_KEY environment variables for certificate authentication

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

def get_bitbucket_user() -> dict:
    """Get the authenticated user information from Bitbucket"""
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
    """List all projects from Bitbucket"""
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
    """
    List repositories from Bitbucket.
    If project_key is provided, lists repos for that project.
    If not provided, lists all repos across all projects.
    """
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
    """Get information about a specific Bitbucket repository"""
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
    """Get branches for a specific Bitbucket repository"""
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
    """Get commits for a specific Bitbucket repository branch"""
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

# Example usage functions
def example_usage():
    """Example of how to use the Bitbucket functions"""
    try:
        # Test connection
        if not test_bitbucket_connection():
            logger.error("Bitbucket connection test failed")
            return
        
        # List projects
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

if __name__ == "__main__":
    example_usage() 