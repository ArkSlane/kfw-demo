# Git Integration Service

## Overview

The Git Integration Service provides a unified REST API for managing Git operations and integrating with popular Git hosting platforms (GitHub, GitLab, Azure DevOps). It enables automated repository management, branch operations, commits, and merge/pull request creation directly from your testing workflow.

## What the Service Does

### Core Capabilities

1. **Repository Management**
   - Clone repositories from any Git provider
   - Manage local repository state
   - Track working directory changes

2. **Branch Operations**
   - Create new branches
   - Checkout existing branches
   - List all branches (local and remote)
   - Switch between branches seamlessly

3. **Version Control Operations**
   - Pull latest changes from remote
   - Push local commits to remote
   - Fetch remote updates
   - Commit changes with custom messages
   - Check repository status

4. **Pull/Merge Request Management**
   - Create PRs on GitHub
   - Create MRs on GitLab
   - Create PRs on Azure DevOps
   - Checkout PR/MR branches locally
   - Review and test PRs before merging

5. **Multi-Provider Support**
   - GitHub (via GitHub REST API)
   - GitLab (via GitLab API)
   - Azure DevOps (via Azure DevOps REST API)

## Architecture

```
┌───────────────────────────────────────────────────────┐
│           Git Integration Service                     │
│                                                       │
│  ┌─────────────────────────────────────────────────┐ │
│  │              FastAPI Server                     │ │
│  │              (Port 8007)                        │ │
│  └──────────────┬──────────────────────────────────┘ │
│                 │                                     │
│  ┌──────────────▼──────────────────────────────────┐ │
│  │          Git Command Executor                   │ │
│  │   (clone, pull, push, commit, branch, etc.)    │ │
│  └──────────────┬──────────────────────────────────┘ │
│                 │                                     │
│  ┌──────────────▼──────────────────────────────────┐ │
│  │       Workspace: /workspace                     │ │
│  │       - Cloned repositories                     │ │
│  │       - Working directories                     │ │
│  │       - Git metadata                            │ │
│  └─────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
    ┌─────────┐       ┌─────────┐       ┌─────────┐
    │ GitHub  │       │ GitLab  │       │ Azure   │
    │   API   │       │   API   │       │ DevOps  │
    └─────────┘       └─────────┘       └─────────┘
```

## Technology Stack

- **Framework**: FastAPI (Python 3.11)
- **Git Client**: Git CLI (via subprocess)
- **HTTP Client**: httpx (async)
- **Storage**: Docker volume for workspace

## Use Cases

### 1. Automated Test Result Commits

```
Test Execution → Generate Report → Commit to Git → Push to Branch
```

### 2. CI/CD Integration

```
Create Feature Branch → Run Tests → Create PR if Tests Pass
```

### 3. Test Case Synchronization

```
Pull Latest Test Cases → Run Tests → Commit Results → Push Updates
```

### 4. Automated PR Creation

```
Generate Automation Scripts → Commit to Branch → Create PR for Review
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WORKSPACE_DIR` | No | `/workspace` | Base directory for cloned repositories |
| `GITHUB_TOKEN` | No | - | Personal access token for GitHub API |
| `GITLAB_TOKEN` | No | - | Personal access token for GitLab API |
| `AZURE_DEVOPS_TOKEN` | No | - | Personal access token for Azure DevOps |
| `AZURE_DEVOPS_ORG` | No | - | Azure DevOps organization name |

### Setting Up Tokens

#### GitHub Token

