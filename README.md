# Claude Code OpenAI API

> **中文** | [EN](./README_EN.md)

完全兼容OpenAI格式的Claude Code API封装服务，将Claude Code智能体框架暴露为标准API接口。

## 🎯 项目背景

Claude Code已经不仅仅是Coding Agent，而是已经发展成为一个构建智能体的灵活框架，允许用户通过配置subagent、MCP、skills、settings等组件创建定制化的AI智能体。然而，如何让外部应用轻松调用这些本地构建的智能体成为一个亟待解决的问题。

本项目解决了这一核心痛点：**将Claude Code制作的智能体封装为标准的OpenAI格式API**，使得您本地构建的智能体可以通过OpenAI兼容的API接口，对接任何支持OpenAI格式的大模型聊天工具和生态系统。

## 🚀 核心价值

- **智能体开放化**: 将本地Claude Code智能体转换为可被外部系统调用的API服务
- **生态集成**: 无缝对接Dify、n8n、CherryStudio等大模型应用生态
- **协议标准化**: 采用OpenAI标准API格式，确保最大的兼容性
- **配置灵活性**: 支持复杂的智能体配置，包括工具调用、技能组合等

## 💡 正确的使用方式

**核心工作原理**：
1. 在Claude Code的启动目录中，您需要预先构建好智能体配置文件：
   - `.claude/agents/` - 子智能体配置
   - `.mcp.json` - MCP服务器配置
   - `.claude/skills/` - 技能配置
   - `.claude/settings.json` - Claude设置

2. 使用本项目启动API服务，并指定Claude工作目录：
   ```bash
   python -m src.cli.server --claude-dir /path/to/your/claude/project
   ```

3. 您的智能体即通过OpenAI API对外提供服务！

## 功能特性

- ✅ 完全兼容OpenAI Chat Completions API格式
- ✅ 支持流式和非流式响应
- ✅ 会话管理和上下文保持
- ✅ API Key认证和频率限制（完全兼容OpenAI标准）
- ✅ 自动端口选择 (9000-10000)
- ✅ 可配置Claude工作目录（智能体项目目录）
- ✅ 完整支持Claude Code工具调用（Skills、MCP等）
- ✅ Python 3.12+ 优化
- ✅ 异步高性能架构

## 快速开始

### 1. 环境要求

- Python 3.12+
- Claude Code
- 虚拟环境

### 2. 安装

```bash
# 克隆项目
git clone <repository-url>
cd claude-openai-api

# 创建虚拟环境
# Linux/macOS:
python3.12 -m venv venv
source venv/bin/activate

# Windows:
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置

```bash
# 复制环境配置文件
# Linux/macOS:
cp .env.example .env

# Windows:
copy .env.example .env

# 编辑配置文件，设置Claude工作目录和API Key
# Linux/macOS: vim .env 或 nano .env
# Windows: notepad .env 或使用其他编辑器
```

#### API Key配置（可选）

如果需要启用API Key认证和频率限制，请在`.env`文件中配置：

```bash
# 启用API Key验证
API_KEY_ENABLED=true

# 配置API Keys（JSON格式）
API_KEYS=[
  {
    "key": "sk-your-api-key",
    "max_requests": 100,
    "period": "day",
    "description": "每日100次请求"
  },
  {
    "key": "sk-prod-key",
    "max_requests": 1000,
    "period": "month",
    "description": "每月1000次请求"
  }
]
```

或者使用单独的配置文件：
```bash
# 创建API Keys配置文件
# Linux/macOS:
cp api_keys.json.example api_keys.json

# Windows:
copy api_keys.json.example api_keys.json

# 编辑api_keys.json文件配置你的API Keys
```

### 4. 启动服务

```bash
# 使用默认配置启动
python -m src.cli.server

# 指定Claude工作目录启动
python -m src.cli.server --claude-dir /path/to/claude/project

# 指定端口启动
python -m src.cli.server --port 9500

# 开发模式启动（支持自动重载）
python -m src.cli.server --reload
```

### 5. 使用API

```bash
# 健康检查
curl http://localhost:9000/health

# 获取模型列表
curl http://localhost:9000/v1/models

# 发送聊天请求（无API Key验证）
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-4-sonnet-xxxxx(随意写)",
    "messages": [
      {
        "role": "user",
        "content": "Hello, Claude!"
      }
    ]
  }'

# 发送聊天请求（使用API Key）
curl -X POST http://localhost:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{
    "model": "claude-4-sonnet-xxxx(随意写)",
    "messages": [
      {
        "role": "user",
        "content": "Hello, Claude!"
      }
    ]
  }'

