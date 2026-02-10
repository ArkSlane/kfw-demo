# Ollama Service

## Overview

Ollama is an open-source Large Language Model (LLM) inference engine that powers the AI-driven test generation and automation capabilities in this system. It provides a local, self-hosted alternative to cloud-based LLM APIs, enabling intelligent test case generation, automation script creation, and iterative browser testing.

## What the Service Does

### Core Capabilities

1. **Test Case Generation**
   - Converts requirements into Gherkin-formatted test scenarios
   - Generates multiple test variations from single requirement
   - Provides context-aware test step recommendations

2. **Automation Script Generation**
   - Transforms test specifications into executable Playwright code
   - Generates complete browser automation scripts
   - Includes assertions and error handling

3. **Iterative Test Execution**
   - Decides next actions based on current page state
   - Adapts to UI changes dynamically
   - Provides reasoning for each action taken

4. **Natural Language Understanding**
   - Interprets test requirements in plain English
   - Understands context from descriptions and preconditions
   - Generates human-readable explanations

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              Ollama Service                          │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │          Ollama API Server                     │ │
│  │          (Port 11434)                          │ │
│  └─────────────┬──────────────────────────────────┘ │
│                │                                     │
│  ┌─────────────▼──────────────────────────────────┐ │
│  │       Model: gpt-oss:20b                       │ │
│  │       (20 billion parameters)                  │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │       Storage: /root/.ollama                   │ │
│  │       - Model weights                          │ │
│  │       - Configuration                          │ │
│  │       - Cache                                  │ │
│  └────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
          ▲                           ▲
          │                           │
    ┌─────┴──────┐           ┌────────┴────────┐
    │ Generator  │           │ Playwright MCP  │
    │  Service   │           │    Service      │
    └────────────┘           └─────────────────┘
```

## Components

### 1. Ollama Main Service

**Image**: `ollama/ollama:latest`  
**Port**: `11434`  
**Purpose**: Serves LLM inference API

**Configuration:**
```yaml
ollama:
  image: ollama/ollama:latest
  ports:
    - "11434:11434"
  volumes:
    - ollama_data:/root/.ollama
  command: ["serve"]
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - NVIDIA_DRIVER_CAPABILITIES=compute,utility
    - OLLAMA_VULKAN=0
  runtime: nvidia
  restart: unless-stopped
```

### 2. Ollama Init Container

**Image**: `ollama/ollama:latest`  
**Purpose**: Downloads and prepares the model on startup

**Configuration:**
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
```

**Why Init Container?**
- Ensures model is available before services start using it
- Handles large model download (several GB) separately
- Prevents service failures due to missing models
- Downloads happen once, cached in volume

## Model Information

### gpt-oss:20b

**Parameters**: 20 billion  
**Type**: Open-source LLM  
**Size**: ~12 GB  
**Context Window**: Typically 4096-8192 tokens  

**Capabilities:**
- Natural language understanding
- Code generation (JavaScript, Python)
- Structured output (Gherkin, JSON)
- Multi-turn conversations
- Reasoning and planning

**Performance:**
- **With GPU**: 50-150 tokens/second
- **Without GPU (CPU)**: 2-10 tokens/second

**Use Cases in System:**
- Test case generation: Excellent
- Script generation: Very good
- Iterative testing: Good (requires multiple calls)

## Environment Variables

### Ollama Service

| Variable | Value | Description |
|----------|-------|-------------|
| `NVIDIA_VISIBLE_DEVICES` | `all` | GPU access for acceleration |
| `NVIDIA_DRIVER_CAPABILITIES` | `compute,utility` | Required GPU capabilities |
| `OLLAMA_VULKAN` | `0` | Disable Vulkan (use CUDA instead) |

### Client Configuration

Services connecting to Ollama use:

| Variable | Default | Used By |
|----------|---------|---------|
| `OLLAMA_URL` | `http://ollama:11434` | Generator, Playwright-MCP |
| `OLLAMA_MODEL` | `gpt-oss:20b` | Generator |

