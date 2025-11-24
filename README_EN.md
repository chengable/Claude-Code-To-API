# Claude Code OpenAI API

> **English** | [中文](./README.md)

A fully OpenAI-compatible Claude Code API wrapper service that exposes the Claude Code agent framework as a standard API interface.

## 🎯 Project Background

Claude Code has evolved beyond just a coding agent into a flexible framework for building intelligent agents. It allows users to create customized AI agents by configuring subagents, MCP (Model Context Protocol), skills, settings, and other components. However, enabling external applications to easily call these locally built agents has become a pressing challenge.

This project addresses this core pain point: **wrapping Claude Code-built agents as standard OpenAI-format APIs**, allowing your locally built agents to interface with any OpenAI-compatible large model chat tools and ecosystems through OpenAI-compatible API endpoints.

## 🚀 Core Value

- **Agent Externalization**: Convert local Claude Code agents into externally callable API services
- **Ecosystem Integration**: Seamlessly integrate with Dify, n8n, CherryStudio, and other large model application ecosystems
- **Protocol Standardization**: Adopt OpenAI standard API format to ensure maximum compatibility
- **Configuration Flexibility**: Support complex agent configurations including tool calling, skill combinations, etc.

## 💡 Correct Usage

**Core Working Principle**:
1. In the Claude Code startup directory, you need to pre-build agent configuration files:
   - `.claude/agents/` - Sub-agent configuration
   - `.mcp.json` - MCP server configuration
   - `.claude/skills/` - Skills configuration
   - `.claude/settings.json` - Claude settings

2. Use this project to start the API service and specify the Claude working directory:
   ```bash
   python -m src.cli.server --claude-dir /path/to/your/claude/project
   ```

3. Your agent will then provide services through the OpenAI API!

## Features

- ✅ Fully compatible with OpenAI Chat Completions API format
- ✅ Support for streaming and non-streaming responses
- ✅ Session management and context preservation
- ✅ API Key authentication and rate limiting (fully OpenAI standard compatible)
- ✅ Automatic port selection (9000-10000)
- ✅ Configurable Claude working directory (agent project directory)
- ✅ Complete support for Claude Code tool calling (Skills, MCP, etc.)
- ✅ Python 3.12+ optimized
- ✅ High-performance asynchronous architecture

## Quick Start

### 1. Requirements

- Python 3.12+
- Claude Code
- Virtual environment

### 2. Installation

```bash
# Clone the project
git clone <repository-url>
cd claude-openai-api

# Create virtual environment
# Linux/macOS:
python3.12 -m venv venv
source venv/bin/activate

# Windows:
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy environment configuration file
# Linux/macOS:
cp .env.example .env

# Windows:
copy .env.example .env

# Edit configuration file to set Claude working directory and API Key
# Linux/macOS: vim .env or nano .env
# Windows: notepad .env or use other editors
```

#### API Key Configuration (Optional)

If you need to enable API Key authentication and rate limiting, configure it in the `.env` file:

```bash
# Enable API Key verification
API_KEY_ENABLED=true

# Configure API Keys (JSON format)
API_KEYS=[
  {
    "key": "sk-your-api-key",
    "max_requests": 100,
    "period": "day",
    "description": "100 requests per day"
  },
  {
    "key": "sk-prod-key",
    "max_requests": 1000,
    "period": "month",
    "description": "1000 requests per month"
  }
]
```

Or use a separate configuration file:
```bash
# Create API Keys configuration file
# Linux/macOS:
cp api_keys.json.example api_keys.json

# Windows:
copy api_keys.json.example api_keys.json

# Edit api_keys.json file to configure your API Keys
```

### 4. Start Service

```bash
# Start with default configuration
python -m src.cli.server

# Start with specified Claude working directory
python -m src.cli.server --claude-dir /path/to/claude/project

# Start with specified port
python -m src.cli.server --port 9500

# Start in development mode (with auto-reload)
python -m src.cli.server --reload
```

### 5. Using the API