1. Go to Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Select scopes: `repo`, `workflow`
4. Copy token and add to `.env`:
   ```
   GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

#### GitLab Token

1. Go to User Settings → Access Tokens
2. Create personal access token
3. Select scopes: `api`, `write_repository`
4. Copy token and add to `.env`:
   ```
   GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
   ```

#### Azure DevOps Token

1. Go to User settings → Personal access tokens
2. Create new token
3. Select scopes: `Code (Read & Write)`, `Pull Request Threads (Read & Write)`
4. Copy token and add to `.env`:
   ```
   AZURE_DEVOPS_TOKEN=xxxxxxxxxxxxxxxxxxxx
   AZURE_DEVOPS_ORG=your-org-name
   ```

## Endpoints

### Base URL
```
http://localhost:8007
```

Internal (from containers):
```
http://git:8007
```

---

### 1. Health Check

#### `GET /health`

Check service status.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-12-13T10:30:00.000000+00:00"
}
```

---

### 2. Clone Repository

#### `POST /clone`

Clone a Git repository to the workspace.

**Request:**
```json
{
  "repo_url": "https://github.com/username/repo.git",
  "branch": "main",
  "target_dir": "my-project"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_url` | string | Yes | Git repository URL (HTTPS or SSH) |
| `branch` | string | No | Specific branch to clone |
| `target_dir` | string | No | Custom directory name (default: repo name) |

**Response:**
```json
{
  "success": true,
  "repo_path": "my-project",
  "message": "Repository cloned to my-project"
}
```

**Status Codes:**
- `200` - Success
- `400` - Target directory already exists
- `500` - Clone failed

---

### 3. Pull Changes

#### `POST /pull`

Pull latest changes from remote repository.

**Request:**
```json
{
  "repo_path": "my-project",
  "branch": "main"
}
```

**Response:**
```json
{
  "success": true,
  "output": "Already up to date.",
  "message": "Changes pulled successfully"
}
```

---

### 4. Push Changes

#### `POST /push`

Push local commits to remote repository.

**Request:**
```json
{
  "repo_path": "my-project",
  "branch": "feature-branch",
  "force": false
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_path` | string | Yes | Path to repository in workspace |
| `branch` | string | No | Branch to push (default: current branch) |
| `force` | boolean | No | Force push (default: false) |

**Response:**
```json
{
  "success": true,
  "output": "To https://github.com/username/repo.git\n   abc1234..def5678  feature-branch -> feature-branch",
  "message": "Changes pushed successfully"
}
```

---

### 5. Fetch Remote

#### `POST /fetch`

Fetch updates from remote without merging.

**Request:**
```json
{
  "repo_path": "my-project"
}
```

**Response:**
```json
{
  "success": true,
  "output": "Fetching origin",
  "message": "Remote updates fetched"
}
```

---

### 6. Get Status

#### `POST /status`

Get current repository status (changes, branch, etc.).

**Request:**
```json
{
  "repo_path": "my-project"
}
```

**Response:**
```json
{
  "current_branch": "feature-branch",
  "changes": [
    {"status": "M", "file": "README.md"},
    {"status": "A", "file": "new-file.txt"},
    {"status": "D", "file": "old-file.txt"}
  ],
  "has_changes": true
}
```

**File Status Codes:**
- `M` - Modified
- `A` - Added
- `D` - Deleted
- `R` - Renamed
- `??` - Untracked

---

### 7. Create Branch

#### `POST /branch/create`

Create and checkout a new branch.

**Request:**
```json
{
  "repo_path": "my-project",
  "branch_name": "feature/new-automation"
}
```

**Response:**
```json
{
  "success": true,
  "branch": "feature/new-automation",
  "message": "Branch 'feature/new-automation' created and checked out"
}
```

---

### 8. Checkout Branch

#### `POST /branch/checkout`

Switch to an existing branch.

**Request:**
```json
{
  "repo_path": "my-project",
  "branch_name": "main"
}
```

**Response:**
```json
{
  "success": true,
  "branch": "main",
  "message": "Switched to branch 'main'"
}
```

---

### 9. List Branches

#### `GET /branch/list/{repo_path}`

List all branches (local and remote).

**Response:**
```json
{
  "branches": [
    "main",
    "feature/automation",
    "remotes/origin/develop",
    "remotes/origin/main"
  ],
  "current_branch": "main"
}
```