## Hardware Acceleration

### GPU Support (Recommended)

**Requirements:**
- NVIDIA GPU with CUDA support
- nvidia-docker runtime installed
- NVIDIA drivers installed on host

**Benefits:**
- 10-50x faster inference
- Supports larger models
- Better for real-time use

**Docker Configuration:**
```yaml
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
  - NVIDIA_DRIVER_CAPABILITIES=compute,utility
```

### CPU-Only Mode (Fallback)

Remove these from docker-compose.yml:
```yaml
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
  - NVIDIA_DRIVER_CAPABILITIES=compute,utility
  - OLLAMA_VULKAN=0
```

**Trade-offs:**
- Much slower (2-10 tokens/sec vs 50-150)
- Still functional for development
- May timeout on complex prompts

## Storage

### Volume: ollama_data

**Mount Point**: `/root/.ollama`  
**Purpose**: Persist model weights and configuration

**Contents:**
```
/root/.ollama/
├── models/
│   └── manifests/
│       └── registry.ollama.ai/
│           └── library/
│               └── gpt-oss/
│                   └── 20b/
├── tmp/
└── .cache/
```

**Disk Usage**: ~15-20 GB (for gpt-oss:20b)

**Management:**
```bash
# Check disk usage
docker exec ollama du -sh /root/.ollama

# List downloaded models
docker exec ollama ollama list

# Remove model to free space
docker exec ollama ollama rm gpt-oss:20b
```

## API Endpoints

Ollama exposes a REST API on port 11434.

### Base URL
```
http://localhost:11434
```

Internal (from containers):
```
http://ollama:11434
```

---

## Primary Endpoints

### 1. Generate Completion

#### `POST /api/generate`

Generate text completion from a prompt.

