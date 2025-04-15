import json
from typing import Dict, List
from .models import Character

class CharacterManager:
    def __init__(self, config_file: str = 'saved_config.json'):
        self.config_file = config_file
        self.characters: Dict[str, Character] = {}

    def load_config(self) -> Dict:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'characters': {}, 'character_info': {}}

    def save_characters(self, characters: List[Character]):
        config = self.load_config()
        
        # 更新角色映射
        config['characters'] = {
            char.id: char.name for char in characters
        }
        
        # 更新角色详细信息
        config['character_info'] = {
            char.id: char.to_dict() for char in characters
        }
        
        # 保存配置
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def get_characters(self) -> Dict[str, str]:
        """获取角色ID到名称的映射，用于主界面显示"""
        config = self.load_config()
        return config.get('characters', {}) 