```bash
# Health check
curl http://localhost:9000/health

# Get model list
curl http://localhost:9000/v1/models

# Send chat request (without API Key verification)
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-4-sonnet-xxxxx(custom)",
    "messages": [
      {
        "role": "user",
        "content": "Hello, Claude!"
      }
    ]
  }'

# Send chat request (using API Key)
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{
    "model": "claude-4-sonnet-xxxx(custom)",
    "messages": [
      {
        "role": "user",
        "content": "Hello, Claude!"
      }
    ]
  }'

# Get API Key usage statistics
curl -H "Authorization: Bearer sk-your-api-key" \
  http://localhost:9000/v1/api-key/stats
```

## 🌐 Integration Scenarios and Applications

### Supported Ecosystems

Through this project, your Claude Code agents can seamlessly integrate with the following platforms:

#### 1. **Visual Agent Platforms**
- **Dify**: Low-code AI application development platform supporting complex workflow orchestration
- **n8n**: Workflow automation platform for building AI-driven automation processes
- **LangFlow**: Visual AI application building tool

#### 2. **Desktop Clients**
- **CherryStudio**: Powerful AI chat client
- **Open WebUI**: Open-source AI chat interface
- **LobeChat**: Modern AI chat application

#### 3. **Enterprise Integration**
- **Custom Web Applications**: Integration through REST API
- **Enterprise Chat Systems**: Internal knowledge base AI assistant
- **IoT Device Control**: Smart home device AI control interface

### Typical Application Scenarios

#### Scenario 1: Enterprise Knowledge Base Agent
```bash
# 1. Configure Claude Code agent
# - Add company documents to working directory
# - Configure document retrieval skills
# - Set professional domain prompts

# 2. Start API service
python -m src.cli.server --claude-dir ./enterprise-agent

# 3. Integrate into enterprise systems
# Configure OpenAI API endpoint in Dify: http://your-server:9000/v1
```

#### Scenario 2: Automation Workflow Agent
```bash
# 1. Configure business process agent
# - Integrate third-party API skills
# - Configure data processing tools
# - Set business rule engine

# 2. Start API service
python -m src.cli.server --claude-dir ./workflow-agent

# 3. Build workflows in n8n
# Integrate the agent as an AI node into business processes
```

## API Documentation

After starting the service, visit the following addresses to view API documentation:

- Swagger UI: http://localhost:9000/docs
- OpenAPI JSON: http://localhost:9000/openapi.json

## Development

### Running Tests

```bash
# Run all tests in virtual environment
pytest

# Run specific tests
pytest tests/unit/

# Generate coverage report
pytest --cov=src tests/
```

### Code Formatting

```bash
# Install pre-commit hooks
pre-commit install

# Manual formatting
black src/
ruff check src/ --fix
mypy src/
```

## Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SERVER_HOST` | 0.0.0.0 | Server host address |
| `SERVER_PORT` | 9000 | Server port |
| `CLAUDE_WORK_DIR` | None | **Agent project directory** (directory containing .claude configuration) |
| `CLAUDE_TIMEOUT` | 300 | Claude command timeout (seconds) |
| `SESSION_TIMEOUT` | 1800 | Session timeout (seconds) |
| `MAX_CONCURRENT_SESSIONS` | 100 | Maximum concurrent sessions |
| `LOG_LEVEL` | INFO | Log level |
| `API_KEY_ENABLED` | true | Whether to enable API Key verification |
| `API_KEYS` | [] | API Key configuration (JSON format) |
| `API_KEYS_FILE` | api_keys.json | API Keys configuration file path |

### Agent Project Directory Structure

Recommended Claude Code agent project directory structure:

```
your-agent-project/
├── .claude/
│   ├── settings.json          # Claude settings
│   ├── mcp_servers.json       # MCP server configuration
│   └── skills/               # Skills directory
│       ├── my-skill.json
│       └── another-skill/
├── .claude/agents/           # Sub-agent configuration
│   ├── agent1.json
│   └── agent2.json
├── .mcp.json                 # MCP configuration
├── docs/                     # Agent knowledge base
├── tools/                    # Custom tools
└── README.md
```

