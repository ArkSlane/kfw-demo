import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from shared.errors import setup_all_error_handlers
from validators import (
    sanitize_path,
    validate_branch_name,
    validate_commit_message,
    validate_file_list,
    validate_repo_url,
    validate_target_dir
)
from ssh_manager import SSHKeyManager
from token_store import APITokenStore
from repo_connections_store import RepoConnectionsStore, RepoConnection
from llm_connections_store import LLMConnectionsStore

# Environment variables
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "/workspace"))
SSH_KEYS_DIR = Path(os.getenv("SSH_KEYS_DIR", "/ssh-keys"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN", "")
AZURE_DEVOPS_TOKEN = os.getenv("AZURE_DEVOPS_TOKEN", "")
AZURE_DEVOPS_ORG = os.getenv("AZURE_DEVOPS_ORG", "")

# Initialize SSH key manager
ssh_manager = SSHKeyManager(SSH_KEYS_DIR)

# Store API tokens in the same Docker volume as SSH keys (restricted perms).
api_token_store = APITokenStore(SSH_KEYS_DIR / "api-tokens")
repo_connections_store = RepoConnectionsStore(SSH_KEYS_DIR / "repo-connections")
llm_connections_store = LLMConnectionsStore(SSH_KEYS_DIR / "llm-connections")

app = FastAPI(
    title="Git Integration Service",
    version="1.0.0",
    description="""Multi-provider Git operations service with support for GitHub, GitLab, and Azure DevOps.
    
    ## Features
    - Clone, pull, push operations with validation
    - Branch management (create, checkout, list)
    - Commit operations with comprehensive validation
    - Pull/Merge request creation
    - **SSH key management** (secure storage, API-driven key operations)
    - Multi-provider support (GitHub, GitLab, Azure DevOps)
    - Security features (path traversal prevention, command injection blocking)
    
    ## Security
    - Input validation on all operations
    - Path sanitization (prevents ../ attacks)
    - Branch name validation (blocks shell metacharacters)
    - Protocol restrictions (https://, git://, and git@... SSH URLs)
    - Commit message validation (max length, encoding checks)
    - SSH key validation and secure storage (0600 permissions)
    
    ## Use Cases
    - Integrate test automation with version control
    - Create PRs/MRs for test updates
    - Store automation scripts in Git repositories
    - Use SSH keys for private repository access
    - Track test case changes over time
    - Automated test deployment workflows
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "repository", "description": "Repository operations (clone, pull, push)"},
        {"name": "branches", "description": "Branch management"},
        {"name": "commits", "description": "Commit operations"},
        {"name": "pull-requests", "description": "Pull/Merge request operations"},
        {"name": "ssh-keys", "description": "SSH key management for secure Git authentication"},
        {"name": "api-tokens", "description": "API token management for Git providers (stored as secrets)"},
        {"name": "repo-connections", "description": "Connect and sync repositories (clone/pull)"},
        {"name": "llm-connections", "description": "Remote LLM connection settings (stored as secrets)"},
        {"name": "health", "description": "Service health and status"}
    ]
)

# Setup standardized error handlers
setup_all_error_handlers(app)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DTOs
class CloneRequest(BaseModel):
    repo_url: str
    branch: str | None = None
    target_dir: str | None = None
    ssh_key_name: str | None = None  # Optional SSH key to use for clone

class BranchRequest(BaseModel):
    repo_path: str
    branch_name: str

class CommitRequest(BaseModel):
    repo_path: str
    message: str
    files: list[str] | None = None  # If None, commit all changes

class PushRequest(BaseModel):
    repo_path: str
    branch: str | None = None
    force: bool = False
    ssh_key_name: str | None = None  # Optional SSH key to use for push

class PullRequest(BaseModel):
    repo_path: str
    branch: str | None = None
    ssh_key_name: str | None = None  # Optional SSH key to use for pull

class MergeRequestCreate(BaseModel):
    repo_path: str
    source_branch: str
    target_branch: str
    title: str
    description: str | None = None
    provider: Literal["github", "gitlab", "azure"]
    api_token_id: str | None = None  # Optional: use a stored provider token instead of env vars

class MergeRequestCheckout(BaseModel):
    repo_path: str
    mr_number: int
    provider: Literal["github", "gitlab", "azure"]

class SSHKeyUpload(BaseModel):
    """Request body for uploading an SSH key."""
    key_name: str
    private_key: str
    public_key: str | None = None

class SSHKeyInfo(BaseModel):
    """Information about an SSH key."""
    key_name: str
    fingerprint: str
    has_public_key: bool
    path: str

class GitStatusRequest(BaseModel):
    repo_path: str

class FileWriteRequest(BaseModel):
    repo_path: str
    file_path: str
    content: str
    branch: str | None = None  # Optional: checkout branch before writing

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_provider_token(provider: Literal["github", "gitlab", "azure"], token_id: str | None) -> str:
    """Resolve a provider token.

    If token_id is provided, read it from the token store.
    Otherwise, fall back to environment-configured tokens.
    """
    if token_id:
        raw = api_token_store.get_raw(token_id)
        stored_provider = raw.get("provider")
        if provider == "azure":
            expected = "azureDevOps"
        else:
            expected = provider
        if stored_provider != expected:
            raise HTTPException(
                status_code=400,
                detail=f"Token provider mismatch: token is '{stored_provider}', requested provider is '{expected}'",
            )
        return api_token_store.get_token_value(token_id)

    if provider == "github":
        return GITHUB_TOKEN
    if provider == "gitlab":
        return GITLAB_TOKEN
    if provider == "azure":
        return AZURE_DEVOPS_TOKEN
    return ""

def run_git_command(args: list[str], cwd: Path | None = None, env: dict | None = None) -> tuple[str, str, int]:
    """Run a git command and return (stdout, stderr, returncode)."""
    try:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=300,
            env=merged_env,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Git command timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Git command failed: {str(e)}")


def redact_secret(text: str, secret: str) -> str:
    if not text or not secret:
        return text
    return text.replace(secret, "***")


def git_https_username_for_provider(provider: Literal["github", "gitlab", "azure"]) -> str:
    # Common, provider-specific usernames for PAT auth over HTTPS.
    if provider == "github":
        return "x-access-token"
    if provider == "gitlab":
        return "oauth2"
    if provider == "azure":
        return "pat"
    return "token"


def build_git_askpass_env(provider: Literal["github", "gitlab", "azure"], token: str) -> tuple[dict, callable]:
    """Create a temporary GIT_ASKPASS script env for HTTPS token auth.

    Returns (env_overrides, cleanup_fn).
    """
    username = git_https_username_for_provider(provider)
    # Script uses prompt text to decide whether Git asks for username or password.
    script = """#!/bin/sh
case "$1" in
  *Username*) echo "$GIT_HTTP_USERNAME";;
  *username*) echo "$GIT_HTTP_USERNAME";;
  *Password*) echo "$GIT_HTTP_PASSWORD";;
  *password*) echo "$GIT_HTTP_PASSWORD";;
  *) echo "";;
