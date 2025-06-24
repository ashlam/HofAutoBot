import json
import os

class ServerConfigManager:
    SERVER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../configs', 'server_address.json')
    def __init__(self):
        # 初始化属性
        self.current_server_id = None
        self.current_server_data = None
        self.all_action_config_by_server = None
        self.auto_bot_config = None
        self.server_config_manager = None
        # 加载服务器配置
        self._load_all_server_info_config()

    def _load_action_config_by_action_id(self, action_id):
        """加载指定ID的动作配置"""
        if not hasattr(self, 'all_action_config_by_server') or self.all_action_config_by_server is None:
            return None
        return self.all_action_config_by_server.get(str(action_id))

    def _load_server_action_config(self, server_data):
        """加载当前Server的动作配置"""
        try:
            with open(f'{server_data.get("config_path")}/action_config_advanced.json', 'r', encoding='utf-8') as f:
                action_config = json.load(f)
                return action_config
        except Exception as e:
            print(f"加载动作配置出错: {str(e)}")
            return None

    def _load_action_group_config(self, server_data):
        """加载当前Server的动作组配置"""
        try:
            with open(f'{server_data.get("config_path")}/auto_action_groups.json', 'r', encoding='utf-8') as f:
                action_group_config = json.load(f)
                return action_group_config
        except Exception as e:
            print(f"加载动作组配置出错: {str(e)}")
            return None
    def _load_auto_bot_config(self, server_data):
        """加载当前Server的自动机器人配置"""
        try:
            with open(f'{server_data.get("config_path")}/auto_bot_loop_config.json', 'r', encoding='utf-8') as f:
                auto_bot_config = json.load(f)
                return auto_bot_config
        except Exception as e:
            print(f"加载自动机器人配置出错: {str(e)}")
            return None

    def _load_all_server_info_config(self):
        """获取服务器配置"""
        try:
            with open(self.SERVER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                all_server_config = json.load(f)
                return all_server_config
        except Exception as e:
            print(f"加载服务器配置出错: {str(e)}")
            return None

    def _get_server_info_config_by_server_id(self, server_id):
        """根据服务器ID加载配置"""
        server_config = self._load_all_server_info_config()
        if server_config is None:
            return None

        server_list = server_config.get("server_address", []) # 如果 "server_address" 不存在，默认为空列表
        # 使用 next 从生成器中获取第一个匹配项，如果找不到则返回 None (由 next 的第二个参数指定)
        found_server = next((server for server in server_list if server.get("id") == server_id), None)

        if found_server:
            print(f"找到 id 为 {server_id} 的数据 (使用 next):")
            print(found_server)
            return found_server
        else:
            print(f"未找到 id 为 {server_id} 的数据 (使用 next)。")

    def set_current_server_id(self, server_id):
        """设置当前服务器ID"""
        self.current_server_id = server_id
        self.current_server_data = self._get_server_info_config_by_server_id(server_id)
        self.all_action_config_by_server = self._load_server_action_config(self.current_server_data)
        self.auto_bot_config = self._load_auto_bot_config(self.current_server_data)


    def get_all_server_info_config(self):
        """获取所有服务器配置"""
        return self._load_all_server_info_config()