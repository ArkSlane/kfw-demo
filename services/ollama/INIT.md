# Ollama Init Container

## Overview

The Ollama Init Container is a specialized initialization service that ensures the required LLM model is downloaded and ready before other services attempt to use it. It runs as a one-time setup task at system startup.

## Purpose

### Problem It Solves

**Without Init Container:**
```
1. System starts
2. Generator service tries to call Ollama
3. Ollama returns "model not found"
4. Generator fails
5. User must manually run: docker exec ollama ollama pull gpt-oss:20b
6. Restart services
```

**With Init Container:**
```
1. System starts
2. Ollama-init waits for Ollama to be ready
3. Ollama-init downloads model automatically
4. Model is cached and ready
5. Generator and other services work immediately
```

## How It Works

```
┌─────────────────────────────────────────────────────┐
│               Docker Compose Startup                │
│                                                     │
│  1. Start Ollama Service                           │
│     └─ ollama serve (port 11434)                   │
│                                                     │
│  2. Start Ollama-Init (depends_on: ollama)         │
│     ├─ Wait 2 seconds for Ollama readiness         │
│     ├─ Execute: ollama pull gpt-oss:20b            │
│     │   ├─ Download model from registry            │
│     │   ├─ Save to /root/.ollama volume            │
│     │   └─ Exit when complete                      │
│     └─ Container stops (job done)                  │
│                                                     │
│  3. Start dependent services                       │
│     ├─ Generator (can now use Ollama)              │
│     └─ Playwright-MCP (can now use Ollama)         │
└─────────────────────────────────────────────────────┘
```

## Configuration

### Docker Compose Setup

```yaml
ollama-init:
  image: ollama/ollama:latest
  depends_on:
    - ollama
  entrypoint: ["/bin/sh", "-c"]
  command: "sleep 2 && ollama pull gpt-oss:20b"
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - NVIDIA_DRIVER_CAPABILITIES=compute,utility
  networks:
    - app-network
```

### Key Configuration

| Field | Value | Purpose |
|-------|-------|---------|
| `image` | `ollama/ollama:latest` | Same image as main Ollama service |
| `depends_on` | `ollama` | Wait for Ollama service to start |
| `entrypoint` | `["/bin/sh", "-c"]` | Override default to run shell command |
| `command` | `"sleep 2 && ollama pull gpt-oss:20b"` | Wait then download model |

### Why the 2-Second Sleep?

```bash
sleep 2 && ollama pull gpt-oss:20b
```

**Reason:** Ollama service needs time to start API server

- Container starts ≠ API ready
- Without sleep: `ollama pull` fails with connection error
- 2 seconds is usually sufficient for API initialization

**Alternative (more robust):**
```bash
until curl -f http://ollama:11434/api/tags; do
  echo "Waiting for Ollama..."
  sleep 2
done
ollama pull gpt-oss:20b
```

## Execution Process

### Step-by-Step Flow

1. **Container Starts**
   ```
   [ollama-init] Container created
   [ollama-init] Waiting for dependencies...
   [ollama-init] ollama service is up
   [ollama-init] Starting initialization
   ```

2. **Wait for Ollama Readiness**
   ```bash
   sleep 2
   ```
   
3. **Pull Model**
   ```bash
   ollama pull gpt-oss:20b
   ```
   
   **Console Output:**
   ```
   pulling manifest
   pulling 8934d96d3f08... 100% ▕████████████████▏ 6.7 GB
   pulling 966de95ca8a6... 100% ▕████████████████▏ 1.4 KB
   pulling fcc5a6bec9da... 100% ▕████████████████▏ 7.7 KB
   pulling a70ff7e570d9... 100% ▕████████████████▏ 6.0 KB
   pulling 56bb8bd477a5... 100% ▕████████████████▏  96 B
   pulling 34bb5ab01051... 100% ▕████████████████▏ 561 B
   verifying sha256 digest
   writing manifest
   success
   ```

4. **Container Exits**
   ```
   [ollama-init] Model download complete
   [ollama-init] Exiting with code 0
   ```

### Download Time

| Connection | Model Size | Time |
|------------|------------|------|
| 1 Gbps | 12 GB | ~2 minutes |
| 100 Mbps | 12 GB | ~15 minutes |
| 10 Mbps | 12 GB | ~2.5 hours |

**First run:** Downloads full model  
**Subsequent runs:** Checks cache, skips download if present

## Environment Variables

### GPU Configuration

```yaml
environment:
  - NVIDIA_VISIBLE_DEVICES=all
  - NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

**Purpose:** Allows init container to access GPU for model preparation

**Note:** Model download itself doesn't require GPU, but having consistent config prevents issues.

### OLLAMA_HOST (Implicit)

The init container automatically connects to `http://ollama:11434` via Docker networking.

## Storage & Caching