---

### 10. Commit Changes

#### `POST /commit`

Commit changes to the repository.

**Request:**
```json
{
  "repo_path": "my-project",
  "message": "Add automated test results",
  "files": ["test-results.json", "README.md"]
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_path` | string | Yes | Path to repository |
| `message` | string | Yes | Commit message |
| `files` | array | No | Specific files to commit (null = all changes) |

**Response:**
```json
{
  "success": true,
  "message": "Changes committed successfully",
  "output": "[feature-branch abc1234] Add automated test results\n 2 files changed, 45 insertions(+), 2 deletions(-)"
}
```

---

### 11. Create Pull/Merge Request

#### `POST /merge-request/create`

Create a pull request (GitHub), merge request (GitLab), or pull request (Azure DevOps).

**Request:**
```json
{
  "repo_path": "my-project",
  "source_branch": "feature/automation",
  "target_branch": "main",
  "title": "Add new automation scripts",
  "description": "This PR adds automated test scripts for user login flow",
  "provider": "github"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `repo_path` | string | Yes | Path to repository |
| `source_branch` | string | Yes | Branch to merge from |
| `target_branch` | string | Yes | Branch to merge into |
| `title` | string | Yes | PR/MR title |
| `description` | string | No | PR/MR description |
| `provider` | string | Yes | `github`, `gitlab`, or `azure` |

**Response (GitHub):**
```json
{
  "success": true,
  "pr_number": 42,
  "pr_url": "https://github.com/username/repo/pull/42",
  "message": "Pull Request #42 created successfully"
}
```

**Response (GitLab):**
```json
{
  "success": true,
  "mr_number": 15,
  "mr_url": "https://gitlab.com/username/repo/-/merge_requests/15",
  "message": "Merge Request !15 created successfully"
}
```

**Status Codes:**
- `200` - Success
- `400` - Provider mismatch or token not configured
- `500` - API error
- `501` - Provider not fully implemented (Azure)

---

### 12. Checkout Pull/Merge Request

#### `POST /merge-request/checkout`

Checkout a pull request or merge request locally for testing.

**Request:**
```json
{
  "repo_path": "my-project",
  "mr_number": 42,
  "provider": "github"
}
```

**Response:**
```json
{
  "success": true,
  "branch": "pr-42",
  "message": "Checked out GitHub PR #42"
}
```

**Branch Naming:**
- GitHub: `pr-{number}`
- GitLab: `mr-{number}`

---

## Integration Examples

### Example 1: Clone and Setup Repository

```python
import httpx
import asyncio

async def setup_repo():
    async with httpx.AsyncClient() as client:
        # Clone repository
        response = await client.post(
            "http://localhost:8007/clone",
            json={
                "repo_url": "https://github.com/username/test-automation.git",
                "branch": "main",
                "target_dir": "automation-project"
            }
        )
        print(response.json())
        
        # Check status
        response = await client.post(
            "http://localhost:8007/status",
            json={"repo_path": "automation-project"}
        )
        print(response.json())

asyncio.run(setup_repo())
```

---

### Example 2: Create Feature Branch and Commit

```python
async def create_feature():
    async with httpx.AsyncClient() as client:
        # Create new branch
        await client.post(
            "http://localhost:8007/branch/create",
            json={
                "repo_path": "automation-project",
                "branch_name": "feature/new-tests"
            }
        )
        
        # Make changes to files locally...
        
        # Commit changes
        await client.post(
            "http://localhost:8007/commit",
            json={
                "repo_path": "automation-project",
                "message": "Add new test cases for login flow",
                "files": ["tests/login_test.py"]
            }
        )
        
        # Push to remote
        await client.post(
            "http://localhost:8007/push",
            json={
                "repo_path": "automation-project",
                "branch": "feature/new-tests"
            }
        )
