import re
import requests
import json
import os
from datetime import datetime, timedelta

class BattleWatcherManager:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), '..', 'configs', 'boss_config.json')
        self.cooldown_total_seconds = None
        self.alived_boss_ids = []

    def get_boss_info(self, union_id):
        """从boss_config.json中获取指定union_id的boss信息"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                boss_config = json.load(f)
                
            for boss in boss_config['boss_list']:
                if boss['union_id'] == union_id:
                    return boss
            return None
        except Exception as e:
            print(f'获取boss信息失败: {str(e)}')
            return None


    def process_timestamp(self, timestamp_str, minutes_to_add=240):
        """处理16位时间戳，转换为标准时间格式并计算未来时间"""
        try:
            # 取前10位转换为整数
            unix_timestamp = int(timestamp_str[:10])
            
            # 转换为datetime对象
            original_time = datetime.fromtimestamp(unix_timestamp)
            # 计算未来时间
            future_time = original_time + timedelta(minutes=minutes_to_add)
            
            # 格式化输出
            return {
                'original': original_time.strftime('%Y-%m-%d %H:%M:%S'),
                'future': future_time.strftime('%Y-%m-%d %H:%M:%S'),
                'original_unixtime': unix_timestamp,
                'future_unixtime': int(future_time.timestamp())
            }
        except Exception as e:
            print(f'处理时间戳失败: {str(e)}')
            return None

    def get_boss_next_battle_real_time(self, union_id, minutes_to_add=240):
        """获取指定boss的下次战斗时间"""
        def get_lastest_timestamp_from_boss_battle_log(union_id):
            """获取指定boss的最近一次战斗记录时间戳"""
            url = 'http://pim0110.com/hall?ulog'
            boss_info = self.get_boss_info(union_id)
            if not boss_info:
                return None
            boss_name = boss_info["name"]
            try:
                response = requests.get(url)
                response.encoding = 'utf-8'
                content = response.text
                
                timestamp_pattern = r'ulog=(\d+)'
                first_matched_boss_text = ""
                
                for line in content.split('<br />'):
                    if boss_name in line:
                        first_matched_boss_text = line
                        break
                
                match = re.search(timestamp_pattern, first_matched_boss_text, re.DOTALL)
                if match:
                    return match.group(1)
                return None
            except Exception as e:
                print(f'获取战斗日志失败: {str(e)}')
                return None
        # 获取boss信息
        latest_timestamp_str = get_lastest_timestamp_from_boss_battle_log(union_id)
        if latest_timestamp_str:
            time_info = self.process_timestamp(latest_timestamp_str, minutes_to_add)
            if time_info:
                return time_info
        return None

    def get_player_challenge_boss_cooldown(self):
        """获取玩家挑战boss的冷却时间"""
        if self.cooldown_total_seconds is None:
            return 0
        return self.cooldown_total_seconds
    
    def get_player_stamina(self):
        """获取玩家当前体力值"""
        return self.stamina

    def get_all_alive_boss(self):
        """获取所有存活的boss"""
        return self.alived_boss_ids

    def _update_all_alive_boss(self, content_text):
        """获取所有存活的boss"""
        try:
            # 匹配所有存活的boss
            import re

            # 修正后的正则表达式（注意结尾的 ')')
            boss_regex_pattern = r"RA_UseBack\s*\(\s*'index2\.php\?union=(\d+)'\s*\)"

            # 匹配所有 boss ID
            boss_matches = re.findall(boss_regex_pattern, content_text)

            if boss_matches:
                print('所有存活的boss:', boss_matches)
                int_list = []
                for x in boss_matches:
                    try:
                        int_list.append(int(x))
                    except ValueError:
                        print(f"警告：'{x}' 无法转换为整数，已跳过。")
                self.alived_boss_ids = int_list  # 取消注释后可实际赋值
            else:
                print('未找到存活的boss')
        except Exception as e:
            print(f'获取所有存活的boss失败: {str(e)}')

    def _update_player_challenge_boss_cooldown(self, content_text):
        """获取玩家挑战boss的冷却时间"""
        try:
            content = content_text
            # 匹配冷却时间
            cooldown_pattern = r'離下次戰鬥還需要 : <span class="bold">(\d+:\d+)</span>'
            cooldown_match = re.search(cooldown_pattern, content)
            if cooldown_match:
                cooldown = cooldown_match.group(1)  # 提取匹配的时间
                # 将时间转换为秒数
                minutes, seconds = map(int, cooldown.split(':'))
                self.cooldown_total_seconds = minutes * 60 + seconds
                print(f'剩余冷却时间:{cooldown}（剩余{self.cooldown_total_seconds}秒）')
            else:
                print('未找到冷却时间信息，说明可以打boss')
                self.cooldown_total_seconds = 0
        except Exception as e:
            print(f'获取冷却时间失败: {str(e)}')

    def _update_player_stamina(self, content_text):
        """获取玩家当前体力值"""
        try:
            content = content_text
            # 匹配体力值
            stamina_pattern = r'<span id="mtime">(\d+)</span>'
            stamina_match = re.search(stamina_pattern, content)
            if stamina_match:
                self.stamina = int(stamina_match.group(1))  # 提取匹配的体力值并转换为整数
                print(f'当前体力值: {self.stamina}/4000')
            else:
                print('未找到体力值信息，请检查登录状态和地址是否正确')
                return None
        except Exception as e:
            print(f'获取体力值失败，请检查登录状态和地址是否正确: {str(e)}')
            return None

    def update_all_from_hunt_page(self, content_text):
        """更新hunt页面信息"""
        self._update_all_alive_boss(content_text)
        self._update_player_stamina(content_text)
        self._update_player_challenge_boss_cooldown(content_text)