**Request:**
```json
{
  "model": "gpt-oss:20b",
  "prompt": "Generate a Gherkin test scenario for user login",
  "stream": false
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | Model name (e.g., "gpt-oss:20b") |
| `prompt` | string | Yes | Input prompt text |
| `system` | string | No | System prompt to guide behavior |
| `stream` | boolean | No | Stream response (default: true) |
| `options` | object | No | Model parameters (temperature, etc.) |

**Response (stream: false):**
```json
{
  "model": "gpt-oss:20b",
  "created_at": "2025-12-13T10:30:00.000000Z",
  "response": "Feature: User Login\n\n  Scenario: Successful login\n    Given the user is on the login page\n    When the user enters valid credentials\n    Then the user should be logged in",
  "done": true,
  "context": [1234, 5678, ...],
  "total_duration": 3500000000,
  "load_duration": 100000000,
  "prompt_eval_count": 25,
  "prompt_eval_duration": 500000000,
  "eval_count": 50,
  "eval_duration": 2900000000
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `response` | string | Generated text |
| `done` | boolean | True when complete |
| `total_duration` | integer | Total time in nanoseconds |
| `eval_count` | integer | Number of tokens generated |

---

### 2. Chat Completion

#### `POST /api/chat`

Multi-turn conversation with message history.

**Request:**
```json
{
  "model": "gpt-oss:20b",
  "messages": [
    {
      "role": "system",
      "content": "You are a QA automation engineer."
    },
    {
      "role": "user",
      "content": "Generate a Playwright script for testing login"
    }
  ],
  "stream": false
}
```

**Message Roles:**
- `system`: Instructions/context for the model
- `user`: User input
- `assistant`: Previous model responses

**Response:**
```json
{
  "model": "gpt-oss:20b",
  "created_at": "2025-12-13T10:30:00.000000Z",
  "message": {
    "role": "assistant",
    "content": "await page.goto('https://example.com/login');\nawait page.fill('#username', 'test');"
  },
  "done": true
}
```

---

### 3. List Models

#### `GET /api/tags`

List all downloaded models.

**Response:**
```json
{
  "models": [
    {
      "name": "gpt-oss:20b",
      "modified_at": "2025-12-13T08:00:00.000000Z",
      "size": 12884901888,
      "digest": "sha256:abc123...",
      "details": {
        "format": "gguf",
        "family": "llama",
        "parameter_size": "20B",
        "quantization_level": "Q4_0"
      }
    }
  ]
}
```

---

### 4. Show Model Info

#### `POST /api/show`

Get detailed model information.

**Request:**
```json
{
  "name": "gpt-oss:20b"
}
```

**Response:**
```json
{
  "modelfile": "FROM /root/.ollama/models/...",
  "parameters": "num_ctx 4096\ntemperature 0.7",
  "template": "{{ .System }}\n{{ .Prompt }}",
  "details": {
    "format": "gguf",
    "family": "llama",
    "parameter_size": "20B"
  }
}
```

---

### 5. Pull Model

#### `POST /api/pull`

Download a model from the registry.

**Request:**
```json
{
  "name": "gpt-oss:20b",
  "stream": true
}
```

**Response (streaming):**
```json
{"status":"pulling manifest"}
{"status":"downloading","digest":"sha256:...","total":12884901888,"completed":1048576}
{"status":"downloading","digest":"sha256:...","total":12884901888,"completed":2097152}
...
{"status":"success"}
```

---

### 6. Delete Model

#### `DELETE /api/delete`

Remove a model from local storage.

**Request:**
```json
{
  "name": "gpt-oss:20b"
}
```

**Response:**
```json
{
  "status": "success"
}
```

---

## Integration Patterns

### Pattern 1: Simple Generation (Generator Service)

```python
import httpx

async def generate_with_ollama(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "http://ollama:11434/api/generate",
            json={
                "model": "gpt-oss:20b",
                "prompt": prompt,
                "stream": False
            }
        )
        data = response.json()
        return data.get("response", "")
```

**Use Case**: Test case or automation generation

---

### Pattern 2: Guided Generation with System Prompt

```python
async def generate_automation_script(test_steps: str) -> str:
    system_prompt = (
        "You are an automation engineer. Generate Playwright scripts. "
        "Use async/await syntax. Include only executable code."
    )
    
    response = await client.post(
        "http://ollama:11434/api/generate",
        json={
            "model": "gpt-oss:20b",
            "prompt": f"Generate script for:\n{test_steps}",
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,  # Lower = more deterministic
                "top_p": 0.9
            }
        }
    )
    return response.json()["response"]
```

**Use Case**: Structured code generation

---

### Pattern 3: Iterative Conversation (Playwright MCP)

```javascript
async function callOllama(prompt, systemPrompt) {
  const response = await axios.post('http://ollama:11434/api/generate', {
    model: 'gpt-oss:20b',
    prompt: prompt,
    system: systemPrompt,
    stream: false,
    options: {
      temperature: 0.7
    }
  });
  
  return response.data.response;
}

// Multi-turn execution
let context = "Navigate to login page";
for (let i = 0; i < 10; i++) {
  const action = await callOllama(
    `Current state: ${context}\nWhat's the next action?`,
    "You are a QA tester. Respond with single actions only."
  );
  
  // Execute action...
  
  // Update context for next iteration
  context = `Just completed: ${action}. Page now shows: ${pageState}`;
}
```

**Use Case**: Iterative test execution

---

## Video Recording

**Note**: Ollama itself does not handle video recording. Video recording is managed by:
- **Playwright MCP**: Records browser sessions during test execution
- **Generator Service**: Initiates recording by passing video parameters to MCP

Ollama's role is to **decide what actions to perform**, which are then recorded.

**Workflow:**
```
Generator → Ollama (decides action) → Playwright MCP (executes + records) → Video file
```

---

## Configuration & Optimization

### Model Parameters

Control generation behavior via `options`:

```json
{
  "options": {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "num_ctx": 4096,
    "repeat_penalty": 1.1
  }
}
```

**Parameter Guide:**

| Parameter | Range | Effect | Use Case |
|-----------|-------|--------|----------|
| `temperature` | 0.0-2.0 | Randomness | 0.3 for code, 0.7 for creative |
| `top_p` | 0.0-1.0 | Nucleus sampling | 0.9 standard |
| `top_k` | 1-100 | Token diversity | 40 standard |
| `num_ctx` | 512-8192 | Context window | 4096 default |
| `repeat_penalty` | 0.0-2.0 | Avoid repetition | 1.1 default |

### Performance Tuning

**For Faster Responses:**
```json
{
  "options": {
    "num_ctx": 2048,
    "num_predict": 256
  }
}
```

**For Better Quality:**
```json
{
  "options": {
    "temperature": 0.3,
    "top_p": 0.95,
    "num_ctx": 8192
  }
}
```

### Memory Management

**Check Memory Usage:**
```bash
docker stats ollama
```

**Typical Usage:**
- **Idle**: 500 MB - 1 GB
- **During inference**: 8-15 GB (with gpt-oss:20b)

**Out of Memory?**
- Use smaller model (e.g., llama3.1:7b)
- Reduce `num_ctx`
- Add more RAM or GPU VRAM

---

## Troubleshooting

### Model Not Loading

**Symptom:**
```
Error: model not found
```

**Solutions:**
1. Check if model exists:
   ```bash
   docker exec ollama ollama list
   ```

2. Manually pull model:
   ```bash
   docker exec ollama ollama pull gpt-oss:20b
   ```

3. Check ollama-init logs:
   ```bash
   docker logs ollama-init
   ```

---

### Slow Inference (CPU Mode)

**Symptom:** Responses take 30+ seconds

**Solutions:**
1. Verify GPU runtime:
   ```bash
   docker inspect ollama | grep Runtime
   # Should show: "Runtime": "nvidia"
   ```

2. Check GPU visibility:
   ```bash
   docker exec ollama nvidia-smi
   ```

3. Use smaller model:
   ```bash
   docker exec ollama ollama pull llama3.1:7b
   ```

---

### Connection Refused

**Symptom:**
```
Error: connect ECONNREFUSED ollama:11434
```

**Solutions:**
1. Check service running:
   ```bash
   docker ps | grep ollama
   ```

2. Check network:
   ```bash
   docker network inspect ai_testing_v2_app-network
   ```

3. Wait for startup:
   ```bash
   # Ollama takes 10-30s to start
   sleep 30
   ```

---

### Out of Disk Space

**Symptom:**
```
Error: no space left on device
```

**Solutions:**
1. Check volume usage:
   ```bash
   docker exec ollama df -h /root/.ollama
   ```

2. Remove unused models:
   ```bash
   docker exec ollama ollama list
   docker exec ollama ollama rm <model-name>
   ```

3. Increase Docker disk allocation

---

## Best Practices

### 1. Prompt Engineering

**Do:**
- Be specific and clear
- Provide context (test steps, expected behavior)
- Use system prompts to set behavior
- Include examples in prompt for better results

**Don't:**
- Use vague language ("test the thing")
- Exceed context window (check `num_ctx`)
- Chain too many prompts without resetting context

**Example:**
```python
# Good prompt
prompt = """
Generate a Playwright script for testing login functionality.

Requirements:
- Navigate to http://localhost:5173/login
- Fill username: testuser
- Fill password: Test123!
- Click submit button
- Verify redirect to /dashboard

Output only JavaScript code, no explanations.
"""