```

---

### Example 3: Create Pull Request

```python
async def create_pr():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8007/merge-request/create",
            json={
                "repo_path": "automation-project",
                "source_branch": "feature/new-tests",
                "target_branch": "main",
                "title": "Add login flow test cases",
                "description": "This PR adds comprehensive test coverage for the login flow",
                "provider": "github"
            }
        )
        
        result = response.json()
        print(f"PR created: {result['pr_url']}")
```

---

### Example 4: Review and Test PR

```python
async def review_pr():
    async with httpx.AsyncClient() as client:
        # Checkout PR locally
        await client.post(
            "http://localhost:8007/merge-request/checkout",
            json={
                "repo_path": "automation-project",
                "mr_number": 42,
                "provider": "github"
            }
        )
        
        # Run tests on the PR branch...
        # (execute test suite)
        
        # Switch back to main
        await client.post(
            "http://localhost:8007/branch/checkout",
            json={
                "repo_path": "automation-project",
                "branch_name": "main"
            }
        )
```

---

### Example 5: Automated Workflow (Full Cycle)

```python
async def automated_workflow():
    async with httpx.AsyncClient(timeout=300) as client:
        repo_path = "automation-project"
        
        # 1. Pull latest changes
        await client.post("/pull", json={"repo_path": repo_path})
        
        # 2. Create feature branch
        await client.post("/branch/create", json={
            "repo_path": repo_path,
            "branch_name": "auto/test-results-2025-12-13"
        })
        
        # 3. Generate test results (your test execution logic)
        # ...
        
        # 4. Commit results
        await client.post("/commit", json={
            "repo_path": repo_path,
            "message": "Update test results - 2025-12-13",
            "files": ["results/test-report.json"]
        })
        
        # 5. Push to remote
        await client.post("/push", json={"repo_path": repo_path})
        
        # 6. Create PR
        response = await client.post("/merge-request/create", json={
            "repo_path": repo_path,
            "source_branch": "auto/test-results-2025-12-13",
            "target_branch": "main",
            "title": "Automated test results - 2025-12-13",
            "description": "Automated PR with latest test execution results",
            "provider": "github"
        })
        
        print(f"✓ Workflow complete: {response.json()['pr_url']}")
```

---

## Configuration

### Docker Compose

```yaml
git:
  build:
    context: .
    dockerfile: services/git/Dockerfile
  environment:
    - WORKSPACE_DIR=/workspace
    - GITHUB_TOKEN=${GITHUB_TOKEN:-}
    - GITLAB_TOKEN=${GITLAB_TOKEN:-}
    - AZURE_DEVOPS_TOKEN=${AZURE_DEVOPS_TOKEN:-}
    - AZURE_DEVOPS_ORG=${AZURE_DEVOPS_ORG:-}
  ports:
    - "8007:8000"
  volumes:
    - git_workspace:/workspace
  networks:
    - app-network

volumes:
  git_workspace:
```

### Environment File (.env)

Create `.env` file in project root:

```bash
# GitHub
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# GitLab
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx

# Azure DevOps
AZURE_DEVOPS_TOKEN=xxxxxxxxxxxxxxxxxxxx
AZURE_DEVOPS_ORG=your-organization
```

---

## Workspace Management

### Directory Structure

```
/workspace/
├── project-1/
│   ├── .git/
│   ├── src/
│   └── README.md
├── project-2/
│   ├── .git/
│   └── ...
└── ...
```

### Disk Usage

Check workspace size:
```bash
docker exec git du -sh /workspace
```

### Cleanup

Remove cloned repositories:
```bash
docker exec git rm -rf /workspace/project-name
```

Or clear entire workspace:
```bash
docker-compose down
docker volume rm ai_testing_v2_git_workspace
docker-compose up -d
```

---

## Best Practices

### 1. Repository Naming

Use consistent directory names:
```python
# Good
target_dir = "automation-tests"
target_dir = "project-frontend"

