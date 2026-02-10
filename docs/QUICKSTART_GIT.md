# Quick Start: Git Integration

## 🚀 Setup (5 minutes)

### 1. Environment Variables

Add to `docker-compose.yml`:

```yaml
generator:
  environment:
    - TESTS_REPO_URL=https://github.com/your-org/your-tests-repo.git
    - TESTS_REPO_BRANCH=main
    - TEST_FILES_PATH=tests/generated

git:
  environment:
    - GITHUB_TOKEN=ghp_your_token_here
```

### 2. Start Services

```bash
docker-compose up -d generator git
```

### 3. Test It!

```bash
curl -X POST http://localhost:8003/push-test-to-git \
  -H "Content-Type: application/json" \
  -d '{"test_case_id": "YOUR_TEST_ID", "provider": "github"}'
```

## 📋 Usage Checklist

- [ ] Set `TESTS_REPO_URL` environment variable
- [ ] Set `GITHUB_TOKEN` (or GITLAB/AZURE token)
- [ ] Create test repository on Git provider
- [ ] Call `/push-test-to-git` endpoint
- [ ] Review PR on GitHub/GitLab/Azure
- [ ] Run test manually: `git checkout <branch> && npx playwright test`
- [ ] Merge PR when validated

## 🔥 Frontend Integration (Copy-Paste)

```javascript
// Add to TestCases.jsx
const handlePushToGit = async (testCase) => {
  try {
    const result = await generatorAPI.pushTestToGit({
      test_case_id: testCase.id,
      provider: 'github'
    });
    toast.success(`PR created: ${result.git_result.pr_url}`);
    window.open(result.git_result.pr_url, '_blank');
  } catch (error) {
    toast.error('Failed to push test to Git');
  }
};

// Add button in render
<Button onClick={() => handlePushToGit(testCase)}>
  Push to Git
</Button>
```

## 🔧 API Endpoints

### Generate & Push Test
```http
POST http://localhost:8003/push-test-to-git
Content-Type: application/json

{
  "test_case_id": "64f1a2b3c4d5e6f7",
  "provider": "github",
  "repo_url": "https://github.com/org/repo.git",  # optional
  "base_branch": "main",  # optional
  "ssh_key_name": "my-key"  # optional, for private repos
}
```

**Response**:
```json
{
  "success": true,
  "pr_url": "https://github.com/org/repo/pull/42",
  "branch_name": "feat/test-64f1a2b3-1702340567",
  "file_path": "tests/generated/test-name.spec.js"
}
```

## 🔐 SSH Keys (for private repos)

```bash
# Generate key
ssh-keygen -t ed25519 -f ./ssh-keys/my-repo-key

# Add to Git provider (GitHub example)
cat ./ssh-keys/my-repo-key.pub | gh ssh-key add -

# Use in API call
{
  "test_case_id": "abc123",
  "provider": "github",
  "ssh_key_name": "my-repo-key"
}
```

## ⚡ Common Commands

### Run test locally
```bash
git clone <repo-url>
cd <repo>
git checkout feat/test-abc123-1702340567
npm install
npx playwright test tests/generated/test-name.spec.js
```

### Check PR status
```bash
gh pr view 42
gh pr checks 42
```

### Run all generated tests
```bash
npx playwright test tests/generated/
```

## 🐛 Troubleshooting

| Error | Solution |
|-------|----------|
| "Repository not found" | Check `TESTS_REPO_URL` and token |
| "Permission denied" | Verify token has `repo` write scope |
| "File write failed" | Check `WORKSPACE_DIR` is writable |
| PR creation fails | Verify token, check rate limits |

## 📊 Workflow Diagram

```
User clicks "Push to Git"
         ↓
Generator fetches test case
         ↓
Check if automation exists
    ↙         ↘
  Yes         No → Generate via Ollama
    ↘         ↙
Format as Playwright test file
         ↓
Clone/pull repository
         ↓
Create feature branch
         ↓
Write test file
         ↓
Commit changes
         ↓
Push to remote
         ↓
Create Pull Request
         ↓
Return PR URL to user
```

## 🎯 Next Steps

**Without CI/CD Pipeline**:
1. Review PR manually
2. Run test: `npx playwright test <file>`
3. Approve and merge

**With CI/CD Pipeline** (future):
1. PR triggers test automatically
2. Review results in PR
3. Merge if passing

## 📚 Full Documentation

See `docs/GIT_INTEGRATION.md` for:
- Complete setup instructions
- CI/CD configuration examples
- Security considerations
- Advanced usage

## 💡 Tips

- Use descriptive test case titles (becomes filename)
- Review generated tests before merging
- Set up branch protection rules
- Use scheduled runs for regression testing
- Keep test repository separate from app code

## ✅ Success Indicators

You're successfully using Git integration when:
- ✅ Tests are in Git repository
- ✅ PRs created automatically
- ✅ Team can review tests
- ✅ Tests run consistently
- ✅ History is tracked

---

**Need help?** Check `docs/GIT_INTEGRATION.md` or `docs/IMPLEMENTATION_SUMMARY.md`
