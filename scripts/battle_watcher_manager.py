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


    def process_timestamp(self, timestamp_str, seconds_to_add):
        """处理16位时间戳，转换为标准时间格式并计算未来时间"""
        try:
            # 将16位时间戳转换为浮点数（保留毫秒精度）
            unix_timestamp = int(timestamp_str) / 1000000
            
            # 转换为datetime对象
            original_time = datetime.fromtimestamp(unix_timestamp)
            # 计算未来时间
            future_time = original_time + timedelta(seconds=seconds_to_add)
            
            # 格式化输出（时间戳保持16位精度）
            return {
                'original': original_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'future': future_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'original_unixtime': int(unix_timestamp * 1000000),
                'future_unixtime': int(future_time.timestamp() * 1000000)
            }
        except Exception as e:
            print(f'处理时间戳失败: {str(e)}')
            return None

    def get_boss_next_battle_real_time(self, union_id, seconds_to_add=240, url = 'http://pim0110.com/hall?ulog'):
        """获取指定boss的下次战斗时间"""
        def get_lastest_timestamp_from_boss_battle_log(union_id):
            """获取指定boss的最近一次战斗记录时间戳"""
            boss_info = self.get_boss_info(union_id)
            print(f'获取{boss_info["name"]}的最近一次战斗记录时间戳')
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
                    matched_text =  match.group(1)
                    print("matched_text = "+ matched_text)
                    return matched_text
                else:
                    print(f'未找到{boss_name}的最近一次战斗记录, url = {url},\n\n timestamp_pattern = {timestamp_pattern} \n\n res.content = {content}')
                return None
            except Exception as e:
                print(f'获取战斗日志失败: {str(e)}')
                return None
        # 获取boss信息
        latest_timestamp_str = get_lastest_timestamp_from_boss_battle_log(union_id)
        if latest_timestamp_str:
            time_info = self.process_timestamp(latest_timestamp_str, seconds_to_add)
            if time_info:
                print(f'>>>下次战斗时间: {time_info}')
                return time_info
        print('获取log -> 下次战斗时间失败, latest_timestamp_str = ' + latest_timestamp_str)
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

    def is_user_pvp_first_place(self, content_text):
        """判断当前用户是否为PVP第一名
        Args:
            content_text: PVP准备页面的HTML内容
        Returns:
            bool: 如果当前用户是第一名返回True，否则返回False
        """
        try:
            # 从页面中提取当前用户名（在menu2区域内，通过資金和時間标记定位）
            """
            <div id="menu2">
			<div style="width:100%">
			<div style="width:30%;float:left">陸斯坎軍團老兵</div>
            """
            user_pattern = r'<div id="menu2">\s*<div style="width:100%">\s*<div style="width:30%;float:left">(.*?)</div>\s*<div style="width:60%;float:right">\s*<div style="width:40%;float:left"><span class="bold">資金</span>.*?<span class="bold">時間</span>'
            user_match = re.search(user_pattern, content_text, re.DOTALL)
            if not user_match:
                print("未能匹配到当前用户名")
                # 尝试使用更宽松的匹配模式
                backup_user_pattern = r'<div id="menu2">\s*<div[^>]*>\s*<div[^>]*>(.*?)</div>'
                backup_user_match = re.search(backup_user_pattern, content_text, re.DOTALL)
                if backup_user_match:
                    current_user = backup_user_match.group(1).strip()
                    print(f"使用备用模式匹配到当前用户名: {current_user}")
                else:
                    print("备用模式也未能匹配到当前用户名")
                    return False
            else:
                current_user = user_match.group(1)
            print(f"current_user: {current_user}")
            
            """
            <tbody><tr><td class="td6" style="text-align:center">排位</td><td class="td6" style="text-align:center">隊伍</td></tr>
            <tr><td class="td7" valign="middle" style="text-align:center">
            <img src="./image/icon/crown01.png" class="vcent" alt=""></td><td class="td8">
            陸斯坎軍團老兵 (3157戰 2283勝807敗 67引 37防 勝率72%)<br>
            </td></tr>
            """

            # 查找第一名用户（在排名表格的第一行，确保在正确的表格结构中）
            # 注意：根据HTML内容，第一名用户名后面紧跟着战绩信息
            # 使用TOP 5作为匹配特征，提高匹配准确性
            first_place_pattern = r'<div class="u">TOP 5</div>[\s\S]*?<td class="td7"[^>]*>\s*<img src="\./image/icon/crown01\.png"[^>]*></td><td class="td8">\s*([^(]+?)\s*\('
            first_place_match = re.search(first_place_pattern, content_text, re.DOTALL)
            if not first_place_match:
                print("未能匹配到第一名用户(TOP 5特征)")
                # 尝试使用更宽松的匹配模式
                backup_pattern = r'<img src="\./image/icon/crown01\.png"[^>]*>[^<]*</td><td class="td8">\s*([^(]+?)\s*\('
                backup_match = re.search(backup_pattern, content_text, re.DOTALL)
                if backup_match:
                    first_place_user = backup_match.group(1).strip()
                    print(f"使用备用模式匹配到第一名用户: {first_place_user}")
                else:
                    # 尝试最宽松的匹配模式
                    last_resort_pattern = r'crown01\.png[^<]*</td><td[^>]*>\s*([^<(]+?)\s*\('
                    last_resort_match = re.search(last_resort_pattern, content_text, re.DOTALL)
                    if last_resort_match:
                        first_place_user = last_resort_match.group(1).strip()
                        print(f"使用最后备用模式匹配到第一名用户: {first_place_user}")
                    else:
                        print("所有备用模式都未能匹配到第一名用户")
                        # 打印HTML中是否包含关键特征
                        if 'crown01.png' in content_text:
                            print("HTML中包含crown01.png图标")
                        if 'TOP 5' in content_text:
                            print("HTML中包含TOP 5文本")
                        if 'td8' in content_text:
                            print("HTML中包含td8类")
                        return False
            else:
                first_place_user = first_place_match.group(1).strip()
            # 打印第一名用户
            print(f"first_place_user: {first_place_user}")
            
            # 比较当前用户是否为第一名
            is_first = current_user == first_place_user
            print(f"用户是否为第一名: {is_first} (当前用户: '{current_user}', 第一名: '{first_place_user}')")
            return is_first
        except Exception as e:
            print(f'判断PVP第一名失败: {str(e)}')
            return False
