from typing import Optional
import os
from datetime import datetime

class LogManager:
    _instance: Optional['LogManager'] = None
    _is_debug: bool = False
    _log_path: Optional[str] = None
    _max_file_size: int = 5 * 1024 * 1024  # 单个日志文件大小上限，超过后轮转
    _max_backup_files: int = 3              # 保留的历史日志文件个数

    def __new__(cls) -> 'LogManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'LogManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_debug(cls, is_debug: bool) -> None:
        cls._is_debug = is_debug

    @classmethod
    def set_log_path(cls, log_path: str) -> None:
        """设置日志文件路径"""
        cls._log_path = log_path
        # 确保日志文件所在目录存在
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    @classmethod
    def set_max_file_size(cls, max_file_size: int) -> None:
        """设置单个日志文件大小上限（字节），超过后轮转"""
        cls._max_file_size = max_file_size

    def _get_timestamp(self) -> str:
        """获取当前时间戳，精确到微秒"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

    def _rotate_if_needed(self) -> None:
        """日志文件超过大小上限时轮转：log.txt -> log.txt.1 -> log.txt.2 ..."""
        if not self._log_path or not os.path.exists(self._log_path):
            return
        try:
            if os.path.getsize(self._log_path) < self._max_file_size:
                return
            # 删除最旧的备份
            oldest = f"{self._log_path}.{self._max_backup_files}"
            if os.path.exists(oldest):
                os.remove(oldest)
            # 依次后移
            for i in range(self._max_backup_files - 1, 0, -1):
                src = f"{self._log_path}.{i}"
                if os.path.exists(src):
                    os.replace(src, f"{self._log_path}.{i + 1}")
            # 当前文件变为 .1，新建空文件
            os.replace(self._log_path, f"{self._log_path}.1")
        except Exception as e:
            print(f"\033[91m[ERROR] Failed to rotate log file: {str(e)}\033[0m")

    def _write_to_file(self, message: str) -> None:
        """将消息追加写入日志文件（按时间正序，最新的在最后）"""
        if not self._log_path:
            return

        try:
            self._rotate_if_needed()
            with open(self._log_path, 'a', encoding='utf-8') as f:
                f.write(f"{message}\n")
        except Exception as e:
            print(f"\033[91m[ERROR] Failed to write log to file: {str(e)}\033[0m")

    def _log(self, level: str, message: str, color: str = None) -> None:
        """统一的日志输出：控制台 + 日志文件"""
        log_message = f"[{self._get_timestamp()}][{level}] {message}"
        if color:
            print(f"{color}{log_message}\033[0m")
        else:
            print(log_message)
        self._write_to_file(log_message)

    def debug(self, message: str) -> None:
        """输出调试信息"""
        if self._is_debug:
            self._log('DEBUG', message)

    def info(self, message: str) -> None:
        """输出普通信息"""
        self._log('INFO', message)

    def warning(self, message: str) -> None:
        """输出警告信息"""
        self._log('WARNING', message, '\033[93m')

    def error(self, message: str) -> None:
        """输出错误信息"""
        self._log('ERROR', message, '\033[91m')

    def success(self, message: str) -> None:
        """输出成功信息"""
        self._log('SUCCESS', message, '\033[92m')
