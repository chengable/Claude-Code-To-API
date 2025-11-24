"""
命令行服务器启动模块

提供启动Claude API服务的命令行接口。
"""

import argparse
import asyncio
import sys
import signal
from pathlib import Path
from typing import Optional
import logging

from ..api.main import app
from ..utils.config import config, Config
from ..utils.port_manager import find_available_port
from ..utils.logging_config import setup_logging
from ..utils.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Claude OpenAI API Wrapper - 完全兼容OpenAI格式的Claude API封装服务"
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="服务器主机地址 (默认: 0.0.0.0)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="服务器端口 (默认: 自动选择9000-10000范围内的可用端口)"
    )

    parser.add_argument(
        "--claude-dir",
        type=str,
        default=None,
        help="Claude工作目录路径"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用自动重载 (开发模式)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="日志级别"
    )

    parser.add_argument(
        "--config-file",
        type=str,
        default=None,
        help="配置文件路径"
    )

    return parser.parse_args()


def validate_claude_setup(claude_dir: Optional[str] = None) -> None:
    """验证Claude CLI设置"""
    import subprocess
    import shutil

    claude_command_name = config.claude_command
    claude_command_path = shutil.which(claude_command_name)

    if not claude_command_path:
        raise ConfigurationError(
            f"Claude CLI command '{claude_command_name}' not found. Please ensure Claude CLI is installed and in PATH.",
            "claude_command"
        )

    # 检查Claude命令是否可用
    try:
        result = subprocess.run(
            [claude_command_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8'
        )

        if result.returncode != 0:
            raise ConfigurationError(
                f"Claude CLI command failed with exit code {result.returncode}: {result.stderr}",
                "claude_command"
            )

        logger.info(f"Claude CLI verified: {result.stdout.strip()}")

    except subprocess.TimeoutExpired:
        raise ConfigurationError(
            "Claude CLI command timed out",
            "claude_command"
        )
    except FileNotFoundError:
        # This case should now be handled by shutil.which, but kept for safety
        raise ConfigurationError(
            f"Claude CLI command '{claude_command_name}' not found. Please ensure Claude CLI is installed and in PATH.",
            "claude_command"
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred while verifying Claude CLI: {e}")
        raise

    # 验证工作目录
    if claude_dir:
        working_dir = Path(claude_dir).expanduser().resolve()
        if not working_dir.exists():
            raise ConfigurationError(
                f"Claude working directory does not exist: {working_dir}",
                "claude_working_dir"
            )
        if not working_dir.is_dir():
            raise ConfigurationError(
                f"Claude working path is not a directory: {working_dir}",
                "claude_working_dir"
            )
        logger.info(f"Claude working directory validated: {working_dir}")


async def start_server(
    host: str = "0.0.0.0",
    port: Optional[int] = None,
    claude_dir: Optional[str] = None,
    reload: bool = False,
    log_level: Optional[str] = None
) -> None:
    """启动服务器"""
    try:
        # 更新配置
        if host:
            config.host = host
        if port:
            config.port = port
        if claude_dir:
            config.claude_working_dir = claude_dir
        if log_level:
            config.log_level = log_level
            config.debug = log_level.upper() == "DEBUG"

        # 自动选择端口
        if config.port == 0:
            config.port = find_available_port(config.host)

        # 验证Claude设置
        validate_claude_setup(config.claude_working_dir)

        logger.info("Starting Claude OpenAI API Wrapper", extra={
            "host": config.host,
            "port": config.port,
            "debug": config.debug,
            "claude_working_dir": config.claude_working_dir,
            "version": "1.0.0"
        })

        # 启动服务器
        import uvicorn

        server_config = uvicorn.Config(
            app=app,
            host=config.host,
            port=config.port,
            reload=reload,
            log_level=config.log_level.lower(),
            access_log=True,
            use_colors=True
        )

        server = uvicorn.Server(server_config)

        # 设置信号处理
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            server.should_exit = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        await server.serve()

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


def main() -> None:
    """主入口函数"""
    try:
        # 设置日志
        setup_logging()

        # 解析命令行参数
        args = parse_arguments()

        # 启动服务器
        asyncio.run(start_server(
            host=args.host,
            port=args.port,
            claude_dir=args.claude_dir,
            reload=args.reload,
            log_level=args.log_level
        ))

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()