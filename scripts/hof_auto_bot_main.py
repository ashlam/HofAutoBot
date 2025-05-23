from math import e
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import json
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from scripts.server_config_manager import ServerConfigManager
from scripts.battle_watcher_manager import BattleWatcherManager
from scripts.action_executor import ActionExecutor
from scripts.log_manager import LogManager
import os

class AutoBotConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        with open(self.config_path, 'r') as f:
            return json.load(f)

    @property
    def boss_cost_stamina(self) -> int:
        return self.config.get('boss_cost_stamina', 10)

    @property
    def stage_cost_stamina(self) -> int: # 小怪消耗体力
        return self.config.get('stage_cost_stamina', 100)
    @property
    def keep_stamnia_for_change_stage(self) -> int: # 切换小怪消耗体力
        return self.config.get('keep_stamnia_for_change_stage', 1000)
    @property
    def quest_cost_stamina(self) -> int: # 任务消耗体力
        return self.config.get('quest_cost_stamina', 300)

    @property
    def max_stamnia_limit(self) -> int: # 体力上限
        return self.config.get('max_stamnia_limit', 4000)

    @property
    def is_challenge_vip_boss(self) -> bool:
        return self.config.get('is_challenge_vip_boss', False)

    @property
    def is_challenge_pvp(self) -> bool:
        return self.config.get('is_challenge_pvp', False)

    @property
    def is_challenge_world_pvp(self) -> bool:
        return self.config.get('is_challenge_world_pvp', False)

    @property
    def vip_boss_need_watch(self) -> List[Dict]:
        return self.config.get('vip_boss_need_watch', [])

    @property
    def normal_boss_loop_order(self) -> List[Dict]:
        return self.config.get('normal_boss_loop_order', [])

    @property
    def normal_stage_loop_order(self) -> List[Dict]:
        return self.config.get('normal_stage_loop_order', [])

    @property
    def pvp_plan_action_id(self) -> int:
        return self.config.get('pvp_plan_action_id', 0)

    @property
    def world_pvp_plan_action_id(self) -> int:
        return self.config.get('world_pvp_plan_action_id', 0)

