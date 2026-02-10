# Git Integration for Automated Test Generation

## Overview

This integration enables automatic pushing of generated Playwright tests to a Git repository with Pull/Merge Request creation. This bridges the gap between AI-generated tests and CI/CD pipelines.

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐      ┌──────────────┐
│  Frontend   │─────▶│  Generator   │─────▶│ Git Service │─────▶│  Git Provider│
│  (Trigger)  │      │   Service    │      │  (Clone/    │      │ (GitHub/     │
└─────────────┘      │              │      │   Push/PR)  │      │  GitLab/     │
                     │  • Generate  │      └─────────────┘      │  Azure)      │
                     │  • Format    │                            └──────────────┘
                     │  • Push      │                                    │
                     └──────────────┘                                    │
                            │                                            │
                            │                                            ▼
                            │                            ┌──────────────────────┐
                            │                            │   CI/CD Pipeline     │
                            │                            │  • Webhook trigger   │
                            └────────────────────────────│  • Run tests         │
                                                         │  • Report results    │
                                                         └──────────────────────┘
```

## Services Involved

### 1. **Generator Service** (`services/generator/`)
- **Role**: Orchestrates the entire workflow
- **Files**:
  - `main.py`: `/push-test-to-git` endpoint
  - `git_integration.py`: Git workflow logic
- **Responsibilities**:
  - Generate Playwright test code via Ollama/MCP
  - Call git service to manage repository
  - Create formatted test files
  - Handle errors and return status

### 2. **Git Service** (`services/git/`)
- **Role**: Manages all Git operations
- **Files**: `main.py`
- **New Endpoints**:
  - `POST /file/write`: Write test files to repo
  - `POST /branch/create`: Create feature branches
  - `POST /commit`: Commit changes
  - `POST /push`: Push to remote
  - `POST /merge-request/create`: Create PR/MR
- **Features**:
  - Multi-provider support (GitHub, GitLab, Azure DevOps)
  - SSH key authentication
  - Security validations

### 3. **Automations Service** (`services/automations/`)
- **Role**: Store generated test scripts
- **Integration**: Generator fetches existing automations or creates new ones

## Setup Instructions

### 1. Environment Variables

Add these to your `docker-compose.yml` or `.env`:

```yaml
generator:
  environment:
    # Existing vars...
    - GIT_SERVICE_URL=http://git:8000
    - TESTS_REPO_URL=https://github.com/your-org/your-tests-repo.git
    - TESTS_REPO_BRANCH=main
    - TEST_FILES_PATH=tests/generated  # Path within repo
    
git:
  environment:
    # For public repos (HTTPS)
    - GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
    - GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
    - AZURE_DEVOPS_TOKEN=xxxxxxxxxxxxxxxxxxxx
    - AZURE_DEVOPS_ORG=your-org
    
    # For private repos (SSH) - alternatively
    - SSH_KEYS_DIR=/ssh-keys
  volumes:
    - ./ssh-keys:/ssh-keys:ro
```

### 2. Git Service Setup

Add git service to `docker-compose.yml`:

```yaml
git:
  build:
    context: .
    dockerfile: services/git/Dockerfile
  environment:
    - WORKSPACE_DIR=/workspace
    - SSH_KEYS_DIR=/ssh-keys
    - GITHUB_TOKEN=${GITHUB_TOKEN}
  ports:
    - "8005:8000"
  volumes:
    - git_workspace:/workspace
    - ./ssh-keys:/ssh-keys:ro
  networks:
    - app-network

volumes:
  git_workspace:
```

### 3. SSH Key Configuration (for private repos)

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "ai-test-platform@example.com" -f ./ssh-keys/test-repo

# Add public key to Git provider
cat ./ssh-keys/test-repo.pub
# → Add to GitHub Settings → SSH Keys

# Upload key via API (optional)
curl -X POST http://localhost:8005/ssh-keys/upload \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "test-repo",
    "private_key": "'"$(cat ./ssh-keys/test-repo)"'",
    "public_key": "'"$(cat ./ssh-keys/test-repo.pub)"'"
  }'
```

## Usage

### Frontend Integration

Add a "Push to Git" button in Test Cases page:

```javascript
// In TestCases.jsx
const handlePushToGit = async (testCase) => {
  try {
    setLoading(true);
    const result = await generatorAPI.pushTestToGit({
      test_case_id: testCase.id,
      provider: 'github',  // or 'gitlab', 'azure'
      ssh_key_name: 'test-repo'  // if using SSH
    });
    
    toast.success(`Test pushed! PR created: ${result.git_result.pr_url}`);
    
    // Show execution instructions
    console.log('To run:', result.execution.instructions);
  } catch (error) {
    toast.error('Failed to push test to Git');
  } finally {
    setLoading(false);
  }
};
```

### API Call Example

```bash
curl -X POST http://localhost:8003/push-test-to-git \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "64f1a2b3c4d5e6f7g8h9i0j1",
    "provider": "github",
    "repo_url": "https://github.com/your-org/tests.git",
    "base_branch": "main",
    "ssh_key_name": "test-repo"
  }'
```

