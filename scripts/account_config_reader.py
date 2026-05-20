# scripts/account_config_reader.py
import os
import json


def _get_account_config_paths(server_id):
    """按优先级返回账号配置文件的搜索路径列表"""
    paths = []

    # 1. 外部配置目录（~/.config/hofautobot2/server_XX/account_config.json）— 不受 git 影响
    home = os.path.expanduser("~")
    external_dir = os.path.join(home, ".config", "hofautobot2", server_id)
    paths.append(os.path.join(external_dir, "account_config.json"))

    # 2. 项目内配置目录（向后兼容）
    paths.append(os.path.join(f"{server_id}", "account_config.json"))

    return paths


def get_account_config(server_id):
    paths = _get_account_config_paths(server_id)
    for config_path in paths:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("user_name"), config.get("password")

    searched = "\n".join(f"  - {p}" for p in paths)
    raise FileNotFoundError(
        f"找不到 {server_id} 的账号配置文件。搜索路径：\n{searched}"
    )