# Bad prompt
prompt = "make a login test"
```

---

### 2. Error Handling

```python
async def safe_ollama_call(prompt: str) -> str | None:
    try:
        response = await client.post(
            "http://ollama:11434/api/generate",
            json={"model": "gpt-oss:20b", "prompt": prompt, "stream": False},
            timeout=60
        )
        response.raise_for_status()
        return response.json().get("response")
    except httpx.TimeoutException:
        logger.error("Ollama timeout")
        return None
    except httpx.HTTPError as e:
        logger.error(f"Ollama error: {e}")
        return None
```

---

### 3. Resource Management

- **Timeouts**: Always set (30-120s depending on task)
- **Streaming**: Use `stream: true` for long responses
- **Batching**: Avoid parallel calls (Ollama handles one at a time)
- **Caching**: Consider caching responses for identical prompts

---

## Examples

### Example 1: Generate Test Case

```bash
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:20b",
    "prompt": "Generate a Gherkin scenario for user registration with email validation",
    "stream": false
  }'
```

**Response:**
```json
{
  "response": "Feature: User Registration\n\n  Scenario: Register with valid email\n    Given I am on the registration page\n    When I enter a valid email address\n    And I fill in all required fields\n    And I click the register button\n    Then my account should be created\n    And I should receive a confirmation email",
  "done": true
}
```

---

### Example 2: Generate Automation Script

```python
import httpx
import asyncio