# Avoid
target_dir = "repo"
target_dir = "test"
```

### 2. Branch Naming

Follow conventions:
```
feature/description
bugfix/issue-number
hotfix/critical-fix
auto/automated-task
```

### 3. Commit Messages

Be descriptive:
```python
# Good
"Add automated test for user registration flow"
"Fix: Correct timeout in login test"
"Update: Refresh test data fixtures"

# Avoid
"update"
"fix"
"changes"
```

### 4. Error Handling

Always handle failures:
```python
try:
    response = await client.post("/push", json={...})
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    print(f"Push failed: {e.response.json()['detail']}")
```

### 5. Token Security

Never commit tokens:
```bash
# .gitignore
.env
*.token
```

---

## Troubleshooting

### Clone Fails with Authentication Error

**Symptom:**
```
Clone failed: fatal: Authentication failed
```

**Solutions:**
1. For HTTPS URLs, use token in URL:
   ```
   https://TOKEN@github.com/user/repo.git
   ```

2. Or configure Git credentials in container

3. Use SSH URLs with keys mounted

---

### Push Fails: "Updates were rejected"

**Symptom:**
```
Push failed: ! [rejected] branch -> branch (non-fast-forward)
```

**Solutions:**
1. Pull first:
   ```python
   await client.post("/pull", json={"repo_path": repo})
   ```

2. Or force push (if safe):
   ```python
   await client.post("/push", json={"repo_path": repo, "force": True})
   ```

---

### PR Creation Fails: Token Invalid

**Symptom:**
```
GitHub API error: Unauthorized
```

**Solutions:**
1. Verify token in `.env`:
   ```bash
   echo $GITHUB_TOKEN
   ```

2. Check token permissions (needs `repo` scope)

3. Regenerate token if expired

---

### Repository Not Found

**Symptom:**
```
Repository path not found: my-project
```

**Solutions:**
1. List workspace contents:
   ```bash
   docker exec git ls /workspace
   ```

2. Clone repository first:
   ```python
   await client.post("/clone", json={...})
   ```

---

## Security Considerations

### Token Storage

- Tokens stored as environment variables
- Never logged or exposed in responses
- Use `.env` file (not tracked in Git)

### Workspace Isolation

- All operations contained in `/workspace`
- Path traversal prevented
- Volume isolated from host system

### API Access

- No authentication (internal network only)
- Not exposed to internet
- Consider adding API keys for production

---

## Performance Metrics

| Operation | Typical Time |
|-----------|--------------|
| Clone (small repo) | 2-5 seconds |
| Clone (large repo) | 30-120 seconds |
| Pull (no changes) | < 1 second |
| Pull (with changes) | 1-5 seconds |
| Push | 2-10 seconds |
| Commit | < 1 second |
| Create PR/MR | 1-3 seconds |
| Checkout PR | 2-5 seconds |

---

## Documentation

### Service Documentation
- **[SSH Key Management Guide](SSH_KEY_MANAGEMENT.md)** - Comprehensive guide for SSH key authentication
- **[SSH Key Implementation](SSH_KEY_IMPLEMENTATION.md)** - Technical implementation details
- **[SSH Implementation Summary](SSH_KEY_IMPLEMENTATION_SUMMARY.md)** - Quick overview of SSH features
- **[Testing Quickstart](TESTING_QUICKSTART.md)** - Guide to running the test suite

### API Documentation
- **Swagger UI**: http://localhost:8007/docs
- **ReDoc**: http://localhost:8007/redoc

---

## Future Enhancements

- [x] SSH key management ✅ **Complete**
- [ ] Git LFS support
- [ ] Submodule handling
- [ ] Cherry-pick operations
- [ ] Rebase support
- [ ] Tag management
- [ ] Release creation
- [ ] Webhook integration
- [ ] PR comment automation
- [ ] Status check integration
- [ ] Multi-repository operations
- [ ] Conflict resolution helpers
