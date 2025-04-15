import json
import uuid
from typing import Dict, List
from .models import Tag

class TagManager:
    def __init__(self, config_file: str = 'saved_config.json'):
        self.config_file = config_file

    def load_config(self) -> Dict[str, Tag]:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                tags_data = data.get('tags', {})
                return {
                    tag_id: Tag.from_dict(tag_data)
                    for tag_id, tag_data in tags_data.items()
                }
        except FileNotFoundError:
            return {}

    def save_tags(self, tags: List[Tag]):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        # 更新标签数据
        config['tags'] = {
            tag.id: tag.to_dict()
            for tag in tags
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    @staticmethod
    def generate_id() -> str:
        return str(uuid.uuid4()) 