esac
"""

    fd, path = tempfile.mkstemp(prefix="git-askpass-", suffix=".sh")
    os.close(fd)
    p = Path(path)
    p.write_text(script, encoding="utf-8")
    try:
        os.chmod(p, 0o700)
    except Exception:
        pass

    env = {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": str(p),
        "GIT_HTTP_USERNAME": username,
        "GIT_HTTP_PASSWORD": token,
    }

    def cleanup():
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

    return env, cleanup

def get_repo_path(repo_path: str) -> Path:
    """Get absolute path to repository, ensure it's within workspace."""
    # Validate and sanitize the path
    path = sanitize_path(repo_path, WORKSPACE_DIR)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Repository path not found: {repo_path}")
    if not (path / ".git").exists():
        raise HTTPException(status_code=400, detail=f"Not a git repository: {repo_path}")
    return path

def parse_remote_url(repo_url: str) -> tuple[str, str, str]:
    """Parse git remote URL to determine provider, org, and repo name.
    Returns: (provider, org, repo)
    """
    if "github.com" in repo_url:
        provider = "github"
    elif "gitlab.com" in repo_url:
        provider = "gitlab"
    elif "dev.azure.com" in repo_url or "visualstudio.com" in repo_url:
        provider = "azure"
    else:
        raise HTTPException(status_code=400, detail="Unsupported Git provider")
    
    # Extract org/repo from URL
    # Example: https://github.com/org/repo.git
    parts = repo_url.rstrip("/").rstrip(".git").split("/")
    if len(parts) >= 2:
        repo = parts[-1]
        org = parts[-2]
    else:
        raise HTTPException(status_code=400, detail="Invalid repository URL format")
    
    return provider, org, repo

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": now_iso()}

