# Git Integration Architecture

## Complete Solution Overview

### Problem Statement
**Current**: AI-generated Playwright tests stored only in MongoDB → No version control, no review process, manual execution
**Goal**: Automatically push generated tests to Git repositories with PR/MR creation → Enable team review, CI/CD integration, and repeated execution

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Test Cases   │  │ Generate AI  │  │ Push to Git  │         │
│  │ Page         │  │ Automation   │  │ Button   ●NEW│         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          │ GET /testcases   │ POST /generate   │ POST /push-test-to-git
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼─────────────────┐
│                   Backend Microservices                          │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────┐   │
│  │  TestCases    │  │  Generator    │  │  Git Service     │   │
│  │  Service      │  │  Service      │  │  ●NEW endpoints  │   │
│  │  :8002        │  │  :8003        │  │  :8005           │   │
│  └───┬───────────┘  └───┬───────────┘  └──────┬───────────┘   │
│      │                  │                      │                │
│      │ MongoDB          │ Ollama               │ Git commands   │
│      │ (tests)          │ (AI model)           │ (subprocess)   │
│  ┌───▼───────────┐  ┌───▼───────────┐  ┌──────▼───────────┐   │
│  │  MongoDB      │  │  Ollama       │  │  /workspace/     │   │
│  │  :27017       │  │  :11434       │  │  (git repos)     │   │
│  └───────────────┘  └───────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────┼──────────────────┘
                                               │ Git operations
                                               │
┌──────────────────────────────────────────────▼──────────────────┐
│                      Git Provider                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   GitHub     │  │   GitLab     │  │  Azure DevOps│          │
│  │              │  │              │  │              │          │
│  │  Pull        │  │  Merge       │  │  Pull        │          │
│  │  Requests    │  │  Requests    │  │  Requests    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└──────────────────────────────────────────────┼──────────────────┘
                                               │ Webhook (future)
                                               │
┌──────────────────────────────────────────────▼──────────────────┐
│                   CI/CD Pipeline (Optional)                      │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  • Triggered by PR creation                           │       │
│  │  • Install dependencies (npm ci)                      │       │
│  │  • Install Playwright browsers                        │       │
│  │  • Run tests (npx playwright test)                    │       │
│  │  • Generate report                                    │       │
│  │  • Comment results on PR                              │       │
│  └──────────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Detailed Flow Sequence

### Flow 1: Generate & Push Test (New Feature)

