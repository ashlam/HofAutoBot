import re
import requests
import json
import os
from datetime import datetime, timedelta
from selenium import webdriver

from scripts.battle_watcher_manager import BattleWatcherManager


# def check_game_status(content_text):
#     """检查游戏状态，获取体力值和冷却时间"""
#     try:
#         content = content_text
        
#         # 匹配体力值
#         stamina_pattern = r'<span id="mtime">(\d+)</span>'
#         stamina_match = re.search(stamina_pattern, content)
        
#         # 匹配冷却时间
#         cooldown_pattern = r'離下次戰鬥還需要 : <span class="bold">(\d+:\d+)</span>'
#         cooldown_match = re.search(cooldown_pattern, content)

#         print(content)
        
#         if stamina_match and cooldown_match:
#             stamina = stamina_match.group(1)
#             cooldown = cooldown_match.group(1)
#             # 将冷却时间转换为秒数
#             minutes, seconds = map(int, cooldown.split(':'))
#             total_seconds = minutes * 60 + seconds
#             print(f'当前体力值: {stamina}/4000')
#             print(f'剩余冷却时间:{cooldown}（剩余{total_seconds}秒）')
#             return True
#         else:
#             print('未找到游戏状态信息')
#             return False
#     except Exception as e:
#         print(f'获取游戏状态失败: {str(e)}')
#         return False


def main():
    
    print('\n正在获取Boss战斗时间...')
    union_id = 17
    # 创建BattleWatcherManager实例
    battle_manager = BattleWatcherManager()
    
    # 获取boss的下次战斗时间
    battle_time = battle_manager.get_boss_next_battle_real_time(union_id)
    
    if battle_time:
        print(f'Boss上次战斗时间: {battle_time["original"]}')
        print(f'Boss下次战斗时间: {battle_time["future"]}')
    else:
        print('获取Boss战斗时间失败')
    
    url = 'https://pim0110.com/hall/index.php?hunt#'
    driver = webdriver.Chrome()
    driver.get(url)
    print('正在打开浏览器...')
    # 等待用户确认
    while True:
        user_input = input('是否已登录？登录后才可以继续后续操作(y/yes继续，其他键退出): ').lower()
        if user_input not in ['y', 'yes']:
            print('已取消更新操作')
            break
        # 检查游戏状态
        print('正在检查游戏状态...')
        driver.get(url)

if __name__ == '__main__':
    main()