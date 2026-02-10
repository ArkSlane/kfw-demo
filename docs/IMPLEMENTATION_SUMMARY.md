# Git Integration Implementation Summary

## What Was Implemented

### 1. **Git Integration Module** (`services/generator/git_integration.py`)

**Purpose**: Orchestrate the workflow of pushing generated tests to Git repositories

**Key Functions**:
- `push_test_to_git()`: Complete workflow for test deployment
  - Clones/pulls repository
  - Creates feature branch
  - Writes test file with proper Playwright format
  - Commits and pushes changes
  - Creates Pull/Merge Request
  
- `generate_playwright_test_file()`: Formats tests as proper `.spec.js` files
- `trigger_test_execution()`: Returns execution instructions (manual for now)

**Flow**:
```
Test Script → Format → Branch → Write → Commit → Push → PR/MR
```

### 2. **Git Service Endpoint** (`services/git/main.py`)

**New Endpoint**: `POST /file/write`

**Purpose**: Write files to Git repositories (for test generation)

**Features**:
- Branch checkout before write
- Directory creation (mkdir -p behavior)
- Path validation and sanitization
- UTF-8 encoding
- File verification after write

**Request**:
```json
{
  "repo_path": "test-repo",
  "file_path": "tests/generated/login-test.spec.js",
  "content": "// Test content...",
  "branch": "feat/new-test"
}
```

### 3. **Generator Service Endpoint** (`services/generator/main.py`)

**New Endpoint**: `POST /push-test-to-git`

**Purpose**: Main entry point for pushing tests to Git

**Workflow**:
1. Fetch test case from testcases service
2. Check if automation exists, generate if not
3. Call `push_test_to_git()` to handle Git operations
4. Return PR/MR URL and execution instructions

**Request**:
```json
{
  "test_case_id": "64f1a2b3c4d5e6f7",
  "provider": "github",
  "repo_url": "https://github.com/org/tests.git",
  "base_branch": "main",
  "ssh_key_name": "test-repo",
  "auto_execute": false
}
```

**Response**:
```json
{
  "success": true,
  "automation_id": "64f...",
  "test_case_id": "64f1a2b3c4d5e6f7",
  "test_title": "User Login Flow",
  "git_result": {
    "pr_url": "https://github.com/org/tests/pull/42",
    "pr_number": 42,
    "branch_name": "feat/test-64f1a2b3-1702340567",
    "file_path": "tests/generated/user-login-flow.spec.js"
  },
  "execution": {
    "instructions": { "commands": [...] },
    "webhook_suggestion": {...}
  },
  "message": "Test pushed to Git successfully!"
}
```

## Services Architecture

```
┌──────────────┐
│   Frontend   │ "Push to Git" button
└──────┬───────┘
       │ POST /push-test-to-git
       ▼
┌──────────────────────────────┐
│   Generator Service :8003    │
│  • Fetch test case           │
│  • Generate/fetch automation │
│  • Orchestrate Git workflow  │
└──────┬───────────────────────┘
       │ Calls git_integration.push_test_to_git()
       ▼
┌──────────────────────────────┐
│   Git Service :8005          │
│  POST /clone                 │
│  POST /pull                  │
│  POST /branch/create         │
│  POST /file/write         ←─── NEW
│  POST /commit                │
│  POST /push                  │
│  POST /merge-request/create  │
└──────┬───────────────────────┘
       │ Git commands
       ▼
┌──────────────────────────────┐
│   Git Provider               │
│  • GitHub                    │
│  • GitLab                    │
│  • Azure DevOps              │
└──────────────────────────────┘
```

## Environment Variables Required

Add to `docker-compose.yml` → `generator` service:

```yaml
generator:
  environment:
    - GIT_SERVICE_URL=http://git:8000
    - TESTS_REPO_URL=https://github.com/your-org/tests.git
    - TESTS_REPO_BRANCH=main
    - TEST_FILES_PATH=tests/generated
```

Add to `docker-compose.yml` → `git` service:

