import json
import re
from typing import Dict, Optional
from .models import CookieConfig

class CookieManager:
    def __init__(self, config_file: str = 'saved_config.json'):
        self.config_file = config_file

    def load_config(self) -> CookieConfig:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return CookieConfig.from_dict(data.get('cookie', {}))
        except FileNotFoundError:
            return CookieConfig()

    def save_config(self, cookie_config: CookieConfig):
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}

        config['cookie'] = cookie_config.to_dict()

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    @staticmethod
    def parse_curl(curl_data: str) -> Optional[CookieConfig]:
        cookie_match = re.search(r'-H "Cookie: ([^"]+)"', curl_data)
        if not cookie_match:
            return None

        cookies = {}
        cookie_str = cookie_match.group(1)
        for cookie in cookie_str.split('; '):
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies[name] = value

        return CookieConfig.from_dict(cookies) 