### Response Example

```json
{
  "success": true,
  "automation_id": "64f1...",
  "test_case_id": "64f1a2b3...",
  "test_title": "User Login Flow",
  "git_result": {
    "success": true,
    "pr_url": "https://github.com/your-org/tests/pull/42",
    "pr_number": 42,
    "branch_name": "feat/test-64f1a2b3-1702340567",
    "file_path": "tests/generated/user-login-flow-64f1a2b3.spec.js",
    "repo_name": "tests"
  },
  "execution": {
    "execution_type": "manual",
    "instructions": {
      "description": "To run this test, execute the following commands:",
      "commands": [
        "git clone <repo-url> tests",
        "cd tests",
        "git checkout feat/test-64f1a2b3-1702340567",
        "npm install",
        "npx playwright test tests/generated/user-login-flow-64f1a2b3.spec.js"
      ]
    },
    "webhook_suggestion": {...},
    "ci_config_examples": {...}
  },
  "message": "Test pushed to Git successfully! PR/MR created at ..."
}
```

## CI/CD Pipeline Integration

### GitHub Actions

Create `.github/workflows/playwright.yml` in your test repository:

```yaml
name: Playwright Tests

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-node@v4
        with:
          node-version: '18'
          
      - name: Install dependencies
        run: npm ci
        
      - name: Install Playwright Browsers
        run: npx playwright install --with-deps
        
      - name: Run Playwright tests
        run: npx playwright test
        
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
```

### GitLab CI

Create `.gitlab-ci.yml`:

```yaml
image: mcr.microsoft.com/playwright:v1.40.0-focal

stages:
  - test

playwright-tests:
  stage: test
  script:
    - npm ci
    - npx playwright test
  artifacts:
    when: always
    paths:
      - playwright-report/
    expire_in: 30 days
  only:
    - merge_requests
    - main
```

### Azure Pipelines

Create `azure-pipelines.yml`:

```yaml
trigger:
  - main

pr:
  - main

pool:
  vmImage: 'ubuntu-latest'

steps:
- task: NodeTool@0
  inputs:
    versionSpec: '18.x'
    
- script: |
    npm ci
    npx playwright install --with-deps
  displayName: 'Install dependencies'
  
- script: npx playwright test
  displayName: 'Run Playwright tests'
  
- task: PublishTestResults@2
  condition: always()
  inputs:
    testResultsFormat: 'JUnit'
    testResultsFiles: 'test-results/junit.xml'
```

## Workflow: From Generation to Execution

### Without Pipeline (Current State)

1. **User clicks "Generate Automation"** in frontend
2. **Generator creates Playwright script** via Ollama/MCP
3. **Script stored in MongoDB** (automations collection)
4. **User manually copies script** to run locally

### With Git Integration (New)

1. **User clicks "Push to Git"** button
2. **Generator service**:
   - Fetches or generates automation script
   - Calls git service to clone/pull repo
   - Creates feature branch (`feat/test-{id}-{timestamp}`)
   - Writes properly formatted `.spec.js` file
   - Commits changes
   - Pushes to remote
   - Creates Pull/Merge Request
3. **User reviews PR** on GitHub/GitLab/Azure
4. **Manual execution** (for now):
   ```bash
   git checkout feat/test-abc123-1702340567
   npx playwright test tests/generated/login-test.spec.js
   ```
5. **Approve and merge** when test is validated

### With CI/CD Pipeline (Future/Recommended)

1. **Steps 1-3 same as above**
2. **Webhook triggers** CI/CD pipeline automatically
3. **Pipeline runs**:
   - Installs dependencies
   - Runs Playwright tests
   - Generates report
   - Comments results on PR
4. **User reviews** test results in PR
5. **Merge if passing** (or manual approval)

## Repeated Test Execution

### Option 1: Webhook + Scheduled Pipeline

Configure your CI/CD to run tests on:
- **Every PR** (automatic via webhook)
- **Schedule** (e.g., nightly): Cron trigger in pipeline config
- **Manual trigger**: Via Git provider UI

Example GitHub Actions scheduled run:

```yaml
on:
  pull_request:
  push:
  schedule:
    - cron: '0 2 * * *'  # Run daily at 2 AM UTC
  workflow_dispatch:  # Allow manual trigger
```

### Option 2: API-Triggered Execution (Custom)

Create a webhook endpoint in your infrastructure:

```python
# services/executor/main.py
@app.post("/trigger-test-run")
async def trigger_test_run(payload: dict):
    """Trigger test execution via API call"""
    branch = payload.get("branch")
    file_path = payload.get("file_path")
    
    # Option A: Trigger CI/CD pipeline via API
    await trigger_github_workflow(branch)
    
    # Option B: Run locally via docker
    await run_playwright_in_docker(branch, file_path)
    
    return {"status": "triggered", "branch": branch}
```

Then call from frontend:

```javascript
const runTest = async (testCase) => {
  await fetch('http://localhost:8006/trigger-test-run', {
    method: 'POST',
    body: JSON.stringify({
      branch: 'feat/test-abc123',
      file_path: 'tests/generated/test.spec.js'
    })
  });
};
```

