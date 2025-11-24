"""
配置管理模块

处理应用配置、环境变量和设置。
"""

import os
import json
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from ..models.api_key import APIKeyConfig, RateLimitPeriod

# 加载环境变量
load_dotenv()


class Config(BaseSettings):
    """应用配置类"""

    # 服务器配置
    host: str = Field(default="0.0.0.0", env="SERVER_HOST")
    port: int = Field(default=9000, env="SERVER_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Claude配置
    claude_working_dir: Optional[str] = Field(default=None, env="CLAUDE_WORK_DIR")
    claude_timeout: int = Field(default=300, env="CLAUDE_TIMEOUT")  # 5分钟
    claude_command: str = Field(default="claude", env="CLAUDE_COMMAND")

    # 会话配置
    session_timeout: int = Field(default=1800, env="SESSION_TIMEOUT")  # 30分钟
    max_concurrent_sessions: int = Field(default=100, env="MAX_CONCURRENT_SESSIONS")
    session_cleanup_interval: int = Field(default=300, env="SESSION_CLEANUP_INTERVAL")  # 5分钟

    # 端口配置
    port_range_start: int = Field(default=9000, env="PORT_RANGE_START")
    port_range_end: int = Field(default=10000, env="PORT_RANGE_END")

    # 性能配置
    max_request_size: int = Field(default=10 * 1024 * 1024, env="MAX_REQUEST_SIZE")  # 10MB
    request_timeout: int = Field(default=600, env="REQUEST_TIMEOUT")  # 10分钟

    # API Key配置
    api_keys: List[APIKeyConfig] = Field(default_factory=list, description="API Key配置列表")
    api_key_enabled: bool = Field(default=True, env="API_KEY_ENABLED", description="是否启用API Key验证")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "allow"  # 允许额外的字段
    }

    @validator('api_keys', pre=True, always=True)
    def parse_api_keys_from_env(cls, v):
        """从环境变量或文件解析API Key配置"""
        if v:
            return v

        # 尝试从API_KEYS环境变量获取
        api_keys_json = os.getenv("API_KEYS")
        if api_keys_json:
            try:
                keys_data = json.loads(api_keys_json)
                api_keys = [APIKeyConfig(**key_data) for key_data in keys_data]
                print(f"成功从环境变量加载 {len(api_keys)} 个API Key配置")
                return api_keys
            except (json.JSONDecodeError, Exception) as e:
                print(f"警告: API_KEYS环境变量解析失败: {e}")

        # 尝试从API_KEYS_FILE文件获取
        api_keys_file = os.getenv("API_KEYS_FILE", "api_keys.json")
        try:
            with open(api_keys_file, 'r', encoding='utf-8') as f:
                keys_data = json.load(f)
                api_keys = [APIKeyConfig(**key_data) for key_data in keys_data]
                print(f"成功从文件 {api_keys_file} 加载 {len(api_keys)} 个API Key配置")
                return api_keys
        except FileNotFoundError:
            print(f"API Keys配置文件未找到: {api_keys_file}")
        except (json.JSONDecodeError, Exception) as e:
            print(f"警告: API Keys配置文件解析失败: {e}")

        return []

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.debug

    @property
    def claude_working_path(self) -> Optional[Path]:
        """获取Claude工作目录路径"""
        if self.claude_working_dir:
            return Path(self.claude_working_dir).expanduser().resolve()
        return None

    def validate_claude_setup(self) -> bool:
        """验证Claude CLI设置"""
        try:
            import subprocess
            result = subprocess.run(
                [self.claude_command, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_api_key_config(self, api_key: str) -> Optional[APIKeyConfig]:
        """根据API Key获取配置"""
        for key_config in self.api_keys:
            if key_config.key == api_key:
                return key_config
        return None

    def is_valid_api_key(self, api_key: str) -> bool:
        """检查API Key是否有效"""
        if not self.api_key_enabled:
            return True  # 如果禁用了API Key验证，则总是有效
        return self.get_api_key_config(api_key) is not None


# 创建全局配置实例
config = Config()

# 为了向后兼容
Config = config