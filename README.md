# AI Testing Platform v2

AI-powered test case generation and execution platform with automated browser testing capabilities.

## Architecture

### Services

| Service | Port | Purpose | Status |
|---------|------|---------|--------|
| Requirements | 8001 | Requirement management | ✅ Production |
| TestCases | 8002 | Test case CRUD | ✅ Production |
| Generator | 8003 | AI test generation | ✅ Production |
| Releases | 8004 | Release management | ✅ Production |
| Executions | 8005 | Test execution tracking | ✅ Production |
| Automations | 8006 | Automation management + execution | ✅ Production |
| Git | 8007 | Git operations + PR/MR management | ✅ Beta |
| Playwright-MCP | 3000 | Browser automation engine | ✅ Production |
| Ollama | 11434 | LLM inference | ✅ Production |
| Frontend | 5173 | React + Vite UI | ✅ Production |
| MongoDB | 27017 | Database | ✅ Production |

### Tech Stack

- **Backend**: Python + FastAPI (async)
- **Frontend**: React + Vite + TailwindCSS
- **Database**: MongoDB (Motor async driver)
- **LLM**: Ollama (self-hosted)
- **Automation**: Playwright (Node.js MCP server)
- **Infrastructure**: Docker + Docker Compose

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend development)

### Start All Services

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### Access Services

- **Frontend**: http://localhost:5173
- **Requirements API**: http://localhost:8001/docs
- **TestCases API**: http://localhost:8002/docs
- **Generator API**: http://localhost:8003/docs
- **Releases API**: http://localhost:8004/docs
- **Executions API**: http://localhost:8005/docs
- **Automations API**: http://localhost:8006/docs
- **Git API**: http://localhost:8007/docs

## Features

### ✅ Core Features

- **AI Test Generation**: Generate test cases from requirements using Ollama
- **Static Automation**: Generate Playwright scripts from Gherkin
- **Execution-Based Automation**: Generate scripts from manual test executions
- **Video Recording**: Record browser sessions for all test runs
- **Multi-Provider Git**: Support for GitHub, GitLab, Azure DevOps
- **Release Tracking**: Organize requirements and tests by release
- **Execution History**: Track all test runs with videos and results

### 🔧 Platform Features

- **Health Checks**: Enhanced endpoints with dependency monitoring
- **Error Handling**: Standardized error responses across all services
- **Input Validation**: Comprehensive security validation (Git service)
- **Video Retention**: Automatic cleanup of old recordings (30 days)

## Development

### Running Tests

```bash
# Requirements service tests
cd services/requirements
$env:PYTHONPATH="..\..\"; pytest tests/ -v --tb=short

# Releases service tests
cd services/releases
$env:PYTHONPATH="..\..\"; pytest tests/ -v --tb=short
```

### Project Structure

```
.
├── docker-compose.yml           # All service definitions
├── ROADMAP.md                  # Feature roadmap
├── shared/                     # Shared Python modules
│   ├── db.py                   # Database connection
│   ├── models.py               # Pydantic models
│   ├── settings.py             # Configuration
│   ├── errors.py               # Error handling
│   ├── health.py               # Health checks
├── frontend/                   # React frontend
│   ├── src/
│   └── package.json
└── services/                   # Backend services
    ├── requirements/
    ├── testcases/
    ├── generator/
    ├── releases/
    ├── executions/
    ├── automations/
    ├── git/
    ├── playwright-mcp/
    └── ollama/
```

## Configuration

### Environment Variables

```bash
# MongoDB
MONGO_URL=mongodb://localhost:27017
DB_NAME=aitp

# Git Providers (optional)
GITHUB_TOKEN=ghp_xxxxx
GITLAB_TOKEN=glpat-xxxxx
AZURE_PAT=xxxxx
```

### Docker Volumes

- **mongodb-data**: Persistent MongoDB data
- **videos**: Test execution recordings (shared across services)

## API Documentation

Each service provides OpenAPI/Swagger documentation:

- Requirements: http://localhost:8001/docs
- TestCases: http://localhost:8002/docs
- Generator: http://localhost:8003/docs
- Releases: http://localhost:8004/docs
- Executions: http://localhost:8005/docs
- Automations: http://localhost:8006/docs
- Git: http://localhost:8007/docs

## Roadmap

See [ROADMAP.md](ROADMAP.md) for:
- Planned features (v1.1, v1.2, v1.3, v2.0)
- Technical debt tracking
- Decision log
- Success metrics

## Documentation
- **[ROADMAP.md](ROADMAP.md)**: Product roadmap and planning
- **Service READMEs**: Each service has its own README with specific details

## Troubleshooting

### Services Not Starting

```bash
# Check logs
docker-compose logs [service-name]

# Restart specific service
docker-compose restart [service-name]

# Rebuild service
docker-compose up -d --build [service-name]
```

### MongoDB Connection Issues

```bash
# Ensure MongoDB is running
docker-compose ps mongodb

# Check MongoDB logs
docker-compose logs mongodb

# Restart MongoDB
docker-compose restart mongodb
```

### Video Files Not Found

```bash
# Check videos volume
docker volume inspect ai_testing_v2_videos

# Verify volume mount in docker-compose.yml
# All services should mount: ./videos:/app/videos
```

## Contributing

### Before Adding Features

1. Check [ROADMAP.md](ROADMAP.md) for planned features
2. Create an issue to discuss the change
3. Follow existing code patterns
4. Write tests for new functionality
5. Update documentation

### Code Style

- **Python**: Follow PEP 8, use type hints
- **JavaScript/React**: Follow Airbnb style guide
- **Git Commits**: Use conventional commits (feat:, fix:, docs:, etc.)

### Branch Strategy

- `main`: Production-ready code
- `feature/`: New features
- `bugfix/`: Bug fixes
- `hotfix/`: Urgent production fixes

## License

[Add your license here]

## Support

For issues, questions, or feature requests:
1. Check existing documentation
2. Search closed issues
3. Create a new issue with:
   - Clear description
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Environment details

## Changelog

### v1.0.0 (Current)

**Infrastructure:**
- ✅ Health checks with dependency monitoring
- ✅ Standardized error handling
- ✅ Input validation (Git service)
- ✅ Video retention policy

**Services:**
- ✅ All 9 services operational
- ✅ End-to-end automation workflow
- ✅ Video recording functional

**Documentation:**
- ✅ ROADMAP.md (feature planning)
- ✅ API documentation (OpenAPI/Swagger)

See [ROADMAP.md](ROADMAP.md) for upcoming features in v1.1, v1.2, and beyond.
