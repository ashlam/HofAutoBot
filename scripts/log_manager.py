from typing import Optional
import os
from datetime import datetime

class LogManager:
    _instance: Optional['LogManager'] = None
    _is_debug: bool = False
    _log_path: Optional[str] = None

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

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _write_to_file(self, message: str) -> None:
        """将消息写入日志文件，按时间倒序写入，最新的消息在最上面"""
        if not self._log_path:
            return
        
        try:
            # 如果文件不存在，直接写入
            if not os.path.exists(self._log_path):
                with open(self._log_path, 'w', encoding='utf-8') as f:
                    f.write(f"{message}\n")
                return
            
            # 如果文件存在，读取现有内容
            with open(self._log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 在文件开头写入新消息
            with open(self._log_path, 'w', encoding='utf-8') as f:
                f.write(f"{message}\n{content}")
        except Exception as e:
            print(f"\033[91m[ERROR] Failed to write log to file: {str(e)}\033[0m")

    def debug(self, message: str, is_write_in_file: bool = False) -> None:
        """输出调试信息"""
        if self._is_debug:
            log_message = f"[{self._get_timestamp()}][DEBUG] {message}"
            print(log_message)
            if is_write_in_file:
                self._write_to_file(log_message)

    def info(self, message: str, is_write_in_file: bool = False) -> None:
        """输出普通信息"""
        log_message = f"[{self._get_timestamp()}][INFO] {message}"
        print(log_message)
        if is_write_in_file:
            self._write_to_file(log_message)

    def warning(self, message: str, is_write_in_file: bool = False) -> None:
        """输出警告信息"""
        log_message = f"[{self._get_timestamp()}][WARNING] {message}"
        print(f"\033[93m{log_message}\033[0m")
        if is_write_in_file:
            self._write_to_file(log_message)

    def error(self, message: str, is_write_in_file: bool = False) -> None:
        """输出错误信息"""
        log_message = f"[{self._get_timestamp()}][ERROR] {message}"
        print(f"\033[91m{log_message}\033[0m")
        if is_write_in_file:
            self._write_to_file(log_message)

    def success(self, message: str, is_write_in_file: bool = False) -> None:
        """输出成功信息"""
        log_message = f"[{self._get_timestamp()}][SUCCESS] {message}"
        print(f"\033[92m{log_message}\033[0m")
        if is_write_in_file:
            self._write_to_file(log_message)