@app.post("/clone")
async def clone_repository(payload: CloneRequest):
    """Clone a Git repository."""
    # Validate repo URL
    validated_url = validate_repo_url(payload.repo_url)
    
    # Configure SSH if key is provided
    if payload.ssh_key_name:
        ssh_manager.configure_git_ssh(payload.ssh_key_name)
    
    # Validate and determine target directory
    if payload.target_dir:
        target = validate_target_dir(payload.target_dir, WORKSPACE_DIR)
    else:
        # Extract repo name from URL and validate
        repo_name = Path(validated_url).stem.replace('.git', '')
        target = validate_target_dir(repo_name, WORKSPACE_DIR)
    
    if target.exists():
        raise HTTPException(status_code=400, detail=f"Target directory already exists: {target.name}")
    
    # Validate branch name if provided
    if payload.branch:
        validate_branch_name(payload.branch)
    
    args = ["clone", validated_url, str(target)]
    if payload.branch:
        args.extend(["-b", payload.branch])
    
    stdout, stderr, code = run_git_command(args)
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Clone failed: {stderr}")
    
    return {
        "success": True,
        "repo_path": target.name,
        "message": f"Repository cloned to {target.name}"
    }

@app.post("/pull")
async def pull_changes(payload: PullRequest):
    """Pull latest changes from remote."""
    repo_path = get_repo_path(payload.repo_path)
    
    # Configure SSH if key is provided
    if payload.ssh_key_name:
        ssh_manager.configure_git_ssh(payload.ssh_key_name)
    
    # Validate branch name if provided
    if payload.branch:
        validate_branch_name(payload.branch)
    
    args = ["pull"]
    if payload.branch:
        args.extend(["origin", payload.branch])
    
    stdout, stderr, code = run_git_command(args, cwd=repo_path)
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Pull failed: {stderr}")
    
    return {
        "success": True,
        "output": stdout,
        "message": "Changes pulled successfully"
    }

@app.post("/push")
async def push_changes(payload: PushRequest):
    """Push local changes to remote."""
    repo_path = get_repo_path(payload.repo_path)
    
    # Configure SSH if key is provided
    if payload.ssh_key_name:
        ssh_manager.configure_git_ssh(payload.ssh_key_name)
    
    # Validate branch name if provided
    if payload.branch:
        validate_branch_name(payload.branch)
    
    args = ["push"]
    if payload.force:
        args.append("--force")
    if payload.branch:
        args.extend(["origin", payload.branch])
    
    stdout, stderr, code = run_git_command(args, cwd=repo_path)
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Push failed: {stderr}")
    
    return {
        "success": True,
        "output": stdout,
        "message": "Changes pushed successfully"
    }

@app.post("/fetch")
async def fetch_remote(payload: GitStatusRequest):
    """Fetch updates from remote without merging."""
    repo_path = get_repo_path(payload.repo_path)
    
    stdout, stderr, code = run_git_command(["fetch", "--all"], cwd=repo_path)
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Fetch failed: {stderr}")
    
    return {
        "success": True,
        "output": stdout,
        "message": "Remote updates fetched"
    }

@app.post("/status")
async def get_status(payload: GitStatusRequest):
    """Get git status of repository."""
    repo_path = get_repo_path(payload.repo_path)
    
    stdout, stderr, code = run_git_command(["status", "--porcelain"], cwd=repo_path)
    
    # Get current branch
    branch_out, _, _ = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
    current_branch = branch_out.strip()
    
    # Parse status output
    changes = []
    for line in stdout.strip().split("\n"):
        if line:
            status = line[:2]
            file_path = line[3:]
            changes.append({"status": status.strip(), "file": file_path})
    
    return {
        "current_branch": current_branch,
        "changes": changes,
        "has_changes": len(changes) > 0
    }

@app.post("/branch/create")
async def create_branch(payload: BranchRequest):
    """Create a new branch."""
    repo_path = get_repo_path(payload.repo_path)
    
    # Validate branch name
    validated_branch = validate_branch_name(payload.branch_name)
    
    stdout, stderr, code = run_git_command(
        ["checkout", "-b", validated_branch],
        cwd=repo_path
    )
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Branch creation failed: {stderr}")
    
    return {
        "success": True,
        "branch": payload.branch_name,
        "message": f"Branch '{payload.branch_name}' created and checked out"
    }

@app.post("/branch/checkout")
async def checkout_branch(payload: BranchRequest):
    """Checkout an existing branch."""
    repo_path = get_repo_path(payload.repo_path)
    
    # Validate branch name
    validated_branch = validate_branch_name(payload.branch_name)
    
    stdout, stderr, code = run_git_command(
        ["checkout", validated_branch],
        cwd=repo_path
    )
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Checkout failed: {stderr}")
    
    return {
        "success": True,
        "branch": payload.branch_name,
        "message": f"Switched to branch '{payload.branch_name}'"
    }

