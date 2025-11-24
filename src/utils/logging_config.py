"""
日志配置模块

设置应用日志配置。
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Any, Dict

from .config import config


def setup_logging() -> None:
    """设置日志配置"""

    # 创建日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 日志配置
    log_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(name)s %(levelname)s %(module)s %(lineno)d %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": config.log_level,
                "formatter": "default",
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": config.log_level,
                "formatter": "detailed",
                "filename": log_dir / "claude-api.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": log_dir / "claude-api-error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf-8"
            }
        },
        "loggers": {
            "": {  # root logger
                "level": config.log_level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "src": {
                "level": config.log_level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False
            },
            "fastapi": {
                "level": config.log_level,
                "handlers": ["console", "file"],
                "propagate": False
            },
            "claude_api": {
                "level": config.log_level,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            }
        }
    }

    # 如果是开发环境，添加更详细的日志
    if config.debug:
        log_config["loggers"][""]["level"] = "DEBUG"
        log_config["handlers"]["console"]["formatter"] = "detailed"

    # 应用日志配置
    logging.config.dictConfig(log_config)

    # 设置第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # 记录启动信息
    logger = logging.getLogger(__name__)
    logger.info("Logging configured", extra={
        "log_level": config.log_level,
        "debug_mode": config.debug,
        "log_file": str(log_dir / "claude-api.log")
    })


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器"""
    return logging.getLogger(f"claude_api.{name}")