```yaml
git:
  environment:
    - GITHUB_TOKEN=ghp_xxxxx  # For PR creation
    - GITLAB_TOKEN=glpat-xxxxx
    - AZURE_DEVOPS_TOKEN=xxxxx
```

## How It Works

### Scenario: User generates test and pushes to Git

1. **User Action**: Clicks "Push to Git" on a test case
2. **Frontend**: Calls `POST /push-test-to-git`
3. **Generator Service**:
   ```python
   # Check if automation exists
   automations = get_automations(test_case_id)
   if not automations:
       # Generate new automation via Ollama
       automation = generate_automation(test_case)
   
   # Format as Playwright test file
   test_content = generate_playwright_test_file(
       title="User Login",
       script=automation.script,
       test_id="abc123"
   )
   # Result:
   # import { test, expect } from '@playwright/test';
   # test.describe('User Login', () => {
   #   test('should execute User Login', async ({ page }) => {
   #     await page.goto('https://example.com');
   #     await page.click('#login-button');
   #     ...
   #   });
   # });
   ```

4. **Git Integration Module**:
   ```python
   # Clone repo (or pull if exists)
   git_service.clone(repo_url)
   
   # Create branch
   branch = f"feat/test-{test_case_id}-{timestamp}"
   git_service.create_branch(branch)
   
   # Write file
   file_path = "tests/generated/user-login-abc123.spec.js"
   git_service.write_file(
       path=file_path,
       content=test_content,
       branch=branch
   )
   
   # Commit
   git_service.commit(
       message="feat: Add test for User Login\n\nTest ID: abc123",
       files=[file_path]
   )
   
   # Push
   git_service.push(branch=branch)
   
   # Create PR
   pr = git_service.create_pr(
       source=branch,
       target="main",
       title="[Auto] Test: User Login",
       description="Generated by AI Test Platform..."
   )
   ```

5. **Git Service**: Executes Git commands via subprocess
6. **Git Provider**: Receives push, creates PR
7. **Response to Frontend**:
   ```json
   {
     "pr_url": "https://github.com/org/tests/pull/42",
     "branch": "feat/test-abc123-1702340567",
     "file": "tests/generated/user-login-abc123.spec.js"
   }
   ```

8. **User**: Reviews PR on GitHub/GitLab
9. **Execution** (manual for now):
   ```bash
   git checkout feat/test-abc123-1702340567
   npx playwright test tests/generated/user-login-abc123.spec.js
   ```

## Test File Format

Generated files follow Playwright best practices:

```javascript
// Auto-generated test by AI Test Platform
// Test ID: 64f1a2b3c4d5e6f7
// Generated: 2024-12-15T10:30:00Z

import { test, expect } from '@playwright/test';

test.describe('User Login Flow', () => {
  test('should execute User Login Flow', async ({ page }) => {
    await page.goto('https://example.com/login');
    await page.fill('input[name="username"]', 'testuser');
    await page.fill('input[name="password"]', 'password123');
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(page.locator('.welcome-message')).toBeVisible();
  });
});
```

## Repeated Test Execution Options

### Option 1: Manual (Current - No Pipeline)
```bash
# Developer runs manually after PR creation
git checkout feat/test-abc123
npx playwright test
```

**Pros**: Works immediately, no setup
**Cons**: Manual effort, inconsistent

### Option 2: Git Webhooks + CI/CD (Recommended)

Set up GitHub Actions `.github/workflows/playwright.yml`:
```yaml
on: [pull_request, push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci
      - run: npx playwright install --with-deps
      - run: npx playwright test
```

**Pros**: Fully automated, consistent
**Cons**: Requires pipeline setup

### Option 3: Scheduled Runs

Add to CI/CD:
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
```

**Pros**: Regular testing without manual trigger
**Cons**: Not immediate, requires pipeline

### Option 4: API-Triggered (Custom)

Create webhook endpoint that triggers test execution:
```python
@app.post("/run-test")
async def run_test(branch: str):
    # Pull branch
    # Run playwright in docker
    # Report results