@app.get("/branch/list/{repo_path}")
async def list_branches(repo_path: str):
    """List all branches."""
    repo = get_repo_path(repo_path)
    
    stdout, stderr, code = run_git_command(["branch", "-a"], cwd=repo)
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Failed to list branches: {stderr}")
    
    branches = []
    current = None
    for line in stdout.split("\n"):
        line = line.strip()
        if line:
            if line.startswith("*"):
                current = line[2:].strip()
                branches.append(current)
            else:
                branches.append(line)
    
    return {
        "branches": branches,
        "current_branch": current
    }

@app.post("/commit")
async def commit_changes(payload: CommitRequest):
    """Commit changes to the repository."""
    repo_path = get_repo_path(payload.repo_path)
    
    # Validate commit message
    validated_message = validate_commit_message(payload.message)
    
    # Add files
    if payload.files:
        # Validate all file paths
        validated_files = validate_file_list(payload.files, repo_path)
        
        for file in validated_files:
            stdout, stderr, code = run_git_command(["add", file], cwd=repo_path)
            if code != 0:
                raise HTTPException(status_code=500, detail=f"Failed to add {file}: {stderr}")
    else:
        # Add all changes
        stdout, stderr, code = run_git_command(["add", "."], cwd=repo_path)
        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to add files: {stderr}")
    
    # Commit
    stdout, stderr, code = run_git_command(
        ["commit", "-m", validated_message],
        cwd=repo_path
    )
    
    if code != 0:
        raise HTTPException(status_code=500, detail=f"Commit failed: {stderr}")
    
    return {
        "success": True,
        "message": "Changes committed successfully",
        "output": stdout
    }