### Shared Volume

Both `ollama` and `ollama-init` access the same volume:

```yaml
volumes:
  ollama_data:

services:
  ollama:
    volumes:
      - ollama_data:/root/.ollama
  
  ollama-init:
    # Implicitly uses Ollama's client which writes to volume
```

**Cache Behavior:**

| Scenario | Behavior |
|----------|----------|
| First startup | Downloads model (~12 GB, 2-15 min) |
| Restart containers | Checks cache, skips download (< 5 sec) |
| Volume deleted | Downloads again |
| Model updated | Downloads delta (only changed layers) |

### Checking Cache

```bash
# List models in volume
docker exec ollama ollama list

# Check disk usage
docker exec ollama du -sh /root/.ollama
```

**Example Output:**
```
NAME            ID              SIZE    MODIFIED
gpt-oss:20b     abc123def456    12 GB   2 hours ago
```

## Lifecycle

### Container Lifecycle

```
Create → Run → Complete → Stop → Remove (optional)
```

**Status Progression:**
```bash
docker ps -a | grep ollama-init

# Starting
ai_testing_v2-ollama-init-1   Up 3 seconds

# Downloading
ai_testing_v2-ollama-init-1   Up 1 minute

# Complete
ai_testing_v2-ollama-init-1   Exited (0) 10 seconds ago
```

### Restart Behavior

```yaml
# No restart policy specified
# Container runs once and exits
```

**On system restart:**
1. Ollama-init runs again
2. Checks if model exists
3. Skips download if cached
4. Exits quickly (< 5 seconds)

## Troubleshooting

### Model Not Downloaded

**Symptom:**
```
Error: model 'gpt-oss:20b' not found
```

**Check init container logs:**
```bash
docker logs ollama-init
```

**Common Causes:**

1. **Init container failed:**
   ```
   Error: connect ECONNREFUSED ollama:11434
   ```
   
   **Solution:** Increase sleep time:
   ```yaml
   command: "sleep 5 && ollama pull gpt-oss:20b"
   ```

2. **Network timeout:**
   ```
   Error: context deadline exceeded
   ```
   
   **Solution:** Check internet connection, retry:
   ```bash
   docker-compose restart ollama-init
   ```

3. **Disk space:**
   ```
   Error: no space left on device
   ```
   
   **Solution:** Free up space, increase Docker disk allocation

---

### Init Container Stuck

**Symptom:** Container running for > 30 minutes

**Check progress:**
```bash
docker logs -f ollama-init
```

**If hung:**
```bash
# Kill and restart
docker-compose kill ollama-init
docker-compose up -d ollama-init
```

---

### Wrong Model Downloaded

**Symptom:** Wrong model in cache

**Fix:**
```bash
# Remove wrong model
docker exec ollama ollama rm wrong-model:tag

# Restart init to download correct one
docker-compose restart ollama-init
```

---

## Alternative Approaches

### Approach 1: Manual Download (Not Recommended)

```bash
# Start Ollama
docker-compose up -d ollama

# Wait
sleep 10

# Manually pull
docker exec ollama ollama pull gpt-oss:20b

# Start other services
docker-compose up -d
```

**Drawbacks:**
- Requires manual intervention
- Error-prone
- Not automated

---

### Approach 2: Health Check (More Robust)

```yaml
ollama-init:
  image: ollama/ollama:latest
  depends_on:
    - ollama
  entrypoint: ["/bin/sh", "-c"]
  command: |
    until curl -f http://ollama:11434/api/tags > /dev/null 2>&1; do
      echo "Waiting for Ollama API..."
      sleep 2
    done
    echo "Ollama is ready, pulling model..."
    ollama pull gpt-oss:20b
    echo "Model ready!"
```

**Benefits:**
- More reliable (waits for actual API readiness)
- Better logging
- Handles slow Ollama startup

**Drawbacks:**
- Slightly more complex
- Requires curl in container (already present)

---

### Approach 3: Docker Healthcheck

```yaml
ollama:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
    interval: 5s
    timeout: 3s
    retries: 10
  
ollama-init:
  depends_on:
    ollama:
      condition: service_healthy
  command: "ollama pull gpt-oss:20b"
```

**Benefits:**
- No sleep required
- Waits for actual health
- Clean separation

**Drawbacks:**
- Requires Docker Compose v2.1+
- More YAML config

---

## Best Practices

### 1. Log Monitoring

Always check init logs after first startup:
```bash
docker-compose up -d
docker logs -f ollama-init
```

**Expected output:**
```
pulling manifest
pulling 8934d96d3f08... 100%
...
success
```

---

### 2. Timeout Handling

For slow networks, increase sleep or add retry logic:
```yaml
command: |
  for i in 1 2 3; do
    sleep 2
    if ollama pull gpt-oss:20b; then
      echo "Success!"
      exit 0
    fi
    echo "Attempt $i failed, retrying..."
  done
  echo "Failed after 3 attempts"
  exit 1
```