```
┌─────┐     ┌──────────┐     ┌───────────┐     ┌─────────┐     ┌──────────┐
│User │     │ Frontend │     │ Generator │     │   Git   │     │GitHub/GL │
└──┬──┘     └────┬─────┘     └─────┬─────┘     └────┬────┘     └────┬─────┘
   │             │                  │                │               │
   │ 1. Click    │                  │                │               │
   │ "Push to    │                  │                │               │
   │  Git"       │                  │                │               │
   ├────────────>│                  │                │               │
   │             │                  │                │               │
   │             │ 2. POST          │                │               │
   │             │ /push-test-to-git│                │               │
   │             ├─────────────────>│                │               │
   │             │                  │                │               │
   │             │                  │ 3. GET         │               │
   │             │                  │ test case      │               │
   │             │                  ├────────┐       │               │
   │             │                  │ (from  │       │               │
   │             │                  │ MongoDB)       │               │
   │             │                  │<───────┘       │               │
   │             │                  │                │               │
   │             │                  │ 4. Generate/   │               │
   │             │                  │ fetch          │               │
   │             │                  │ automation     │               │
   │             │                  ├────────┐       │               │
   │             │                  │ (Ollama│       │               │
   │             │                  │ if new)        │               │
   │             │                  │<───────┘       │               │
   │             │                  │                │               │
   │             │                  │ 5. POST /clone │               │
   │             │                  ├───────────────>│               │
   │             │                  │                │ 6. git clone  │
   │             │                  │                ├──────────────>│
   │             │                  │                │<──────────────│
   │             │                  │<───────────────│ (repo data)   │
   │             │                  │                │               │
   │             │                  │ 7. POST        │               │
   │             │                  │ /branch/create │               │
   │             │                  ├───────────────>│               │
   │             │                  │                │ 8. git branch │
   │             │                  │                │ git checkout  │
   │             │                  │                ├────────┐      │
   │             │                  │                │<───────┘      │
   │             │                  │<───────────────│               │
   │             │                  │                │               │
   │             │                  │ 9. POST        │               │
   │             │                  │ /file/write    │               │
   │             │                  ├───────────────>│               │
   │             │                  │                │ 10. Write     │
   │             │                  │                │ .spec.js file │
   │             │                  │                ├────────┐      │
   │             │                  │                │<───────┘      │
   │             │                  │<───────────────│               │
   │             │                  │                │               │
   │             │                  │ 11. POST       │               │
   │             │                  │ /commit        │               │
   │             │                  ├───────────────>│               │
   │             │                  │                │ 12. git add   │
   │             │                  │                │ git commit    │
   │             │                  │                ├────────┐      │
   │             │                  │                │<───────┘      │
   │             │                  │<───────────────│               │
   │             │                  │                │               │
   │             │                  │ 13. POST /push │               │
   │             │                  ├───────────────>│               │
   │             │                  │                │ 14. git push  │
   │             │                  │                ├──────────────>│
   │             │                  │                │<──────────────│
   │             │                  │<───────────────│               │
   │             │                  │                │               │
   │             │                  │ 15. POST       │               │
   │             │                  │ /merge-request │               │
   │             │                  ├───────────────>│               │
   │             │                  │                │ 16. API call  │
   │             │                  │                │ Create PR/MR  │
   │             │                  │                ├──────────────>│
   │             │                  │                │<──────────────│
   │             │                  │<───────────────│ PR #42 created│
   │             │                  │                │               │
   │             │ 17. Response     │                │               │
   │             │ { pr_url: ... }  │                │               │
   │             │<─────────────────│                │               │
   │             │                  │                │               │
   │ 18. Display │                  │                │               │
   │ success     │                  │                │               │
   │ + PR link   │                  │                │               │
   │<────────────│                  │                │               │
   │             │                  │                │               │
```

---

## Component Breakdown

### 1. Generator Service (`services/generator/main.py`)

**New Code**:
```python
@app.post("/push-test-to-git")
async def push_test_to_git_endpoint(payload: GitPushRequest):
    # 1. Fetch test case from MongoDB
    test_case = await fetch_test_case(payload.test_case_id)
    
    # 2. Generate or fetch automation
    automation = await get_or_generate_automation(test_case)
    
    # 3. Push to Git (orchestration)
    git_result = await push_test_to_git(
        test_case_id=payload.test_case_id,
        test_title=test_case.title,
        script_content=automation.script,
        provider=payload.provider
    )
    
    # 4. Return PR URL + instructions
    return {
        "pr_url": git_result.pr_url,
        "branch": git_result.branch_name,
        "execution": {...}
    }
```

**Dependencies**:
- `git_integration.py`: Orchestration logic
- `shared/models.py`: Data models
- Git service: HTTP client to call endpoints

### 2. Git Integration Module (`services/generator/git_integration.py`)

**Core Function**:
```python
async def push_test_to_git(
    test_case_id: str,
    test_title: str,
    script_content: str,
    provider: str
) -> dict:
    # Step 1: Clone/pull repository
    await git_service.clone_or_pull(repo_url)
    
    # Step 2: Create feature branch
    branch_name = f"feat/test-{test_case_id}-{timestamp}"
    await git_service.create_branch(branch_name)
    
    # Step 3: Format test as Playwright file
    test_file = generate_playwright_test_file(
        title=test_title,
        script=script_content,
        test_id=test_case_id
    )
    
    # Step 4: Write file
    file_path = f"tests/generated/{safe_title}.spec.js"
    await git_service.write_file(file_path, test_file, branch_name)
    
    # Step 5: Commit
    await git_service.commit(
        message=f"feat: Add test for {test_title}",
        files=[file_path]
    )
    
    # Step 6: Push
    await git_service.push(branch=branch_name)
    
    # Step 7: Create PR/MR
    pr = await git_service.create_merge_request(
        source=branch_name,
        target="main",
        title=f"[Auto] Test: {test_title}",
        provider=provider
    )
    
    return {
        "pr_url": pr.url,
        "branch_name": branch_name,
        "file_path": file_path
    }
```