async def generate_script():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "gpt-oss:20b",
                "prompt": (
                    "Generate Playwright JavaScript code to:\n"
                    "1. Navigate to https://example.com\n"
                    "2. Click button with id 'login'\n"
                    "3. Wait for navigation\n\n"
                    "Output only code, no markdown."
                ),
                "stream": False,
                "options": {
                    "temperature": 0.3
                }
            },
            timeout=60
        )
        print(response.json()["response"])

asyncio.run(generate_script())
```

---

### Example 3: Check Available Models

```bash
curl http://localhost:11434/api/tags | jq
```

**Response:**
```json
{
  "models": [
    {
      "name": "gpt-oss:20b",
      "size": 12884901888,
      "parameter_size": "20B"
    }
  ]
}
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check if Ollama is responding
curl http://localhost:11434/api/tags

# Check model loaded
docker exec ollama ollama list

# Monitor resource usage
docker stats ollama
```

### Logs

```bash
# View Ollama logs
docker logs ollama

# Follow logs in real-time
docker logs -f ollama

# Check init container logs
docker logs ollama-init
```

### Performance Metrics

Track these metrics for optimization:
- **Response time**: Average time per generation
- **Token rate**: Tokens per second
- **Memory usage**: Peak and average
- **GPU utilization**: % usage during inference

---

## Alternative Models

### Smaller Models (Faster)

```bash
# 7B model - much faster, decent quality
docker exec ollama ollama pull llama3.1:7b

# 3B model - very fast, basic tasks
docker exec ollama ollama pull llama3.2:3b
```

Update `OLLAMA_MODEL` in docker-compose.yml.

### Specialized Models

```bash
# Code-focused
docker exec ollama ollama pull codellama:13b

# Instruction-tuned
docker exec ollama ollama pull mistral:7b-instruct
```

### Model Comparison

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| gpt-oss:20b | 12 GB | Medium | Excellent | Production |
| llama3.1:7b | 4 GB | Fast | Very Good | Development |
| llama3.2:3b | 2 GB | Very Fast | Good | Quick tests |
| codellama:13b | 7 GB | Medium | Excellent | Code generation only |

---

## Security Considerations

### Network Isolation

- Ollama not exposed to internet (internal only)
- Accessible only from app-network
- No authentication required (trusted environment)

### Resource Limits

Consider adding to docker-compose.yml:
```yaml
ollama:
  deploy:
    resources:
      limits:
        memory: 16G
        cpus: '4'
```

### Data Privacy

- All inference happens locally
- No data sent to external APIs
- Model weights stored on local volume
- Prompts/responses never leave infrastructure

---

## Future Enhancements

- [ ] Multiple model support (switch based on task)
- [ ] Model fine-tuning on project-specific data
- [ ] Response caching layer
- [ ] Load balancing across multiple Ollama instances
- [ ] Prometheus metrics export
- [ ] Automated model updates
- [ ] A/B testing different models