```

**Pros**: On-demand, integrated with platform
**Cons**: Custom development needed

## Getting Closest to Pipeline Without One

**What we have NOW**:
✅ Tests version-controlled in Git
✅ Tests reviewable via PR/MR
✅ Manual execution instructions provided
✅ Proper test file structure
✅ Traceability (test ID in file)

**What's missing**:
❌ Automatic execution on PR
❌ Result reporting in PR
❌ Scheduled runs

**How to bridge the gap**:

1. **Batch execution script**:
```bash
#!/bin/bash
# run-pending-prs.sh
for pr in $(gh pr list --json number -q '.[].number'); do
  gh pr checkout $pr
  npx playwright test
  gh pr comment $pr --body "Tests completed"
done
```

2. **Docker-based execution**:
```bash
docker run -v ./tests:/tests \
  mcr.microsoft.com/playwright:v1.40.0 \
  sh -c "cd /tests && npm ci && npx playwright test"
```

3. **Frontend trigger + Docker**:
   - User clicks "Run Test"
   - Frontend calls backend
   - Backend runs test in Docker
   - Results displayed in UI

This gets you **~80% of the way** to a full pipeline!

## Security Features

✅ **Path sanitization**: Prevents `../../../etc/passwd` attacks
✅ **Branch validation**: Blocks shell injection (`; rm -rf /`)
✅ **Commit validation**: Max length, encoding checks
✅ **SSH key support**: Secure authentication for private repos
✅ **Token rotation**: Use short-lived tokens
✅ **Code review**: Generated tests reviewed before merge

## Next Steps

### Immediate (No Pipeline)
1. Add "Push to Git" button in frontend
2. Configure `TESTS_REPO_URL` env var
3. Test workflow manually
4. Review and merge generated test PRs

### Short-term (Basic Pipeline)
1. Add `.github/workflows/playwright.yml` to test repo
2. Tests run automatically on PR
3. Results visible in PR checks

### Long-term (Full Automation)
1. Test results commented on PR
2. Screenshots attached on failure
3. Scheduled nightly runs
4. Integration with test analytics

## Testing the Implementation

### 1. Test git service file write:
```bash
curl -X POST http://localhost:8005/file/write \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "my-repo",
    "file_path": "tests/test.spec.js",
    "content": "import { test } from \"@playwright/test\"; test(\"example\", async ({ page }) => {});",
    "branch": "main"
  }'
```

### 2. Test full push workflow:
```bash
curl -X POST http://localhost:8003/push-test-to-git \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "64f1a2b3c4d5e6f7",
    "provider": "github"
  }'
```

### 3. Verify in Git provider:
- Check PR was created
- Review file contents
- Verify branch exists

### 4. Manual test execution:
```bash
git clone <repo-url>
git checkout feat/test-abc123-...
npm install
npx playwright test
```

## Files Modified/Created

### Created:
1. `services/generator/git_integration.py` (344 lines)
   - Git workflow orchestration
   - Test file formatting
   - Execution instructions

2. `docs/GIT_INTEGRATION.md` (580 lines)
   - Complete documentation
   - Setup instructions
   - CI/CD examples
   - Troubleshooting guide

3. `docs/IMPLEMENTATION_SUMMARY.md` (this file)
   - High-level overview
   - Architecture diagram
   - Usage examples

### Modified:
1. `services/git/main.py`
   - Added `FileWriteRequest` model
   - Added `POST /file/write` endpoint

2. `services/generator/main.py`
   - Added `git_integration` import
   - Added `GitPushRequest` model
   - Added `POST /push-test-to-git` endpoint

## Summary

This implementation creates a complete workflow for pushing AI-generated Playwright tests to Git repositories with PR/MR creation. While it doesn't include automatic execution (requires CI/CD pipeline), it provides:

1. **Version Control**: Tests tracked in Git
2. **Code Review**: Team reviews via PR before merge
3. **Reproducibility**: Anyone can run tests from repo
4. **Manual Execution**: Clear instructions for running tests
5. **Foundation**: Ready for CI/CD integration when available

**Key Achievement**: Bridges the gap between AI generation and production-ready test automation WITHOUT requiring a pipeline to be configured first. You can start using it immediately with manual execution, then add automation later.