### 3. Git Service (`services/git/main.py`)

**New Endpoint**:
```python
@app.post("/file/write")
async def write_file(payload: FileWriteRequest):
    repo_path = get_repo_path(payload.repo_path)
    
    # Checkout branch if specified
    if payload.branch:
        run_git_command(["checkout", payload.branch], cwd=repo_path)
    
    # Sanitize and create path
    file_path = sanitize_path(payload.file_path, repo_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write content
    file_path.write_text(payload.content, encoding="utf-8")
    
    return {
        "success": True,
        "file_path": str(file_path.relative_to(repo_path)),
        "size_bytes": file_path.stat().st_size
    }
```

**Existing Endpoints Used**:
- `POST /clone`: Clone repository
- `POST /pull`: Pull latest changes
- `POST /branch/create`: Create branch
- `POST /commit`: Commit changes
- `POST /push`: Push to remote
- `POST /merge-request/create`: Create PR/MR

---

## File Structure

```
ai_testing_v2/
├── services/
│   ├── generator/
│   │   ├── main.py              (Modified: +100 lines)
│   │   ├── git_integration.py   (NEW: 344 lines)
│   │   └── requirements.txt     (Add: httpx)
│   └── git/
│       ├── main.py              (Modified: +60 lines)
│       └── ...
├── docs/
│   ├── GIT_INTEGRATION.md       (NEW: 580 lines)
│   ├── IMPLEMENTATION_SUMMARY.md(NEW: 400 lines)
│   ├── QUICKSTART_GIT.md        (NEW: 150 lines)
│   └── ARCHITECTURE.md          (NEW: this file)
└── docker-compose.yml           (Modify: add git service)
```

---

## Data Flow

### Test Generation → Git Push

```
1. Test Case in MongoDB
   {
     "id": "64f1a2b3c4d5e6f7",
     "title": "User Login Flow",
     "metadata": {
       "steps": [...],
       "description": "...",
       "preconditions": "..."
     }
   }
   
2. Generate Automation (Ollama)
   {
     "script": "await page.goto('...');\nawait page.click('...');"
   }
   
3. Format as Playwright Test
   // Auto-generated test by AI Test Platform
   // Test ID: 64f1a2b3c4d5e6f7
   
   import { test, expect } from '@playwright/test';
   
   test.describe('User Login Flow', () => {
     test('should execute User Login Flow', async ({ page }) => {
       await page.goto('https://example.com/login');
       await page.click('#login-btn');
       ...
     });
   });
   
4. Write to Git
   tests/generated/user-login-flow-64f1a2b3.spec.js
   
5. Create PR
   https://github.com/org/repo/pull/42
   Title: [Auto-Generated] Test: User Login Flow
   Description: Test ID: 64f1a2b3c4d5e6f7
   
6. Return to User
   {
     "pr_url": "https://github.com/org/repo/pull/42",
     "branch": "feat/test-64f1a2b3-1702340567",
     "file": "tests/generated/user-login-flow-64f1a2b3.spec.js"
   }
```

---

## Execution Paths

### Path 1: Immediate Execution (Current - via MCP)
```
User → Generate Automation → Execute via Playwright MCP → Results in UI
```
**Use**: Rapid feedback during development

### Path 2: Git + Manual Execution (New - This Implementation)
```
User → Generate + Push to Git → PR Created → Developer checks out → Runs test locally
```
**Use**: Code review, team collaboration, version control

### Path 3: Git + CI/CD (Future - Recommended)
```
User → Generate + Push to Git → PR Created → Webhook → CI/CD runs tests → Results in PR
```
**Use**: Automated regression testing, production deployments

---

## Configuration Matrix

