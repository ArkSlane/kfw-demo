# SSH Key Management Guide

## Overview

The Git Service now supports SSH key management for secure Git authentication. This allows you to:
- Store SSH keys securely in a Docker volume
- Use SSH authentication for private repositories
- Manage keys through REST API endpoints
- Automatically configure Git to use stored keys

## Features

### Secure Storage
- Keys stored with **0600 permissions** (owner read/write only)
- Persistent storage in Docker volume (`git_ssh_keys`)
- Automatic validation using `ssh-keygen`
- Invalid keys are rejected before storage

### Multi-Key Support
- Store multiple SSH keys with unique names
- Select specific key per Git operation
- Support for both private and public keys
- Automatic key fingerprint generation

### API Integration
- RESTful API for all key operations
- Comprehensive OpenAPI documentation
- Integrated with clone, pull, push operations
- Automatic SSH configuration

## Getting Started

### Prerequisites

1. **Generate an SSH key pair** (if you don't have one):
   ```bash
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   ```

2. **Add public key to Git provider**:
   - GitHub: Settings → SSH and GPG keys → New SSH key
   - GitLab: Preferences → SSH Keys → Add new key
   - Azure DevOps: User settings → SSH public keys → Add

### Upload SSH Key

#### Using cURL
```bash
# Read the private key
PRIVATE_KEY=$(cat ~/.ssh/id_rsa)

# Upload to Git service
curl -X POST "http://localhost:8007/ssh-keys" \
  -H "Content-Type: application/json" \
  -d "{
    \"key_name\": \"github_deploy\",
    \"private_key\": \"$PRIVATE_KEY\",
    \"public_key\": \"$(cat ~/.ssh/id_rsa.pub)\"
  }"
```

#### Using PowerShell
```powershell
$privateKey = Get-Content "$env:USERPROFILE\.ssh\id_rsa" -Raw
$publicKey = Get-Content "$env:USERPROFILE\.ssh\id_rsa.pub" -Raw

$body = @{
    key_name = "github_deploy"
    private_key = $privateKey
    public_key = $publicKey
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8007/ssh-keys" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

#### Using Python
```python
import requests

with open(os.path.expanduser("~/.ssh/id_rsa")) as f:
    private_key = f.read()

with open(os.path.expanduser("~/.ssh/id_rsa.pub")) as f:
    public_key = f.read()

response = requests.post(
    "http://localhost:8007/ssh-keys",
    json={
        "key_name": "github_deploy",
        "private_key": private_key,
        "public_key": public_key
    }
)

print(response.json())
# Output: {"key_name": "github_deploy", "fingerprint": "2048 SHA256:...", ...}
```

### List SSH Keys

```bash
curl http://localhost:8007/ssh-keys
```

Response:
```json
[
  {
    "key_name": "github_deploy",
    "fingerprint": "2048 SHA256:abc123def456... (RSA)",
    "has_public_key": true,
    "path": "/ssh-keys/github_deploy"
  }
]
```

### Get Key Details

```bash
curl http://localhost:8007/ssh-keys/github_deploy
```

Response includes public key content:
```json
{
  "key_name": "github_deploy",
  "fingerprint": "2048 SHA256:abc123def456... (RSA)",
  "has_public_key": true,
  "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQAB...",
  "path": "/ssh-keys/github_deploy"
}
```

### Delete SSH Key

```bash
curl -X DELETE http://localhost:8007/ssh-keys/github_deploy
```

## Using SSH Keys with Git Operations

### Clone with SSH

```bash
curl -X POST "http://localhost:8007/clone" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "git@github.com:username/private-repo.git",
    "ssh_key_name": "github_deploy",
    "branch": "main"
  }'
```

### Pull with SSH

```bash
curl -X POST "http://localhost:8007/pull" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "private-repo",
    "ssh_key_name": "github_deploy"
  }'
```

### Push with SSH

```bash
curl -X POST "http://localhost:8007/push" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "private-repo",
    "branch": "main",
    "ssh_key_name": "github_deploy"
  }'
```

## Supported SSH URL Formats

The Git service accepts these SSH URL formats:

### GitHub
```
git@github.com:username/repository.git
```

### GitLab
```
git@gitlab.com:username/repository.git
```

### Azure DevOps
```
git@ssh.dev.azure.com:v3/organization/project/repository
```

### Custom Git Server
```
git@your-server.com:path/to/repository.git
```

## Security Best Practices

### Key Generation
- **Use strong keys**: RSA 4096-bit or Ed25519
- **Add passphrase**: Extra layer of protection (not currently supported by service)
- **Unique keys**: Different keys for different environments

```bash
# RSA 4096-bit
ssh-keygen -t rsa -b 4096 -C "deploy@example.com"