@app.post("/file/write", tags=["files"])
async def write_file(payload: FileWriteRequest):
    """Write content to a file in the repository.
    
    This creates directories if they don't exist and writes the file content.
    Useful for generating test files, config files, etc.
    """
    repo_path = get_repo_path(payload.repo_path)
    
    # Checkout branch if specified
    if payload.branch:
        validated_branch = validate_branch_name(payload.branch)
        stdout, stderr, code = run_git_command(["checkout", validated_branch], cwd=repo_path)
        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to checkout branch {payload.branch}: {stderr}")
    
    # Sanitize file path to prevent traversal attacks
    file_path = sanitize_path(payload.file_path, repo_path)
    
    # Create parent directories if they don't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file
    try:
        file_path.write_text(payload.content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")
    
    # Verify file was created
    if not file_path.exists():
        raise HTTPException(status_code=500, detail="File write verification failed")
    
    return {
        "success": True,
        "file_path": str(file_path.relative_to(repo_path)),
        "size_bytes": file_path.stat().st_size,
        "message": f"File written successfully: {payload.file_path}"
    }

@app.post("/merge-request/create")
async def create_merge_request(payload: MergeRequestCreate):
    """Create a merge/pull request on the Git provider."""
    repo_path = get_repo_path(payload.repo_path)
    
    # Validate branch names
    validate_branch_name(payload.source_branch)
    validate_branch_name(payload.target_branch)
    
    # Get remote URL
    stdout, _, _ = run_git_command(["config", "--get", "remote.origin.url"], cwd=repo_path)
    remote_url = stdout.strip()
    
    provider, org, repo = parse_remote_url(remote_url)
    
    if payload.provider != provider:
        raise HTTPException(
            status_code=400,
            detail=f"Provider mismatch: repository is on {provider}, requested {payload.provider}"
        )
    
    if provider == "github":
        return await create_github_pr(org, repo, payload)
    elif provider == "gitlab":
        return await create_gitlab_mr(org, repo, payload)
    elif provider == "azure":
        return await create_azure_pr(org, repo, payload)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

@app.post("/merge-request/checkout")
async def checkout_merge_request(payload: MergeRequestCheckout):
    """Checkout a merge/pull request locally."""
    repo_path = get_repo_path(payload.repo_path)
    
    # Get remote URL
    stdout, _, _ = run_git_command(["config", "--get", "remote.origin.url"], cwd=repo_path)
    remote_url = stdout.strip()
    
    provider, org, repo = parse_remote_url(remote_url)
    
    if payload.provider != provider:
        raise HTTPException(
            status_code=400,
            detail=f"Provider mismatch: repository is on {provider}, requested {payload.provider}"
        )
    
    if provider == "github":
        # Fetch PR ref
        ref = f"pull/{payload.mr_number}/head:pr-{payload.mr_number}"
        stdout, stderr, code = run_git_command(["fetch", "origin", ref], cwd=repo_path)
        
        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to fetch PR: {stderr}")
        
        # Checkout the PR branch
        stdout, stderr, code = run_git_command(["checkout", f"pr-{payload.mr_number}"], cwd=repo_path)
        
        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to checkout PR: {stderr}")
        
        return {
            "success": True,
            "branch": f"pr-{payload.mr_number}",
            "message": f"Checked out GitHub PR #{payload.mr_number}"
        }
    
    elif provider == "gitlab":
        # Fetch MR ref
        ref = f"merge-requests/{payload.mr_number}/head:mr-{payload.mr_number}"
        stdout, stderr, code = run_git_command(["fetch", "origin", ref], cwd=repo_path)
        
        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to fetch MR: {stderr}")
        
        stdout, stderr, code = run_git_command(["checkout", f"mr-{payload.mr_number}"], cwd=repo_path)
        
        if code != 0:
            raise HTTPException(status_code=500, detail=f"Failed to checkout MR: {stderr}")
        
        return {
            "success": True,
            "branch": f"mr-{payload.mr_number}",
            "message": f"Checked out GitLab MR !{payload.mr_number}"
        }
    
    elif provider == "azure":
        raise HTTPException(
            status_code=501,
            detail="Azure DevOps PR checkout not yet implemented"
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

async def create_github_pr(org: str, repo: str, payload: MergeRequestCreate) -> dict:
    """Create a GitHub Pull Request."""
    token = get_provider_token("github", payload.api_token_id)
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token not configured")
    
    url = f"https://api.github.com/repos/{org}/{repo}/pulls"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    data = {
        "title": payload.title,
        "head": payload.source_branch,
        "base": payload.target_branch,
        "body": payload.description or ""
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}"
            )
        
        pr_data = response.json()
        
        return {
            "success": True,
            "pr_number": pr_data["number"],
            "pr_url": pr_data["html_url"],
            "message": f"Pull Request #{pr_data['number']} created successfully"
        }

async def create_gitlab_mr(org: str, repo: str, payload: MergeRequestCreate) -> dict:
    """Create a GitLab Merge Request."""
    token = get_provider_token("gitlab", payload.api_token_id)
    if not token:
        raise HTTPException(status_code=400, detail="GitLab token not configured")
    
    # Encode project path for URL
    project_path = f"{org}/{repo}".replace("/", "%2F")
    url = f"https://gitlab.com/api/v4/projects/{project_path}/merge_requests"
    headers = {
        "PRIVATE-TOKEN": token,
        "Content-Type": "application/json"
    }
    
    data = {
        "title": payload.title,
        "source_branch": payload.source_branch,
        "target_branch": payload.target_branch,
        "description": payload.description or ""
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitLab API error: {response.text}"
            )
        
        mr_data = response.json()
        
        return {
            "success": True,
            "mr_number": mr_data["iid"],
            "mr_url": mr_data["web_url"],
            "message": f"Merge Request !{mr_data['iid']} created successfully"
        }

async def create_azure_pr(org: str, repo: str, payload: MergeRequestCreate) -> dict:
    """Create an Azure DevOps Pull Request."""
    token = get_provider_token("azure", payload.api_token_id)
    if not token or not AZURE_DEVOPS_ORG:
        raise HTTPException(status_code=400, detail="Azure DevOps credentials not configured")
    
    # Azure DevOps API requires project name, which we need to extract or configure
    # For now, return not implemented
    raise HTTPException(
        status_code=501,
        detail="Azure DevOps PR creation not yet fully implemented. Configure AZURE_DEVOPS_ORG and project name."
    )


# === SSH Key Management Endpoints ===

@app.post(
    "/ssh-keys",
    tags=["ssh-keys"],
    summary="Upload SSH key",
    description="""Upload an SSH key for Git authentication.
    
    The key will be securely stored with 0600 permissions and can be used for:
    - Cloning private repositories
    - Pushing/pulling with SSH authentication
    - Accessing Git providers without HTTPS tokens
    
    **Security:**
    - Private keys are stored with 0600 permissions (owner read/write only)
    - Keys are validated using ssh-keygen before storage
    - Invalid keys are rejected and not stored
    
    **Key Name Requirements:**
    - Alphanumeric characters, underscores, and hyphens only
    - Used as filename and identifier
    - Must be unique
    
    **Example:**
    ```json
    {
        "key_name": "github_deploy",
        "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\\n...\\n-----END OPENSSH PRIVATE KEY-----",
        "public_key": "ssh-rsa AAAAB3Nza..."
    }
    ```
    """,
    responses={
        200: {
            "description": "SSH key uploaded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "key_name": "github_deploy",
                        "fingerprint": "2048 SHA256:abc123... (RSA)",
                        "has_public_key": True,
                        "path": "/ssh-keys/github_deploy"
                    }
                }
            }
        },
        400: {
            "description": "Invalid key format or name",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid private key format. Must be PEM format starting with -----BEGIN"}
                }
            }
        },
        409: {
            "description": "Key already exists",
            "content": {
                "application/json": {
                    "example": {"detail": "SSH key 'github_deploy' already exists"}
                }
            }
        }
    }
)
async def upload_ssh_key(payload: SSHKeyUpload):
    """Upload and store an SSH key for Git operations."""
    return ssh_manager.add_key(
        key_name=payload.key_name,
        private_key=payload.private_key,
        public_key=payload.public_key
    )