**Important Note**: `CLAUDE_WORK_DIR` should point to the agent project root directory containing the above structure.

## 🎯 Complete Example: Building and Deploying an Agent from Scratch

### Step 1: Create Claude Code Agent

```bash
# 1. Create agent project directory
mkdir my-ai-assistant
cd my-ai-assistant

# 2. Initialize Claude project (automatically creates .claude directory)
claude

# 3. Configure agent skills
mkdir -p .claude/skills
echo '{"name": "calculator", "description": "Math calculation tool"}' > .claude/skills/calculator.json

# 4. Add some documents as knowledge base
echo "# My Knowledge Base\nHere is some important information..." > docs/knowledge.md
```

### Step 2: Deploy API Service

```bash
# 1. Clone this project
git clone <repository-url>
cd claude-openai-api

# 2. Install dependencies
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt

# 3. Configure environment variables
copy .env.example .env
# Edit .env, set CLAUDE_WORK_DIR=D:\path\to\my-ai-assistant

# 4. Start API service
python -m src.cli.server --claude-dir "D:\path\to\my-ai-assistant"
```

### Step 3: Integrate with Third-party Platforms

**Configure in CherryStudio:**
1. Open Settings → Model Settings
2. Add custom API endpoint: `http://localhost:9000`
3. API Key: `sk-your-key` (if verification is enabled)
4. Model name: `claude-4-sonnet-custom`

**Configure in Dify:**
1. Create new application → Select LLM model
2. Model provider: OpenAI Compatible
3. API Base: `http://localhost:9000/v1`
4. API Key: `sk-your-key`
5. Model name: `claude-4-sonnet-custom`

Now your agent can be used in these platforms!

## API Key Authentication and Rate Limiting

### Features
- Fully OpenAI standard compatible API Key authentication
- Day/month cycle based rate limiting
- Usage statistics and management features
- OpenAI compatible error responses

### Supported Authentication Methods
1. **Authorization Header**: `Authorization: Bearer sk-your-api-key`
2. **Query Parameters**: `?api_key=sk-your-api-key`
3. **Request Body**: Include `api_key` field in JSON request

### Rate Limiting Cycles
- **day**: Resets daily at 00:00:00 UTC
- **month**: Resets on the 1st of each month at 00:00:00 UTC

### Management Endpoints
- `GET /v1/api-key/stats` - Get current key usage statistics
- `GET /v1/api-key/admin/stats` - Get all key statistics
- `POST /v1/api-key/admin/reset` - Reset key usage records

## Cross-platform Deployment

This project supports deployment on both Linux and Windows platforms:

### Linux/macOS Deployment
```bash
# Environment setup
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env file, set correct path format

# Start service
python -m src.cli.server
```

### Windows Deployment
```bash
# Environment setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure environment variables
copy .env.example .env
# Edit .env file, set Windows format paths (use backslashes or double backslashes)

# Start service
python -m src.cli.server
```

## Troubleshooting

### Claude Command Not Found

Ensure Claude CLI is installed and in PATH:

```bash
# Linux/macOS/Windows universal command
claude --version
```

If the command is not found, please:
1. Confirm Claude CLI is correctly installed
2. Check if PATH environment variable includes Claude CLI path
3. Restart terminal or reload environment variables

### Port Already in Use

The service will automatically select available ports, or manually specify:

```bash
python -m src.cli.server --port 9000
```

### Permission Issues

**Linux/macOS:**
Ensure Claude CLI has execution permissions:

```bash
chmod +x /path/to/claude
```

**Windows:**
Usually no special permission settings are required. If you encounter permission issues, please:
1. Run command prompt as administrator
2. Check execution permissions of Claude CLI installation directory
3. Ensure antivirus software is not blocking Claude CLI

## License

MIT License

## Contributing

Issues and Pull Requests are welcome!