# 获取API Key使用统计
curl -H "Authorization: Bearer sk-your-api-key" \
  http://localhost:9000/v1/api-key/stats
```

## 🌐 集成场景与应用

### 支持的生态系统

通过本项目，您的Claude Code智能体可以无缝集成到以下平台：

#### 1. **可视化智能体平台**
- **Dify**: 低代码AI应用开发平台，支持复杂的工作流编排
- **n8n**: 工作流自动化平台，可构建AI驱动的自动化流程
- **LangFlow**: 可视化AI应用构建工具

#### 2. **桌面客户端**
- **CherryStudio**: 功能强大的AI聊天客户端
- **Open WebUI**: 开源的AI聊天界面
- **LobeChat**: 现代化的AI聊天应用

#### 3. **企业级集成**
- **自定义Web应用**: 通过REST API集成
- **企业聊天系统**: 内部知识库AI助手

### 典型应用场景

#### 场景1: 企业知识库智能体
```bash
# 1. 配置Claude Code智能体
# - 添加公司文档到工作目录
# - 配置文档检索技能
# - 设置专业领域prompt

# 2. 启动API服务
python -m src.cli.server --claude-dir ./enterprise-agent

# 3. 集成到企业系统
# 在Dify中配置OpenAI API端点：http://your-server:9000/v1
```

#### 场景2: 自动化工作流智能体
```bash
# 1. 配置业务流程智能体
# - 集成第三方API技能
# - 配置数据处理工具
# - 设置业务规则引擎

# 2. 启动API服务
python -m src.cli.server --claude-dir ./workflow-agent

# 3. 在n8n中构建工作流
# 将智能体作为AI节点集成到业务流程中
```

## API文档

启动服务后，访问以下地址查看API文档：

- Swagger UI: http://localhost:9000/docs
- OpenAPI JSON: http://localhost:9000/openapi.json

## 开发

### 运行测试

```bash
# 在虚拟环境中运行所有测试
pytest

# 运行特定测试
pytest tests/unit/

# 生成覆盖率报告
pytest --cov=src tests/
```

### 代码格式化

```bash
# 安装pre-commit钩子
pre-commit install

# 手动运行格式化
black src/
ruff check src/ --fix
mypy src/
```

## 配置选项

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `SERVER_HOST` | 0.0.0.0 | 服务器主机地址 |
| `SERVER_PORT` | 9000 | 服务器端口 |
| `CLAUDE_WORK_DIR` | None | **智能体项目目录**（包含.claude配置的目录） |
| `CLAUDE_TIMEOUT` | 300 | Claude命令超时时间(秒) |
| `SESSION_TIMEOUT` | 1800 | 会话超时时间(秒) |
| `MAX_CONCURRENT_SESSIONS` | 100 | 最大并发会话数 |
| `LOG_LEVEL` | INFO | 日志级别 |
| `API_KEY_ENABLED` | true | 是否启用API Key验证 |
| `API_KEYS` | [] | API Key配置（JSON格式） |
| `API_KEYS_FILE` | api_keys.json | API Keys配置文件路径 |


**重要提示**: `CLAUDE_WORK_DIR`应该指向包含上述结构的智能体项目根目录。

## API Key认证和频率限制

### 功能概述
- 支持完全兼容OpenAI标准的API Key认证
- 基于日/月周期的频率限制
- 使用统计和管理功能
- OpenAI兼容的错误响应

### 支持的认证方式
1. **Authorization Header**: `Authorization: Bearer sk-your-api-key`
2. **查询参数**: `?api_key=sk-your-api-key`
3. **请求体**: 在JSON请求中包含 `api_key` 字段

### 频率限制周期
- **day**: 从每日00:00:00 UTC重置
- **month**: 从每月1日00:00:00 UTC重置

### 管理接口
- `GET /v1/api-key/stats` - 获取当前Key使用统计
- `GET /v1/api-key/admin/stats` - 获取所有Key统计
- `POST /v1/api-key/admin/reset` - 重置Key使用记录

## 故障排除

### Claude命令未找到

确保Claude CLI已安装并在PATH中：

```bash
# Linux/macOS/Windows通用命令
claude --version
```

如果命令未找到，请：
1. 确认已正确安装Claude CLI
2. 检查PATH环境变量是否包含Claude CLI路径
3. 重启终端或重新加载环境变量

### 端口被占用

服务会自动选择可用端口，或手动指定：

```bash
python -m src.cli.server --port 9000
```

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！