@app.get(
    "/ssh-keys",
    tags=["ssh-keys"],
    summary="List SSH keys",
    description="""List all stored SSH keys.
    
    Returns information about each stored key including:
    - Key name (identifier)
    - Key fingerprint
    - Whether public key is available
    - Storage path
    
    **Use Cases:**
    - Verify which keys are available
    - Check key fingerprints before use
    - Audit stored keys
    
    **Example Response:**
    ```json
    [
        {
            "key_name": "github_deploy",
            "fingerprint": "2048 SHA256:abc123... (RSA)",
            "has_public_key": true,
            "path": "/ssh-keys/github_deploy"
        },
        {
            "key_name": "gitlab_automation",
            "fingerprint": "4096 SHA256:def456... (RSA)",
            "has_public_key": false,
            "path": "/ssh-keys/gitlab_automation"
        }
    ]
    ```
    """,
    responses={
        200: {
            "description": "List of SSH keys",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "key_name": "github_deploy",
                            "fingerprint": "2048 SHA256:abc123... (RSA)",
                            "has_public_key": True,
                            "path": "/ssh-keys/github_deploy"
                        }
                    ]
                }
            }
        }
    }
)
async def list_ssh_keys():
    """List all stored SSH keys."""
    return ssh_manager.list_keys()


@app.get(
    "/ssh-keys/{key_name}",
    tags=["ssh-keys"],
    summary="Get SSH key details",
    description="""Get detailed information about a specific SSH key.
    
    Returns:
    - Key name and fingerprint
    - Public key content (if available)
    - Storage path
    
    **Note:** Private key content is never returned for security reasons.
    Only the public key (if stored) is included in the response.
    
    **Example Response:**
    ```json
    {
        "key_name": "github_deploy",
        "fingerprint": "2048 SHA256:abc123... (RSA)",
        "has_public_key": true,
        "public_key": "ssh-rsa AAAAB3NzaC1yc2...",
        "path": "/ssh-keys/github_deploy"
    }
    ```
    """,
    responses={
        200: {
            "description": "SSH key details",
            "content": {
                "application/json": {
                    "example": {
                        "key_name": "github_deploy",
                        "fingerprint": "2048 SHA256:abc123... (RSA)",
                        "has_public_key": True,
                        "public_key": "ssh-rsa AAAAB3NzaC1yc2...",
                        "path": "/ssh-keys/github_deploy"
                    }
                }
            }
        },
        404: {
            "description": "SSH key not found",
            "content": {
                "application/json": {
                    "example": {"detail": "SSH key 'unknown_key' not found"}
                }
            }
        }
    }
)
async def get_ssh_key(key_name: str):
    """Get information about a specific SSH key."""
    return ssh_manager.get_key(key_name)


@app.delete(
    "/ssh-keys/{key_name}",
    tags=["ssh-keys"],
    summary="Delete SSH key",
    description="""Delete an SSH key from storage.
    
    This will permanently remove both the private key and public key (if present).
    
    **Warning:** This operation cannot be undone. Make sure you have a backup
    of the key if needed.
    
    **Example Response:**
    ```json
    {
        "key_name": "github_deploy",
        "deleted": true
    }
    ```
    """,
    responses={
        200: {
            "description": "SSH key deleted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "key_name": "github_deploy",
                        "deleted": True
                    }
                }
            }
        },
        404: {
            "description": "SSH key not found",
            "content": {
                "application/json": {
                    "example": {"detail": "SSH key 'unknown_key' not found"}
                }
            }
        }
    }
)
async def delete_ssh_key(key_name: str):
    """Delete an SSH key from storage."""
    return ssh_manager.delete_key(key_name)