# Ed25519 (more modern)
ssh-keygen -t ed25519 -C "deploy@example.com"
```

### Key Management
- **Rotate keys regularly**: Change keys every 90-180 days
- **Limit key access**: Use deploy keys with read-only access when possible
- **Monitor usage**: Check Git provider logs for unauthorized access
- **Delete unused keys**: Remove old keys from both service and Git provider

### Access Control
- **Environment variables**: Don't commit keys to repositories
- **Restrict API access**: Use firewall rules to limit who can upload keys
- **Audit logs**: Track key usage and API calls
- **Backup keys**: Keep secure backups of keys in password manager

## Architecture

### Storage Location
```
/ssh-keys/              # Docker volume mount
├── github_deploy       # Private key (0600)
├── github_deploy.pub   # Public key (0644)
├── gitlab_ci           # Private key (0600)
├── known_hosts         # SSH known hosts file
└── config              # SSH config file (auto-generated)
```

### SSH Configuration
The service automatically configures Git to use SSH:
```bash
# Sets GIT_SSH_COMMAND environment variable
export GIT_SSH_COMMAND="ssh -i /ssh-keys/github_deploy -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/ssh-keys/known_hosts"
```

### Key Validation
All keys are validated before storage:
```bash
ssh-keygen -l -f /ssh-keys/github_deploy
# Output: 2048 SHA256:abc123... (RSA)
```

## API Reference

### POST /ssh-keys
Upload a new SSH key.

**Request:**
```json
{
  "key_name": "string",       // Required: Alphanumeric, underscore, hyphen
  "private_key": "string",    // Required: PEM format
  "public_key": "string"      // Optional: Public key content
}
```

**Response (200):**
```json
{
  "key_name": "string",
  "fingerprint": "string",
  "has_public_key": boolean,
  "path": "string"
}
```

**Errors:**
- `400`: Invalid key format or name
- `409`: Key already exists
- `500`: Storage failure

### GET /ssh-keys
List all stored SSH keys.

**Response (200):**
```json
[
  {
    "key_name": "string",
    "fingerprint": "string",
    "has_public_key": boolean,
    "path": "string"
  }
]
```

### GET /ssh-keys/{key_name}
Get details about a specific SSH key.

**Response (200):**
```json
{
  "key_name": "string",
  "fingerprint": "string",
  "has_public_key": boolean,
  "public_key": "string",    // Only if public key exists
  "path": "string"
}
```

**Errors:**
- `404`: Key not found

### DELETE /ssh-keys/{key_name}
Delete an SSH key.

**Response (200):**
```json
{
  "key_name": "string",
  "deleted": true
}
```

**Errors:**
- `404`: Key not found

## Troubleshooting

### Key Upload Fails with "Invalid SSH key"

**Symptoms:**
```json
{"detail": "Invalid SSH key: key is not valid format"}
```

**Solutions:**
1. Verify key format (must start with `-----BEGIN`)
2. Check for corrupted key file
3. Ensure no extra whitespace or characters
4. Try re-generating the key

### Clone Fails with "Permission denied (publickey)"

**Symptoms:**
```
Clone failed: Permission denied (publickey)
```

**Solutions:**
1. Verify public key is added to Git provider
2. Check key name matches the one uploaded
3. Test key manually:
   ```bash
   docker exec -it ai_testing_v2-git-1 ssh -T git@github.com
   ```
4. Verify key permissions in container:
   ```bash
   docker exec -it ai_testing_v2-git-1 ls -la /ssh-keys/
   ```

### Wrong Key Used

**Symptoms:**
Multiple keys exist but wrong one is being used.

**Solutions:**
1. Explicitly specify `ssh_key_name` in API call
2. Check key name spelling
3. List keys to verify name: `GET /ssh-keys`

### Known Hosts Warning

**Symptoms:**
```
The authenticity of host 'github.com' can't be established
```

**Solution:**
The service automatically uses `StrictHostKeyChecking=accept-new` to accept new hosts on first connection. The fingerprint is saved to `/ssh-keys/known_hosts`.

## Examples

### Complete Workflow: Private Repository

```bash
# 1. Generate SSH key
ssh-keygen -t ed25519 -C "automation@example.com" -f ~/.ssh/automation_key

# 2. Add public key to GitHub
cat ~/.ssh/automation_key.pub
# Copy output and add to GitHub Settings → SSH Keys

# 3. Upload private key to service
curl -X POST "http://localhost:8007/ssh-keys" \
  -H "Content-Type: application/json" \
  -d "{
    \"key_name\": \"automation_key\",
    \"private_key\": \"$(cat ~/.ssh/automation_key)\"
  }"

# 4. Clone private repository
curl -X POST "http://localhost:8007/clone" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "git@github.com:myorg/private-tests.git",
    "ssh_key_name": "automation_key"
  }'

# 5. Make changes and push
curl -X POST "http://localhost:8007/commit" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "private-tests",
    "message": "Update test cases"
  }'

curl -X POST "http://localhost:8007/push" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "private-tests",
    "ssh_key_name": "automation_key"
  }'
```

### Automation Script: Key Rotation

```python
import requests
import os
from datetime import datetime

GIT_SERVICE = "http://localhost:8007"
OLD_KEY_NAME = "deploy_2024_q3"
NEW_KEY_NAME = f"deploy_{datetime.now().strftime('%Y_q%q')}"