---

### 3. Model Verification

Verify model after init completes:
```bash
docker exec ollama ollama list | grep gpt-oss:20b
```

**Should output:**
```
gpt-oss:20b    abc123def456    12 GB    2 hours ago
```

---

### 4. Multiple Models

Pull multiple models in one init:
```yaml
command: |
  sleep 2
  ollama pull gpt-oss:20b
  ollama pull llama3.1:7b
  echo "All models ready"
```

---

## Performance Impact

### Startup Time

| Scenario | Time |
|----------|------|
| **First run** (download model) | 2-15 minutes |
| **Cached** (model exists) | 3-5 seconds |
| **Multiple models** | Multiply by number of models |

### System Resources

**During Download:**
- **Network**: ~10-100 Mbps sustained
- **Disk I/O**: ~50-200 MB/s writes
- **CPU**: ~5-10% (minimal)
- **Memory**: ~500 MB

**After Complete:**
- Container exits, resources released
- Only volume storage remains (~12 GB)

---

## Advanced Configuration

### Custom Model Registry

```yaml
command: "sleep 2 && OLLAMA_API_BASE_URL=http://custom-registry:11434 ollama pull custom-model:latest"
```

### Pre-downloaded Models

Mount pre-downloaded model directory:
```yaml
ollama-init:
  volumes:
    - ./models:/models
  command: "sleep 2 && ollama create custom-model -f /models/Modelfile"
```

### Skip Init (Development)

Comment out init container to save time if model already cached:
```yaml
# ollama-init:
#   image: ollama/ollama:latest
#   ...
```

**Use when:**
- Model already downloaded
- Testing non-LLM features
- Rapid iteration cycles

---

## Monitoring & Debugging

### Check Init Status

```bash
# View all containers including stopped
docker-compose ps -a

# Check exit code
docker inspect ollama-init --format='{{.State.ExitCode}}'
# 0 = success, non-zero = failure
```

### View Download Progress

```bash
docker logs -f ollama-init
```

**Progress indicators:**
```
pulling 8934d96d3f08... 45% ▕████████░░░░░░░░▏ 3.0 GB
```

### Validate Model

After init completes:
```bash
# Check model exists
docker exec ollama ollama list

# Test model
docker exec ollama ollama run gpt-oss:20b "Hello"
```

---

## Common Issues & Solutions

### Issue: "Connection refused to ollama:11434"

**Cause:** Ollama service not ready yet

**Solution:**
```yaml
command: "sleep 5 && ollama pull gpt-oss:20b"
# Increase sleep from 2 to 5 seconds
```

---

### Issue: "Failed to pull model: context deadline exceeded"

**Cause:** Network timeout, slow connection

**Solution:**
```bash
# Manually pull with longer timeout
docker exec ollama sh -c "OLLAMA_MAX_LOADED_MODELS=1 ollama pull gpt-oss:20b"
```

---

### Issue: Container exits immediately with code 1

**Cause:** Command failed

**Debug:**
```bash
# Check logs
docker logs ollama-init

# Run manually
docker run --rm --network ai_testing_v2_app-network ollama/ollama:latest \
  sh -c "sleep 2 && ollama pull gpt-oss:20b"
```

---

## Integration with System

### Service Dependencies

```
ollama-init
    ↓ (provides model)
ollama
    ↓ (used by)
generator, playwright-mcp
```

### Startup Order

1. `mongo` (independent)
2. `ollama` (independent)
3. `ollama-init` (depends on ollama)
4. Other services (depend on ollama being ready)

**Recommendation:** Add `depends_on: ollama` to services using LLM:

```yaml
generator:
  depends_on:
    - ollama
    - mongo
```

---

## Maintenance

### Update Model

```bash
# Remove old version
docker exec ollama ollama rm gpt-oss:20b

# Restart init to download new version
docker-compose restart ollama-init
```

### Clear Cache

```bash
# Stop services
docker-compose down

# Remove volume
docker volume rm ai_testing_v2_ollama_data

# Restart (will trigger re-download)
docker-compose up -d
```

### Change Model

Update docker-compose.yml:
```yaml
ollama-init:
  command: "sleep 2 && ollama pull llama3.1:7b"
```

And update services:
```yaml
generator:
  environment:
    - OLLAMA_MODEL=llama3.1:7b
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

---

## Summary

The Ollama Init Container is a simple but critical component that:

✅ **Automates** model download  
✅ **Ensures** model availability before services start  
✅ **Handles** first-time setup transparently  
✅ **Caches** models to avoid re-downloads  
✅ **Exits** cleanly after completing its job  

**Best Practice:** Always monitor init logs on first deployment to ensure successful model download.