# === API Token Management Endpoints ===


class APITokenCreate(BaseModel):
    provider: Literal["github", "gitlab", "azureDevOps"]
    name: str
    token: str
    azure_org: str | None = None


class APITokenInfo(BaseModel):
    id: str
    provider: Literal["github", "gitlab", "azureDevOps"]
    name: str
    created_at: str
    token_masked: str
    azure_org: str | None = None


@app.get(
    "/api-tokens",
    tags=["api-tokens"],
    summary="List stored API tokens",
    description="""List stored provider API tokens.

Tokens are stored as secrets in the git service volume and are never returned in full.
""",
)
async def list_api_tokens() -> list[APITokenInfo]:
    return [t.__dict__ for t in api_token_store.list()]


@app.post(
    "/api-tokens",
    tags=["api-tokens"],
    summary="Store an API token",
    description="""Store a provider API token as a secret.

The token value is never returned; the response contains only metadata.
""",
)
async def create_api_token(payload: APITokenCreate) -> APITokenInfo:
    created = api_token_store.create(
        provider=payload.provider,
        name=payload.name,
        token=payload.token,
        azure_org=payload.azure_org,
    )
    return created.__dict__


@app.delete(
    "/api-tokens/{token_id}",
    tags=["api-tokens"],
    summary="Delete an API token",
)
async def delete_api_token(token_id: str):
    api_token_store.delete(token_id)
    return {"id": token_id, "deleted": True}


# === Repo Connections Endpoints ===


class RepoConnectionCreate(BaseModel):
    repo_url: str
    branch: str | None = None
    target_dir: str | None = None
    ssh_key_name: str | None = None
    api_token_id: str | None = None


class RepoConnectionInfo(BaseModel):
    id: str
    repo_url: str
    provider: Literal["github", "gitlab", "azureDevOps", "unknown"]
    repo_path: str
    created_at: str
    last_synced_at: str | None = None
    status: str
    auth_type: Literal["api-token", "ssh-key", "none"]
    api_token_id: str | None = None
    ssh_key_name: str | None = None
    branch: str | None = None


def provider_from_repo_url(repo_url: str) -> Literal["github", "gitlab", "azure", "unknown"]:
    url = (repo_url or "").lower()
    if "github.com" in url:
        return "github"
    if "gitlab.com" in url:
        return "gitlab"
    if "dev.azure.com" in url or "visualstudio.com" in url:
        return "azure"
    return "unknown"


@app.get(
    "/repo-connections",
    tags=["repo-connections"],
    summary="List repo connections",
)
async def list_repo_connections() -> list[RepoConnectionInfo]:
    return [c.__dict__ for c in repo_connections_store.list()]


@app.post(
    "/repo-connections",
    tags=["repo-connections"],
    summary="Connect repo (clone)",
    description="""Clone a repository into the git service workspace and store a connection record.

Auth:
- Prefer `ssh_key_name` (uses existing SSH key management).
- Or specify `api_token_id` to use a stored provider token over HTTPS via GIT_ASKPASS.
""",
)
async def connect_repo(payload: RepoConnectionCreate) -> RepoConnectionInfo:
    if payload.ssh_key_name and payload.api_token_id:
        raise HTTPException(status_code=400, detail="Provide either ssh_key_name or api_token_id, not both")

    validated_url = validate_repo_url(payload.repo_url)
    provider = provider_from_repo_url(validated_url)
    if provider == "unknown":
        raise HTTPException(status_code=400, detail="Unsupported Git provider")

    if payload.branch:
        validate_branch_name(payload.branch)

    if payload.target_dir:
        target = validate_target_dir(payload.target_dir, WORKSPACE_DIR)
    else:
        repo_name = Path(validated_url).stem.replace(".git", "")
        target = validate_target_dir(repo_name, WORKSPACE_DIR)

    if target.exists():
        raise HTTPException(status_code=400, detail=f"Target directory already exists: {target.name}")

    env = None
    cleanup = None
    auth_type: Literal["api-token", "ssh-key", "none"] = "none"

    try:
        if payload.ssh_key_name:
            ssh_manager.configure_git_ssh(payload.ssh_key_name)
            auth_type = "ssh-key"
        elif payload.api_token_id:
            token = get_provider_token(provider, payload.api_token_id)
            if not token:
                raise HTTPException(status_code=400, detail="Provider token not configured")
            env, cleanup = build_git_askpass_env(provider, token)
            auth_type = "api-token"

        args = ["clone", validated_url, str(target)]
        if payload.branch:
            args.extend(["-b", payload.branch])

        stdout, stderr, code = run_git_command(args, env=env)
        if code != 0:
            # Best-effort redaction if git prints the token anywhere.
            if payload.api_token_id:
                try:
                    secret = api_token_store.get_token_value(payload.api_token_id)
                    stderr = redact_secret(stderr, secret)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=f"Clone failed: {stderr}")

        # Ensure origin URL is stored without credentials.
        run_git_command(["remote", "set-url", "origin", validated_url], cwd=target)

        provider_label = "azureDevOps" if provider == "azure" else provider
        conn = repo_connections_store.create(
            repo_url=validated_url,
            provider=provider_label,
            repo_path=target.name,
            auth_type=auth_type,
            api_token_id=payload.api_token_id,
            ssh_key_name=payload.ssh_key_name,
            branch=payload.branch,
        )
        return conn.__dict__
    finally:
        if cleanup:
            cleanup()


