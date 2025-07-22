from math import e
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import json
from scripts.actions.factory import ActionExecutorFactory
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from scripts.advanced_action_executor import AdvancedActionExecutor, AdvancedActionManager
from scripts.server_config_manager import ServerConfigManager
from scripts.battle_watcher_manager import BattleWatcherManager
from scripts.log_manager import LogManager
from scripts.auto_bot_config_manager import AutoBotConfigManager
from scripts.boss_battle_manager import BossBattleManager

from scripts.states.state_factory import StateFactory

# from scripts.states.base_state import BaseState
# from scripts.states.prepare_boss_state import PrepareBossState
# from scripts.states.directly_challenge_boss_state import DirectlyChallengeBossState
# from scripts.states.idle_state import IdleState
# from scripts.states.normal_boss_state import NormalBossState
# from scripts.states.normal_stage_state import NormalStageState
# from scripts.states.pvp_state import PvpState
# from scripts.states.vip_boss_state import VipBossState
# from scripts.states.wait_vip_boss_state import WaitVipBossState
# from scripts.states.world_pvp_state import WorldPvpState

import os

class HofAutoBot:
    def __init__(self):
        """构造函数"""
        self.current_state_str = None
        self.server_config_manager = None
        self.auto_bot_config_manager = None
        self.action_manager = None
        self.is_finished = False
        self.status_update_signal = None

        self.challenge_next_cooldown = 0
        self.player_stamina = 0
        self.waiting_vip_boss_time = 0

        self.next_vip_boss_spawn_timestamp = 0
        self.next_vip_boss_id = 0
        self.is_waiting_for_vip_boss = False
        
        self.logger = LogManager.get_instance()
        self.directly_challenge_boss_id = None
        self.directly_challenge_boss_action = None
        self.boss_battle_manager = None

        from scripts.states.base_state import BaseState
        self.current_state = BaseState(self)

    COOLDOWN_SECONDS_FOR_CHALLENGE_BOSS = 1200

    def set_next_vip_boss_spawn_timestamp(self, vip_boss_id, timestamp):
        self.next_vip_boss_spawn_timestamp = timestamp
        print(f"fffffff {self.next_vip_boss_spawn_timestamp}")
        self.next_vip_boss_id = vip_boss_id
        self.is_waiting_for_vip_boss = True

    def reset_waiting_vip_boss_spawn_info(self):
        self.next_vip_boss_spawn_timestamp = -1
        self.next_vip_boss_id = -1
        self.is_waiting_for_vip_boss = False

    def switch_to_next_state(self, state):
        self.current_state = state
        self.current_state_str = state.__class__.__name__

    def run(self):
        while True:
            if self.is_finished:
                return
            if self.current_state is not None:
                print("HofAutoBot.run -> current_state: " + self.current_state.__class__.__name__)
                self.current_state.process()

    def _check_is_user_pvp_first_rank(self):
        """检查当前用户是否为PVP第一名"""
        return self.battle_watcher_manager.is_user_pvp_first_place(self.driver.page_source)

    def _update_info_from_hunt_page(self):
        self.logger.info(f'{self.server_config_manager.current_server_data["name"]} 开始更新boss信息')
        current_server_data = self.server_config_manager.current_server_data
        hunt_url = f'{current_server_data["url"]}{current_server_data["hunt_page"]}'
        #<a href="#" onclick="RA_UseBack('index2.php?hunt')">冒險</a>
        driver = self.driver
        driver.get(hunt_url)
        # 等待页面加载
        wait = WebDriverWait(driver, 10)
        wait.until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
        # 更新boss信息
        self.battle_watcher_manager.update_all_from_hunt_page(driver.page_source)
        self.all_alived_boss_ids = self.battle_watcher_manager.get_all_alive_boss()
        self.challenge_next_cooldown = self.battle_watcher_manager.get_player_challenge_boss_cooldown()
        self.player_stamina = self.battle_watcher_manager.get_player_stamina()


        # 发送状态更新信号
        if self.status_update_signal:
            status_info = {
                'state': self.current_state_str,
                'stamina': self.player_stamina,
                'cooldown': self.challenge_next_cooldown
            }
            self.status_update_signal.emit(status_info)

        self.logger.info(f'{self.server_config_manager.current_server_data["name"]} 更新boss信息完毕')

    def _get_recover_stamina_time(self, current_stamina, need_stamnia):
        """获取恢复体力的时间"""
        stamina_diff = need_stamnia - current_stamina
        recover_stamnia_per_second = 1000 / 3600
        recover_time = stamina_diff * recover_stamnia_per_second
        return recover_time

   
    def _set_state(self, state):
        """设置当前状态"""
        self.logger.info(f'状态切换：{self.current_state} -> {state}')
         # 发送状态更新信号
        if self.status_update_signal:
            status_info = {
                'state': state,
                'stamina': self.player_stamina,
                'cooldown': self.challenge_next_cooldown
            }
            self.status_update_signal.emit(status_info)
        self.current_state_str = state

    

    def cleanup(self):
        self.is_finished = True
        """释放 Bot 持有的资源"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.error(f"释放 Bot 的浏览器实例时出错: {e}")
            finally:
                self.driver = None
    def initialize_with_driver(self, server_id, driver):
        """初始化自动战斗"""
        self.driver = driver
        self.server_config_manager = ServerConfigManager()
        self.server_config_manager.set_current_server_id(server_id)
        current_server_data = self.server_config_manager.current_server_data

        # 初始化配置和管理器
        auto_bot_config_path = f"{current_server_data.get('config_path')}/{current_server_data.get('auto_bot_loop_config_path')}"
        self.logger.info(f'auto_bot_config_path: {auto_bot_config_path}')

        self.auto_bot_config_manager = AutoBotConfigManager(auto_bot_config_path)
        self.battle_watcher_manager = BattleWatcherManager()
        self.action_manager = AdvancedActionManager()
        self.boss_battle_manager = BossBattleManager()
        self.boss_battle_manager.set_server_id(server_id)
        log_path = os.path.join(os.path.dirname(__file__), '..', 'logs', f'log_server_{current_server_data.get("id")}.txt')
        print(log_path)
        self.logger.set_log_path(log_path)

        if not self.driver:
             # 初始化浏览器
            self.driver = webdriver.Chrome()

        self.driver.get(current_server_data["url"])
        # self.current_state = StateFactory.create_prepare_boss_state(self)
        # 上来先更新一下角色数据
        self.current_state = StateFactory.create_update_character_state(self)


    def _initialize_from_command_line(self):
        """等待登录"""
        # 初始化服务器配置管理器
        self.server_config_manager = ServerConfigManager()
        all_server_info = self.server_config_manager.get_all_server_info_config()
        print('请选择要连接的服务器:')
        # 显示所有可用的服务器
        server_list = all_server_info.get("server_address", [])
        for server in server_list:
            print(f"{server['id']}、{server['name']}")
        
        while True:
            user_input = input('请输入服务器编号，或输入q/no退出: ')
            if user_input.lower() in ['q', 'no']:
                print('已取消打开网址')
                return False
            
            try:
                selected_server_id = int(user_input)
                # 检查是否是有效的服务器ID
                if any(server['id'] == selected_server_id for server in server_list):
                    break
                else:
                    print('无效的服务器编号，请重新输入。')
            except ValueError:
                print('请输入有效的数字。')
        
        # 设置当前服务器
        self.server_config_manager.set_current_server_id(selected_server_id)
        current_server_data = self.server_config_manager.current_server_data
        if not current_server_data:
            print('错误：未找到指定id的服务器数据')
            return False

        url = current_server_data.get('url')
        if not url:
            print('错误：服务器URL为空')
            return False

        print(f'正在连接服务器：{url}')
        print('即将打开浏览器，待登录成功后按y继续')
        
        # 初始化浏览器
        self.driver = webdriver.Chrome()
        self.driver.get(url)
        print('正在打开浏览器...')
        
        # 等待用户确认
        while True:
            user_input = input('准备好开始执行bot了吗？(y/yes)， q/n/no键退出: ').lower()
            if user_input in ['y', 'yes']:
                break
            if user_input in ['n', 'no', 'q']:
                print('已取消执行动作')
                return False
        
        print('已准备好开始执行动作')
        
        # 初始化配置和管理器
        auto_bot_config_path = f"{current_server_data.get('config_path')}/{current_server_data.get('auto_bot_loop_config_path')}"
        self.logger.info(f'auto_bot_config_path: {auto_bot_config_path}')

        self.auto_bot_config_manager = AutoBotConfigManager(auto_bot_config_path)
        self.battle_watcher_manager = BattleWatcherManager()
        self.action_manager = AdvancedActionManager()
        self.boss_battle_manager = BossBattleManager()
        self.boss_battle_manager.set_server_id(selected_server_id)
        self.current_state = StateFactory.create_prepare_boss_state(self)
        return True

if __name__ == '__main__':
    bot = HofAutoBot()
    if bot._initialize_from_command_line():
        bot.run()