### Option 3: Frontend-Triggered via MCP (Current Approach)

Keep using Playwright MCP for immediate execution:

```javascript
// Generate + Execute immediately
const generateAndExecute = async (testCase) => {
  // 1. Generate automation (runs via MCP)
  const automation = await generatorAPI.generateAutomation(testCase.id);
  
  // 2. Also push to Git for versioning
  await generatorAPI.pushTestToGit({
    test_case_id: testCase.id,
    provider: 'github'
  });
  
  // Result: Immediate execution + Git history
};
```

## Getting Close to Pipeline Without One

Since you don't have a pipeline configured yet, here's how to get closest:

### 1. **Git Integration (This PR)**
✅ Tests are version-controlled
✅ Tests can be reviewed via PR/MR
✅ Manual execution instructions provided

### 2. **Manual Execution Workflow**
```bash
# Developer workflow
git fetch origin
git checkout feat/test-xyz
npx playwright test
# Review results, approve PR
```

### 3. **Batch Execution Script**
Create a simple script to run all pending test PRs:

```bash
#!/bin/bash
# run-pending-tests.sh

# Get all open PRs with label "automated-test"
prs=$(gh pr list --label "automated-test" --json number --jq '.[].number')

for pr in $prs; do
  echo "Testing PR #$pr"
  gh pr checkout $pr
  npx playwright test > "results-pr-$pr.txt"
  gh pr comment $pr --body "Test results: $(cat results-pr-$pr.txt)"
done
```

### 4. **Docker-based Local "Pipeline"**
```bash
# Execute test in isolated environment
docker run -v $(pwd):/tests \
  mcr.microsoft.com/playwright:v1.40.0-focal \
  sh -c "cd /tests && npm ci && npx playwright test"
```

### 5. **Next Steps for True Pipeline**

When ready, set up in order:

1. **GitHub Actions** (easiest, free for public repos)
   - Copy `.github/workflows/playwright.yml` template above
   - Commit to repo
   - Automatic on next PR

2. **GitLab CI** (if using GitLab)
   - Copy `.gitlab-ci.yml` template
   - Commit to repo
   - Automatic on next MR

3. **Self-hosted** (if needed)
   - Jenkins, Azure DevOps, CircleCI
   - Requires more setup but more control

## Security Considerations

- ✅ SSH keys stored securely (0600 permissions)
- ✅ Path traversal prevention in git service
- ✅ Branch name validation (no shell injection)
- ✅ Commit message sanitization
- ⚠️ Store tokens in secrets manager (not code)
- ⚠️ Use SSH for private repos (not HTTPS with tokens in URL)
- ⚠️ Review generated tests before merging (security scan for malicious code)

## Troubleshooting

### "Repository not found" error
- Check `TESTS_REPO_URL` is correct
- Verify authentication (SSH key or token)
- Ensure service has network access

### "Permission denied" on push
- Check SSH key is added to Git provider
- Verify token has write permissions
- Check branch protection rules

### "File write failed"
- Check directory permissions in container
- Verify `WORKSPACE_DIR` mount in docker-compose
- Check disk space

### PR/MR creation fails
- Verify provider token has repo:write scope
- Check provider API rate limits
- Ensure base branch exists

## Example Full Workflow

```bash
# 1. Set up environment
export TESTS_REPO_URL="git@github.com:yourorg/tests.git"
export TESTS_REPO_BRANCH="main"
export TEST_FILES_PATH="tests/e2e/generated"

# 2. Start services
docker-compose up -d

# 3. Trigger from frontend or API
curl -X POST http://localhost:8003/push-test-to-git \
  -H "Content-Type: application/json" \
  -d '{"test_case_id": "abc123", "provider": "github"}'

# 4. Response includes PR URL
# Navigate to PR URL, review test

# 5. Manual test execution
git clone git@github.com:yourorg/tests.git
cd tests
git checkout feat/test-abc123-1702340567
npm install
npx playwright test tests/e2e/generated/login-test-abc123.spec.js

# 6. Review results, approve PR, merge

# 7. (Future) CI/CD runs automatically on merge to main
```

## Future Enhancements

- [ ] Automatic test execution via webhook
- [ ] Test result comments on PR/MR
- [ ] Test coverage reports
- [ ] Failed test screenshots in PR
- [ ] Batch test generation (multiple tests → single PR)
- [ ] Test update detection (update existing test instead of creating new)
- [ ] Integration with test management tools
- [ ] Scheduled test runs
- [ ] Test analytics dashboard

## Conclusion

This integration provides a bridge between AI-generated tests and production-ready test automation:

✅ **Version Control**: Tests are tracked in Git
✅ **Code Review**: PRs allow team review before merge
✅ **Reproducibility**: Tests can be run by anyone with repo access
✅ **Auditability**: Git history shows what, when, who

**Without pipeline**: Manual execution, but structured workflow
**With pipeline**: Fully automated test-on-commit flow

This gets you ~80% of the way to a full CI/CD pipeline without requiring one immediately!