# Generate new key
os.system(f"ssh-keygen -t ed25519 -f ~/.ssh/{NEW_KEY_NAME} -N ''")

# Upload new key
with open(os.path.expanduser(f"~/.ssh/{NEW_KEY_NAME}")) as f:
    private_key = f.read()

response = requests.post(
    f"{GIT_SERVICE}/ssh-keys",
    json={
        "key_name": NEW_KEY_NAME,
        "private_key": private_key
    }
)
print(f"New key uploaded: {response.json()}")

# Test new key with a pull
response = requests.post(
    f"{GIT_SERVICE}/pull",
    json={
        "repo_path": "test-repo",
        "ssh_key_name": NEW_KEY_NAME
    }
)

if response.status_code == 200:
    # Delete old key
    requests.delete(f"{GIT_SERVICE}/ssh-keys/{OLD_KEY_NAME}")
    print(f"Old key {OLD_KEY_NAME} deleted")
else:
    print(f"New key test failed: {response.text}")
```

## Docker Volume Management

### Backup SSH Keys

```bash
# Create backup directory
mkdir -p ssh-keys-backup

# Copy keys from Docker volume
docker run --rm \
  -v ai_testing_v2_git_ssh_keys:/source \
  -v $(pwd)/ssh-keys-backup:/backup \
  busybox \
  cp -r /source/. /backup/
```

### Restore SSH Keys

```bash
# Restore keys to Docker volume
docker run --rm \
  -v ai_testing_v2_git_ssh_keys:/destination \
  -v $(pwd)/ssh-keys-backup:/backup \
  busybox \
  cp -r /backup/. /destination/
```

### Inspect Volume

```bash
# List contents of ssh-keys volume
docker run --rm \
  -v ai_testing_v2_git_ssh_keys:/ssh-keys \
  busybox \
  ls -la /ssh-keys/
```

## Migration from HTTPS to SSH

If you have repositories cloned with HTTPS tokens, you can switch to SSH:

```bash
# 1. Upload SSH key
# (see "Upload SSH Key" section above)

# 2. Update remote URL in existing repository
docker exec -it ai_testing_v2-git-1 sh -c "
  cd /workspace/my-repo
  git remote set-url origin git@github.com:username/my-repo.git
"

# 3. Use SSH for future operations
curl -X POST "http://localhost:8007/pull" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "my-repo",
    "ssh_key_name": "github_deploy"
  }'
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Deploy Tests
on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Upload SSH Key
        run: |
          curl -X POST "http://git-service:8007/ssh-keys" \
            -H "Content-Type: application/json" \
            -d "{
              \"key_name\": \"ci_deploy\",
              \"private_key\": \"${{ secrets.DEPLOY_SSH_KEY }}\"
            }"
      
      - name: Clone Repository
        run: |
          curl -X POST "http://git-service:8007/clone" \
            -H "Content-Type: application/json" \
            -d '{
              "repo_url": "git@github.com:org/tests.git",
              "ssh_key_name": "ci_deploy"
            }'
```

### GitLab CI Example

```yaml
deploy:
  script:
    - |
      curl -X POST "http://git-service:8007/ssh-keys" \
        -H "Content-Type: application/json" \
        -d "{
          \"key_name\": \"gitlab_ci\",
          \"private_key\": \"$SSH_PRIVATE_KEY\"
        }"
    - |
      curl -X POST "http://git-service:8007/clone" \
        -H "Content-Type: application/json" \
        -d '{
          "repo_url": "git@gitlab.com:org/tests.git",
          "ssh_key_name": "gitlab_ci"
        }'
```

## FAQ

### Q: Can I use keys with passphrases?
**A:** Currently, the service does not support SSH keys with passphrases. Generate keys without passphrases or use `ssh-agent` manually.

### Q: How many keys can I store?
**A:** There is no hard limit, but keep it reasonable (< 100 keys) for performance.

### Q: Are keys encrypted at rest?
**A:** Keys are stored with 0600 permissions in a Docker volume. For encryption at rest, use Docker volume encryption or encrypted filesystems.

### Q: Can I retrieve a private key after upload?
**A:** No, for security reasons. Only public keys can be retrieved via API.

### Q: What happens if I delete the Docker volume?
**A:** All stored SSH keys will be lost. Always maintain backups of important keys.

### Q: Can I use the same key for multiple providers?
**A:** Yes, one key can be used with multiple Git providers (GitHub, GitLab, etc.) if the public key is added to all of them.

### Q: How do I know which key is being used?
**A:** Check the `GIT_SSH_COMMAND` environment variable or review Docker logs:
```bash
docker logs ai_testing_v2-git-1
```

## Next Steps

1. **Generate and upload your first SSH key**
2. **Test with a private repository clone**
3. **Set up key rotation schedule**
4. **Integrate with your CI/CD pipeline**
5. **Review security best practices**

For more information, see:
- [Git Service API Documentation](http://localhost:8007/docs)
- [GitHub SSH Key Documentation](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
- [GitLab SSH Key Documentation](https://docs.gitlab.com/ee/user/ssh.html)
