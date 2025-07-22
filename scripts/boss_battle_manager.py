import os
import json
from typing import Dict
from scripts.battle_watcher_manager import BattleWatcherManager

class BossBattleManager:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(__file__))
        self.boss_config_path = os.path.join(self.base_path, 'configs', 'boss_config.json')
        self.character_config_path = None
        self.action_config_path = None
        self.server_id = None
        
    def set_server_id(self, server_id):
        """
        设置服务器ID，用于加载对应服务器的配置文件
        
        Args:
            server_id: 服务器ID，如1表示server_01
        """
        self.server_id = server_id
        server_folder = f"server_{server_id:02d}"
        self.character_config_path = os.path.join(self.base_path, 'configs', server_folder, 'character_config.json')
        self.action_config_path = os.path.join(self.base_path, 'configs', server_folder, 'action_config_advanced.json')
        self.boss_config_path = os.path.join(self.base_path, 'configs', 'boss_config.json')
        
    def load_boss_config(self):
        """
        加载Boss配置信息
        
        Returns:
            dict: Boss配置信息
        """
        try:
            with open(self.boss_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'加载Boss配置失败: {str(e)}')
            return None
            
    def load_character_config(self):
        """
        加载角色配置信息
        
        Returns:
            dict: 角色配置信息
        """
        try:
            with open(self.character_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'加载角色配置失败: {str(e)}')
            return None
            
    def load_action_config(self):
        """
        加载动作配置信息
        
        Returns:
            dict: 动作配置信息
        """
        try:
            with open(self.action_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'加载动作配置失败: {str(e)}')
            return None
    
    def get_boss_level_limit(self, boss_id):
        """
        获取指定Boss的等级限制
        
        Args:
            boss_id: Boss的union_id
            
        Returns:
            int: Boss的等级限制，如果未找到则返回None
        """
        boss_config = self.load_boss_config()
        if not boss_config:
            return None
            
        for boss in boss_config['boss_list']:
            if boss['union_id'] == boss_id:
                return boss['level_limit']
                
        return None
    
    def get_character_level(self, character_id):
        """
        获取指定角色的等级
        
        Args:
            character_id: 角色的udid
            
        Returns:
            int: 角色的等级，如果未找到则返回0
        """
        character_config = self.load_character_config()
        if not character_config:
            return 0
            
        for character in character_config['characters']:
            if character['udid'] == character_id:
                return int(character['level'])
                
        return 0
    
    def get_action_characters(self, action_id):
        """
        获取指定动作中包含的角色ID列表
        
        Args:
            action_id: 动作ID
            
        Returns:
            list: 角色ID列表
        """
        action_config = self.load_action_config()
        if not action_config or action_id not in action_config:
            return []
            
        character_ids = []
        for action in action_config[action_id]['actions']:
            if action['trigger_type'] == 'check_box_select_character':
                # 从value中提取角色ID，格式为"char_xxxxxxxxxx"
                # 直接提取完整的ID，不需要正则表达式
                if action['value'].startswith('char_'):
                    # 提取char_后面的部分作为角色ID
                    character_ids.append(action['value'][5:])
                    
        return character_ids
    
    def is_action_level_exceed_boss_limit(self, action_id, boss_id):
        """
        判断某动作中包含的角色的等级之和是否大于boss的等级限制
        
        Args:
            action_id: 动作ID
            boss_id: Boss的union_id
            
        Returns:
            bool: 如果角色等级之和大于boss等级限制则返回True，否则返回False
            None: 如果获取配置失败则返回None
        """
        # 获取Boss等级限制
        boss_level_limit = self.get_boss_level_limit(boss_id)
        if boss_level_limit is None:
            print(f'未找到Boss(ID:{boss_id})的等级限制')
            return None
            
        # 获取动作中包含的角色ID
        character_ids = self.get_action_characters(action_id)
        if not character_ids:
            print(f'动作(ID:{action_id})中未包含角色')
            return False
            
        # 计算角色等级之和
        total_level = 0
        for char_id in character_ids:
            char_level = self.get_character_level(char_id)
            total_level += char_level
            
        print(f'动作(ID:{action_id})中角色等级之和为{total_level}，Boss(ID:{boss_id})等级限制为{boss_level_limit}')
        
        # 判断是否超过限制
        return total_level > boss_level_limit
        
    def get_next_vip_boss(self, vip_boss_dict: Dict, union_id, battle_watcher_manager: BattleWatcherManager):
        """
        获取下一个VIP Boss的刷新时间信息
        
        Args:
            vip_boss_dict: VIP Boss的配置字典
            union_id: Boss的union_id
            battle_watcher_manager: BattleWatcherManager实例
            
        Returns:
            dict: 包含下次战斗时间信息的字典，如果获取失败则返回None
        """
        # 从vip_boss_dict中获取服务器URL
        server_url = vip_boss_dict.get('server_url')
        if not server_url:
            # 如果vip_boss_dict中没有server_url，则需要从外部传入
            print(f'警告：vip_boss_dict中未包含server_url，请确保在调用时提供正确的URL')
            return None
            
        boss_log_url = f"{server_url}?ulog"
        kill_cooldown = vip_boss_dict.get('kill_cooldown_seconds', 14400)  # 默认为4小时
        next_battle_info = battle_watcher_manager.get_boss_next_battle_real_time(union_id, kill_cooldown, boss_log_url)
        return next_battle_info