@app.post(
    "/repo-connections/{connection_id}/sync",
    tags=["repo-connections"],
    summary="Sync repo (pull)",
)
async def sync_repo_connection(connection_id: str) -> RepoConnectionInfo:
    conn = repo_connections_store.get(connection_id)
    repo_path = get_repo_path(conn.repo_path)

    env = None
    cleanup = None
    try:
        if conn.ssh_key_name:
            ssh_manager.configure_git_ssh(conn.ssh_key_name)
        elif conn.api_token_id:
            provider = provider_from_repo_url(conn.repo_url)
            token = get_provider_token(provider, conn.api_token_id)
            if not token:
                raise HTTPException(status_code=400, detail="Provider token not configured")
            env, cleanup = build_git_askpass_env(provider, token)

        args = ["pull"]
        if conn.branch:
            validate_branch_name(conn.branch)
            args.extend(["origin", conn.branch])

        stdout, stderr, code = run_git_command(args, cwd=repo_path, env=env)
        if code != 0:
            if conn.api_token_id:
                try:
                    secret = api_token_store.get_token_value(conn.api_token_id)
                    stderr = redact_secret(stderr, secret)
                except Exception:
                    pass
            raise HTTPException(status_code=500, detail=f"Pull failed: {stderr}")

        updated = RepoConnection(
            **{
                **conn.__dict__,
                "last_synced_at": now_iso(),
                "status": "synced",
            }
        )
        repo_connections_store.update(updated)
        return updated.__dict__
    finally:
        if cleanup:
            cleanup()


@app.delete(
    "/repo-connections/{connection_id}",
    tags=["repo-connections"],
    summary="Disconnect repo",
    description="Deletes the connection record. Does not delete the local checkout.",
)
async def disconnect_repo(connection_id: str):
    repo_connections_store.delete(connection_id)
    return {"id": connection_id, "deleted": True}


# === LLM Connections Endpoints ===


class LLMConnectionCreate(BaseModel):
    provider: Literal["openai", "azure", "aws", "google", "other"]
    name: str
    base_url: str
    api_key: str
    default_model: str | None = None


class LLMConnectionInfo(BaseModel):
    id: str
    provider: Literal["openai", "azure", "aws", "google", "other"]
    name: str
    base_url: str
    default_model: str | None = None
    created_at: str
    api_key_masked: str


@app.get(
    "/llm-connections",
    tags=["llm-connections"],
    summary="List stored LLM connections",
    description="Lists remote LLM connection settings. API keys are never returned.",
)
async def list_llm_connections() -> list[LLMConnectionInfo]:
    return [c.__dict__ for c in llm_connections_store.list()]


@app.post(
    "/llm-connections",
    tags=["llm-connections"],
    summary="Create LLM connection",
    description="Stores a remote LLM connection configuration as a secret. API key is never returned.",
)
async def create_llm_connection(payload: LLMConnectionCreate) -> LLMConnectionInfo:
    created = llm_connections_store.create(
        provider=payload.provider,
        name=payload.name,
        base_url=payload.base_url,
        api_key=payload.api_key,
        default_model=payload.default_model,
    )
    return created.__dict__


@app.delete(
    "/llm-connections/{connection_id}",
    tags=["llm-connections"],
    summary="Delete LLM connection",
)
async def delete_llm_connection(connection_id: str):
    llm_connections_store.delete(connection_id)
    return {"id": connection_id, "deleted": True}

