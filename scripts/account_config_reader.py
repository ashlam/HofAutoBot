# scripts/account_config_reader.py
import os
import json

def get_account_config(server_id):
    config_path = os.path.join(f'{server_id}', 'account_config.json')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到 {server_id} 的账号配置文件: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config.get("user_name"), config.get("password")