| Component | Environment Variable | Required | Default | Purpose |
|-----------|---------------------|----------|---------|---------|
| Generator | `GIT_SERVICE_URL` | No | `http://git:8000` | Git service endpoint |
| Generator | `TESTS_REPO_URL` | **Yes** | - | Git repository URL |
| Generator | `TESTS_REPO_BRANCH` | No | `main` | Base branch for PRs |
| Generator | `TEST_FILES_PATH` | No | `tests/generated` | Path within repo |
| Git | `WORKSPACE_DIR` | No | `/workspace` | Local git repos |
| Git | `SSH_KEYS_DIR` | No | `/ssh-keys` | SSH key storage |
| Git | `GITHUB_TOKEN` | For GitHub | - | GitHub API access |
| Git | `GITLAB_TOKEN` | For GitLab | - | GitLab API access |
| Git | `AZURE_DEVOPS_TOKEN` | For Azure | - | Azure DevOps API |

---

## Deployment Scenarios

### Scenario A: Public Repository (HTTPS)
```yaml
generator:
  environment:
    - TESTS_REPO_URL=https://github.com/public-org/tests.git
git:
  environment:
    - GITHUB_TOKEN=ghp_publicReadWrite123
```
**Use**: Open source projects, public test repositories

### Scenario B: Private Repository (SSH)
```yaml
generator:
  environment:
    - TESTS_REPO_URL=git@github.com:private-org/tests.git
git:
  volumes:
    - ./ssh-keys:/ssh-keys:ro
```
**Use**: Enterprise, private codebases

### Scenario C: Multi-Provider
```yaml
# Support GitHub + GitLab + Azure simultaneously
git:
  environment:
    - GITHUB_TOKEN=ghp_xxx
    - GITLAB_TOKEN=glpat_yyy
    - AZURE_DEVOPS_TOKEN=zzz
```
**Use**: Organizations using multiple Git providers

---

## Success Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Tests version-controlled | 0% | 100% | ∞ |
| Tests reviewable | No | Yes (via PR) | ✓ |
| Execution repeatability | Manual copy | Clone + run | High |
| Team collaboration | Individual | Shared repo | High |
| Audit trail | MongoDB logs | Git history | High |
| CI/CD ready | No | Yes (structure) | High |

---

## Security Model

```
┌─────────────────────────────────────────┐
│         Security Layers                 │
├─────────────────────────────────────────┤
│ 1. Path Sanitization                    │
│    ✓ Prevents ../../../ attacks         │
│    ✓ Stays within WORKSPACE_DIR         │
├─────────────────────────────────────────┤
│ 2. Branch Validation                    │
│    ✓ Blocks shell metacharacters        │
│    ✓ No ; && || ` $ in branch names     │
├─────────────────────────────────────────┤
│ 3. Commit Validation                    │
│    ✓ Max length (10KB)                  │
│    ✓ UTF-8 encoding check               │
├─────────────────────────────────────────┤
│ 4. Authentication                       │
│    ✓ SSH keys (0600 permissions)        │
│    ✓ Tokens in secrets (not code)       │
├─────────────────────────────────────────┤
│ 5. Code Review                          │
│    ✓ All tests reviewed via PR          │
│    ✓ No direct merge to main            │
└─────────────────────────────────────────┘
```

---

## Future Enhancements Roadmap

### Phase 1: ✅ Done
- [x] Git integration module
- [x] File write endpoint
- [x] PR/MR creation
- [x] Documentation

### Phase 2: 🔄 In Progress (Your Next Steps)
- [ ] Frontend "Push to Git" button
- [ ] Environment variable configuration
- [ ] Test repository setup
- [ ] Manual execution workflow

### Phase 3: 📋 Planned
- [ ] CI/CD pipeline templates
- [ ] Webhook integration
- [ ] Test result comments on PR
- [ ] Screenshot attachment on failure

### Phase 4: 🚀 Advanced
- [ ] Scheduled test runs
- [ ] Test analytics integration
- [ ] Batch test generation
- [ ] Test update detection (modify existing instead of new)

---

**This architecture enables a seamless flow from AI-generated test concepts to production-ready, version-controlled, team-reviewed test automation!**