class HofAutoBot:
    def __init__(self):
        """构造函数"""
        self.current_state = None
        self.server_config_manager = None
        self.auto_bot_config_manager = None
        self.action_executor = None
        self.is_finished = False
        self.status_update_signal = None

        self.challenge_next_cooldown = 0
        self.player_stamina = 0
        self.waiting_vip_boss_time = 0
        self.logger = LogManager.get_instance()

    # 定义游戏状态
    GAME_STATE_BOSS = 'boss'
    GAME_STATE_NORMAL_BOSS = 'normal_boss'
    GAME_STATE_VIP_BOSS = 'vip_boss'
    GAME_STATE_WAIT_VIP_BOSS = 'wait_vip_boss'
    GAME_STATE_PVP = 'pvp'
    GAME_STATE_WORLD_PVP = 'world_pvp'
    GAME_STATE_NORMAL_STAGE = 'normal_stage'
    GAME_STATE_IDLE_FOR_BOSS = 'idle_for_boss'

    IDLE_SECONDS_FOR_REFRESH = 1
    IDLE_SECONDS_FOR_RECOVER_STAMINA = 7
    IDLE_SECONDS_FOR_CHALLENGE_BOSS = 30
    COOLDOWN_SECONDS_FOR_CHALLENGE_BOSS = 1200

    def run(self):
        """运行主循环"""
        
        self.current_state = self.GAME_STATE_BOSS
        
        while True:
            if self.is_finished:
                return
            # 根据当前状态执行相应的操作
            if self.current_state == self.GAME_STATE_BOSS:
                self._process_boss_battle()
            elif self.current_state == self.GAME_STATE_NORMAL_BOSS:
                self._process_normal_boss()
            elif self.current_state == self.GAME_STATE_VIP_BOSS:
                self._process_vip_boss()
            elif self.current_state == self.GAME_STATE_WAIT_VIP_BOSS:
                self._process_wait_vip_boss()
            elif self.current_state == self.GAME_STATE_PVP:
                self._execute_pvp_action()
            elif self.current_state == self.GAME_STATE_WORLD_PVP:
                self._execute_world_pvp_action()
            elif self.current_state == self.GAME_STATE_NORMAL_STAGE:
                self._execute_normal_stage()
            elif self.current_state == self.GAME_STATE_IDLE_FOR_BOSS:
                self._process_idle_for_challenge_boss()
            else:
                self._set_state(self.GAME_STATE_BOSS)

    def _update_info_from_hunt_page(self):
        self.logger.info('开始更新boss信息')
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
                'state': self.current_state,
                'stamina': self.player_stamina,
                'cooldown': self.challenge_next_cooldown
            }
            self.status_update_signal.emit(status_info)

        self.logger.info('更新boss信息完毕', True)

    def _get_recover_stamina_time(self, current_stamina, need_stamnia):
        """获取恢复体力的时间"""
        stamina_diff = need_stamnia - current_stamina
        recover_stamnia_per_second = 1000 / 3600
        recover_time = stamina_diff * recover_stamnia_per_second
        return recover_time

    def _process_boss_battle(self):
        """处理boss战斗逻辑
        Returns:
            str: 下一个游戏状态
        """
        self.logger.info('开始处理boss战斗')
        # 检查挑战boss冷却时间
        self._update_info_from_hunt_page()
        
        # 如果体力不足
        if self.player_stamina < self.auto_bot_config_manager.boss_cost_stamina:
            recover_time = self._get_recover_stamina_time(self.player_stamina, self.auto_bot_config_manager.boss_cost_stamina)
            self.logger.warning(f'体力不足，无法挑战boss，等待{recover_time}秒后重试')
            if recover_time > 0:
                time.sleep(recover_time)
            self._set_state(self.GAME_STATE_BOSS)
            return
        
        # 处理冷却时间
        if self.challenge_next_cooldown > 0:
            if self.challenge_next_cooldown >= self.IDLE_SECONDS_FOR_CHALLENGE_BOSS:
                # 如果在冷却中，且体力大于一定值，去干点别的
                next_challange_real_time = time.time() + self.challenge_next_cooldown
                self.logger.info(f'BOSS冷却还早，当前体力：{self.player_stamina}，下次boss挑战时间：{next_challange_real_time}，于是去干别的')
                self._set_state(self.GAME_STATE_PVP)
                return
                
            # 耐心等一下就能打boss了
            else:
                self.logger.info(f'Boss挑战冷却中，还剩{self.challenge_next_cooldown}秒，等待冷却结束')
                time.sleep(self.challenge_next_cooldown)
        
        # 如果没有冷却时间，可以打boss
        self.logger.info('进入boss检查流程')
        self._on_prepare_challenge_boss()

    def _on_prepare_challenge_boss(self):
        """准备挑战boss的逻辑
            正常走到这里应该是体力充沛且无冷却的状态
        """
        # 但还是要再刷一遍hunt，以更新boss存活信息。
        self._update_info_from_hunt_page()
        # 先看看要不要打vip boss
        if self.auto_bot_config_manager.is_challenge_vip_boss and self.auto_bot_config_manager.vip_boss_need_watch:
            self._process_vip_boss()
        else:
            # 没有打vip boss，检查普通boss
            self._process_normal_boss()
    def _process_vip_boss(self):
        """ 处理VIP boss战斗
            如果出现就直接打，如果没有出现则看一下历史记录，看要不要等待。
            注意等待vip boss的过程是在这里处理的，后面Normal boss就不管这个了
        """
        # 刷一下
        self._update_info_from_hunt_page()
        for vip_boss in self.auto_bot_config_manager.vip_boss_need_watch:
            union_id = vip_boss['union_id']
            plan_action_id = vip_boss['plan_action_id']
            action = self.server_config_manager.all_action_config_by_server.get(f"{plan_action_id}")
            if not action:
                self.logger.error(f'未找到动作配置，id: {plan_action_id} ，没有办法处理boss({union_id})，中止处理。')
                continue
            # 检查VIP boss是否出现
            if union_id in self.all_alived_boss_ids:
                # 活着，试着干它
                self.logger.info(f'VIP boss {union_id} 已出现，BEAT IT！！！')
                self.action_executor.execute_actions(self.driver, action)
                # 打完了，更新一下信息，看打成功没有（有可能被人抢了）
                self.logger.info(f"锤完了，更新一下信息，看打成功没有（有可能被人抢了）", True)
                self._update_info_from_hunt_page()
                # 如果自己进冷却，说明打成功了，跳出循环并结束
                if self.challenge_next_cooldown > 0:
                    self._on_challenge_vip_boss_finished(True)
                    return
            else:
                # 没活着，看下历史记录
                boss_log_url = f"{self.server_config_manager.current_server_data['url']}?ulog"
                kill_cooldown = vip_boss.get('kill_cooldown_seconds', 14400)
                # 获取boss下次被击败的时间
                next_battle_info = self.battle_watcher_manager.get_boss_next_battle_real_time(union_id, kill_cooldown, boss_log_url)
                if not next_battle_info:
                    # 如果没有记录，说明可能boss记录太多了，那也没办法，就算了
                    self.logger.warning(f'未找到上次vip boss被击败的时间，id: {union_id} ，没有办法处理boss({union_id})，去处理下一个vip boss。')
                    continue
                else:
                    # 计算下次刷新时间
                    next_spawn_time = datetime.fromtimestamp(next_battle_info['future_unixtime'])
                    time_until_spawn = (next_spawn_time - datetime.now()).total_seconds()
                    seconds = int(time_until_spawn)
                    minutes, seconds = divmod(seconds, 60)
                    self.logger.info(f"vip boss({union_id})将于{next_spawn_time}刷新，距离刷新还有{minutes}分{seconds}秒", True)
                    wait_time = min(self.COOLDOWN_SECONDS_FOR_CHALLENGE_BOSS, max(0, time_until_spawn))
                    self.logger.info(f"{ '将于%.2f秒后暂停' % wait_time if wait_time > 0 else '已暂停' }挑战普通boss行为，专心等vip", True)

                    # 如果很快就会刷新，等一等直接打
                    if time_until_spawn <= wait_time:
                        self.logger.info(f'VIP boss {union_id} 将在 {time_until_spawn} 秒后刷新。注意不要打其他Boss，去干别的。', True)
                        self._set_wait_vip_boss_time(time_until_spawn)
                        self._set_state(self.GAME_STATE_WAIT_VIP_BOSS)
                        return
                    else:
                        # 还早，甭管它了，处理下一个
                        continue
            continue
        # 走到这里说明所有vip boss都处理过了
        self._on_challenge_vip_boss_finished(False)

    def _set_wait_vip_boss_time(self, wait_time):
        """设置等待VIP boss的时间"""
        self.logger.info(f"设置等待VIP boss的时间为 {wait_time} 秒", True)
        self.waiting_vip_boss_time = wait_time

    def _process_wait_vip_boss(self):
        """处理等待VIP boss的逻辑"""
        if self.waiting_vip_boss_time <= 0:
            self.logger.info("等待vip finished，可以尝试打vip boss", True)
            self._set_state(self.GAME_STATE_VIP_BOSS)
            return
        elif self.waiting_vip_boss_time > self.IDLE_SECONDS_FOR_CHALLENGE_BOSS:
            next_active_time = datetime.now() + timedelta(seconds=self.IDLE_SECONDS_FOR_CHALLENGE_BOSS)
            self.logger.info("在等vip boss，但时间太久了，干点别的去，省的被踢掉！")
            self.logger.info(f"...但也不能刷太快发个呆。{next_active_time}后继续行动")
            # 加一点发呆时间，既避免长时间不动被踢掉，也避免刷新太快被ban掉
            self._idle_and_update_cooldown(self.IDLE_SECONDS_FOR_CHALLENGE_BOSS)
            self._set_state(self.GAME_STATE_PVP)
            return
        else:
            if self.waiting_vip_boss_time > 0:
                idle_time = min(self.waiting_vip_boss_time - self.IDLE_SECONDS_FOR_REFRESH, self.IDLE_SECONDS_FOR_REFRESH)
                idle_time = max(idle_time, 0)
                if idle_time > 0:
                    self._idle_and_update_cooldown(idle_time)
            self._set_state(self.GAME_STATE_VIP_BOSS)

    def _on_challenge_vip_boss_finished(self, is_challenged_vip_boss = False):
        """处理完VIP boss战斗后的逻辑"""
        self.logger.info(f"已处理完VIP boss战斗，{ '已挑战' if is_challenged_vip_boss else '未挑战' }vip boss", True)
        if is_challenged_vip_boss:
            self._set_state(self.GAME_STATE_PVP)
        else:
            self._set_state(self.GAME_STATE_NORMAL_BOSS)

    def _idle_and_update_cooldown(self, idle_time):
        """发呆并更新冷却时间"""
        self.logger.info(f"发呆{idle_time}秒", True)
        if idle_time > 0:
            time.sleep(idle_time)
        self.challenge_next_cooldown -= idle_time
        self.challenge_next_cooldown = max(0, self.challenge_next_cooldown)
        self.waiting_vip_boss_time -= idle_time
        self.waiting_vip_boss_time = max(0, self.waiting_vip_boss_time)
        self.logger.info(f"发呆结束，剩余冷却时间: {self.challenge_next_cooldown} 秒", True)            

    def _process_normal_boss(self):
        """处理普通boss战斗
        Returns:
            str: 下一个游戏状态
        """
        # 先刷新页面获取最新状态
        self._update_info_from_hunt_page()

        # 检查冷却时间
        if self.challenge_next_cooldown > self.IDLE_SECONDS_FOR_CHALLENGE_BOSS:
            # 冷却时间还长，去干别的
            self._idle_and_update_cooldown(self.IDLE_SECONDS_FOR_CHALLENGE_BOSS)
            self._on_challenge_normal_boss_finished()
            return
        elif self.challenge_next_cooldown > 0:
            # 冷却时间还短，先等一等
            self.logger.info(f'Boss挑战冷却中，还剩{self.challenge_next_cooldown}秒，等待冷却结束')
            time.sleep(self.challenge_next_cooldown)
            self._update_info_from_hunt_page()
            return

        self.logger.info('没有冷却，开刷普通boss')
        for boss in self.auto_bot_config_manager.normal_boss_loop_order:
            if boss['union_id'] not in self.battle_watcher_manager.get_all_alive_boss():
                self.logger.info(f'普通boss {boss["union_id"]} 未出现，跳过')
                continue
            else:
                self.logger.info(f'普通boss {boss["union_id"]} 已出现，尝试处理')
                # 执行boss战斗动作
                action = self.server_config_manager.all_action_config_by_server.get(f"{boss['plan_action_id']}")
                self.action_executor.execute_actions(self.driver, action)
                time.sleep(5)
                self._on_challenge_normal_boss_finished()
                return
        
        # 如果没有可以打的boss，进入PVP状态
        self.logger.info(f'没有普通boss需要处理, 普通boss清单：{self.auto_bot_config_manager.normal_boss_loop_order}')
        self._on_challenge_normal_boss_finished()

    def _on_challenge_normal_boss_finished(self):
        """处理boss战斗完成后的逻辑"""
        self._set_state(self.GAME_STATE_PVP)

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
        self.current_state = state

    def _execute_pvp_action(self):
        """执行PVP战斗动作"""
        if (self.auto_bot_config_manager.is_challenge_pvp and self.auto_bot_config_manager.pvp_plan_action_id > 0):
            pvp_plan_action_id = self.auto_bot_config_manager.pvp_plan_action_id
            action = self.server_config_manager.all_action_config_by_server.get(f"{pvp_plan_action_id}")
            if action:
                self.logger.info(f'进行PVP竞技场挑战：{pvp_plan_action_id}')
                self.action_executor.execute_actions(self.driver, action)
        self._challenge_pvp_finished()

    def _challenge_pvp_finished(self):
        """处理PVP竞技场完成后的逻辑"""
        # self._execute_world_pvp_action()
        self._set_state(self.GAME_STATE_WORLD_PVP)

    def _execute_world_pvp_action(self):
        """执行世界PVP战斗动作"""
        if (self.auto_bot_config_manager.is_challenge_world_pvp and self.auto_bot_config_manager.world_pvp_plan_action_id > 0):
            world_pvp_plan_action_id = self.auto_bot_config_manager.world_pvp_plan_action_id
            action = self.server_config_manager.all_action_config_by_server.get(f"{world_pvp_plan_action_id}")
            if action:
                self.logger.info(f'进行世界PVP竞技场挑战：{world_pvp_plan_action_id}')
                self.action_executor.execute_actions(self.driver, action)
        self._on_challenge_world_pvp_finished()

    def _on_challenge_world_pvp_finished(self):
        """处理世界PVP战斗完成后的逻辑"""
        # self._execute_normal_stage()
        self._set_state(self.GAME_STATE_NORMAL_STAGE)

    def _execute_normal_stage(self):
        """执行普通小怪战斗
        Returns:
            str: 下一个游戏状态
        """

        for stage in self.auto_bot_config_manager.normal_stage_loop_order:
            # 刷一下战斗界面，看看剩余体力
            self._update_info_from_hunt_page()
            player_stamina = self.battle_watcher_manager.get_player_stamina()
            if (player_stamina < self.auto_bot_config_manager.keep_stamnia_for_change_stage):
                self.logger.warning(f'体力不足打小怪...')
                self._set_state(self.GAME_STATE_IDLE_FOR_BOSS)
                return
            action = self.server_config_manager.all_action_config_by_server.get(f"{stage['plan_action_id']}")
            if action:
                self.logger.info(f'进行普通小怪挑战：{stage["plan_action_id"]}')
                self.action_executor.execute_actions(self.driver, action)
                time.sleep(5)

        # 完成所有小怪战斗后，返回boss状态
        self._on_challenge_normal_stage_finished()

    def _on_challenge_normal_stage_finished(self):
        """处理普通小怪战斗完成后的逻辑"""
        # self._process_boss_battle()
        self._set_state(self.GAME_STATE_BOSS)

    def _process_idle_for_challenge_boss(self):
        """处理在挑战Boss前的空闲状态"""
        idle_time = min(self.waiting_vip_boss_time, self.IDLE_SECONDS_FOR_CHALLENGE_BOSS) if self.waiting_vip_boss_time > 0 else self.IDLE_SECONDS_FOR_CHALLENGE_BOSS 
        self.logger.info(f'进入空闲状态，等待{idle_time}秒后开始挑战Boss')
        self._idle_and_update_cooldown(idle_time)
        self._set_state(self.GAME_STATE_BOSS)

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
        self.action_executor = ActionExecutor()
        log_path = os.path.join(os.path.dirname(__file__), '..', 'logs', f'log_server_{current_server_data.get("id")}.txt')
        print(log_path)
        self.logger.set_log_path(log_path)

        if not self.driver:
             # 初始化浏览器
            self.driver = webdriver.Chrome()

        self.driver.get(current_server_data["url"])


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
        self.action_executor = ActionExecutor()
        return True

if __name__ == '__main__':
    bot = HofAutoBot()
    if bot._initialize_from_command_line():
        bot.run()