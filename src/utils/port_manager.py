"""
端口管理工具模块

处理端口发现和管理功能。
"""

import socket
import random
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PortManager:
    """端口管理器"""

    def __init__(self, start_port: int = 9000, end_port: int = 10000):
        self.start_port = start_port
        self.end_port = end_port
        self._used_ports: set[int] = set()

    def is_port_available(self, port: int, host: str = "localhost") -> bool:
        """检查端口是否可用"""
        if port in self._used_ports:
            return False

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                return result != 0  # 0 表示连接成功，端口被占用
        except Exception as e:
            logger.warning(f"Error checking port {port}: {e}")
            return False

    def find_available_port(self, host: str = "localhost") -> int:
        """在指定范围内查找可用端口"""
        # 优先尝试顺序扫描
        for port in range(self.start_port, self.end_port + 1):
            if self.is_port_available(port, host):
                self._used_ports.add(port)
                logger.info(f"Found available port: {port}")
                return port

        raise RuntimeError(
            f"No available ports found in range {self.start_port}-{self.end_port}"
        )

    def find_random_available_port(self, host: str = "localhost") -> int:
        """在指定范围内随机查找可用端口"""
        max_attempts = 100
        attempts = 0

        while attempts < max_attempts:
            port = random.randint(self.start_port, self.end_port)
            if self.is_port_available(port, host):
                self._used_ports.add(port)
                logger.info(f"Found random available port: {port}")
                return port
            attempts += 1

        raise RuntimeError(
            f"Failed to find available port after {max_attempts} attempts"
        )

    def reserve_port(self, port: int) -> bool:
        """预留端口"""
        if self.is_port_available(port):
            self._used_ports.add(port)
            return True
        return False

    def release_port(self, port: int) -> None:
        """释放端口"""
        self._used_ports.discard(port)
        logger.debug(f"Released port: {port}")

    def get_used_ports(self) -> set[int]:
        """获取已使用的端口列表"""
        return self._used_ports.copy()

    def clear_used_ports(self) -> None:
        """清空已使用端口列表"""
        self._used_ports.clear()
        logger.info("Cleared all used ports")

    @staticmethod
    def validate_port_range(start_port: int, end_port: int) -> bool:
        """验证端口范围是否有效"""
        return (
            isinstance(start_port, int) and
            isinstance(end_port, int) and
            1 <= start_port <= 65535 and
            1 <= end_port <= 65535 and
            start_port < end_port
        )


# 全局端口管理器实例
_port_manager: Optional[PortManager] = None


def get_port_manager() -> PortManager:
    """获取全局端口管理器实例"""
    global _port_manager
    if _port_manager is None:
        from .config import config
        _port_manager = PortManager(
            start_port=config.port_range_start,
            end_port=config.port_range_end
        )
    return _port_manager


def find_available_port(host: str = "localhost") -> int:
    """便捷函数：查找可用端口"""
    return get_port_manager().find_available_port(host)


def reserve_port(port: int) -> bool:
    """便捷函数：预留端口"""
    return get_port_manager().reserve_port(port)


def release_port(port: int) -> None:
    """便捷函数：释放端口"""
    get_port_manager().release_port(port)