from math import e
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import json
from selenium import webdriver
from server_config_manager import ServerConfigManager
from battle_watcher_manager import BattleWatcherManager
from action_executor import ActionExecutor

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
        pass

    def run(self):
        """运行主循环"""
        # 定义游戏状态
        GAME_STATE_BOSS = 'boss'
        GAME_STATE_PVP = 'pvp'
        GAME_STATE_WORLD_PVP = 'world_pvp'
        GAME_STATE_NORMAL_STAGE = 'normal_stage'
        
        current_state = GAME_STATE_BOSS
        
        while True:
            # 根据当前状态执行相应的操作
            if current_state == GAME_STATE_BOSS:
                current_state = self._process_boss_battle()
            elif current_state == GAME_STATE_PVP and self.auto_bot_config_manager.is_challenge_pvp:
                self.pvp_manager.execute_pvp_action(self.auto_bot_config_manager.pvp_plan_action_id)
                current_state = GAME_STATE_WORLD_PVP
            elif current_state == GAME_STATE_WORLD_PVP and self.auto_bot_config_manager.is_challenge_world_pvp:
                self.pvp_manager.execute_world_pvp_action(self.auto_bot_config_manager.world_pvp_plan_action_id)
                current_state = GAME_STATE_NORMAL_STAGE
            elif current_state == GAME_STATE_NORMAL_STAGE:
                current_state = self._execute_normal_stage()
            else:
                current_state = GAME_STATE_BOSS

    def _update_info_from_hunt_page(self):
        current_server_data = self.server_config_manager.current_server_data
        hunt_url = f'{current_server_data["url"]}{current_server_data["hunt_page"]}'
        #<a href="#" onclick="RA_UseBack('index2.php?hunt')">冒險</a>
        driver = self.driver
        # 等待页面加载
        time.sleep(2)
        driver.get(hunt_url)
        self.battle_watcher_manager.update_all_from_hunt_page(driver.page_source)


    def _process_boss_battle(self):
        """处理boss战斗逻辑
        Returns:
            str: 下一个游戏状态
        """
        print('开始处理boss战斗')
        # 检查挑战boss冷却时间
        self._update_info_from_hunt_page()
        challenge_next_cooldown = self.battle_watcher_manager.get_player_challenge_boss_cooldown()
        player_stamina = self.battle_watcher_manager.get_player_stamina()
        all_alived_boss_ids = self.battle_watcher_manager.get_all_alive_boss()
        
        # 如果体力不足
        if player_stamina < self.auto_bot_config_manager.boss_cost_stamina:
            print('体力不足，无法挑战boss，等待5秒后重试')
            time.sleep(5)
            return 'boss'
        
        # 处理冷却时间
        if challenge_next_cooldown > 0:
            if challenge_next_cooldown > 10:
                # 如果在冷却中，且体力大于一定值，执行小怪战斗
                if player_stamina >= self.auto_bot_config_manager.keep_stamnia_for_change_stage:
                    next_challange_real_time = time.time() + challenge_next_cooldown
                    print(f'冷却中，当前体力：{player_stamina}，下次boss挑战时间：{next_challange_real_time}，于是去练级')
                    return 'pvp'
                else:
                    print(f'Boss挑战冷却中，还剩{challenge_next_cooldown}秒，但体力不足，等待10秒后重试')
                    time.sleep(10)
                    return 'boss'
            else:
                print(f'Boss挑战冷却中，还剩{challenge_next_cooldown}秒，等待冷却结束')
                time.sleep(challenge_next_cooldown)
                return 'boss'
        
        # 如果没有冷却时间，可以打boss
        print('进入vip boss检查流程')
        # 检查是否需要打VIP boss
        if self.auto_bot_config_manager.is_challenge_vip_boss and self.auto_bot_config_manager.vip_boss_need_watch:
            for vip_boss in self.auto_bot_config_manager.vip_boss_need_watch:
                vip_boss_id = vip_boss['union_id']
                if not vip_boss_id in all_alived_boss_ids:
                    continue
                # 处理Vip boss，如果返回True，则表示打过了Boss或已设定等待打该Boss。否则继续处理下一个VIP boss
                if self._handle_vip_boss(vip_boss):
                    # 如果成功处理了VIP boss战斗，则进入PVP状态
                    return 'pvp'
                else:
                    continue

        print('进入普通 boss检查流程')
        # 如果没有VIP boss或不需要打VIP boss，则处理普通boss
        return self._process_normal_boss()

    def _handle_vip_boss(self, vip_boss: Dict) -> bool:
        """处理VIP boss战斗
        Returns:
            bool: 是否成功处理了VIP boss战斗，
                True = 打过了Boss或已设定等待打该Boss，接下来应该去打小怪。
                False = 不需要处理VIP boss战斗，可以去打其他Boss。
        """
        union_id = vip_boss['union_id']
        plan_action_id = vip_boss['plan_action_id']
        kill_cooldown = vip_boss.get('kill_cooldown_seconds', 14400)
        action = self.server_config_manager.all_action_config_by_server.get(f"{plan_action_id}")
        if not action:
            print(f'错误：未找到动作配置，id: {plan_action_id} ，没有办法处理boss({union_id})，中止处理。')
            return False
        # 检查VIP boss是否出现
        if union_id in self.battle_watcher_manager.get_all_alive_boss():
            print(f'VIP boss {union_id} 已出现，尝试处理')
            # 执行boss战斗动作
            self.action_executor.execute_actions(self.driver, action)
            return True
        # 否则说明当前没有该boss存在，即已被打败
        else:
            # 获取boss下次被击败的时间
            next_battle_info = self.battle_watcher_manager.get_boss_next_battle_real_time(union_id, kill_cooldown)
            if not next_battle_info or next_battle_info:
                # 如果没有记录，说明可能boss记录太多了，那也没办法，就算了
                print(f'未找到上次boss被击败的时间，id: {union_id} ，没有办法处理boss({union_id})，中止处理。')
                return False
            # 计算下次刷新时间
            next_spawn_time = next_battle_info['future_unixtime']
            time_until_spawn = (next_spawn_time - datetime.now()).total_seconds()

            # 如果20分钟内会刷新
            if time_until_spawn < 30:
                print(f'VIP boss {union_id} 将在 {time_until_spawn} 秒后刷新，尝试处理。')
                time.sleep(time_until_spawn)
                # 虽然上次没有出现，但根据计算现在已经刷新，直接执行boss战斗动作
                self.action_executor.execute_actions(self.driver, action)
                return True
            elif time_until_spawn < 1200:
                print(f'VIP boss {union_id} 将在 {time_until_spawn} 秒后刷新。注意不要打其他Boss，可以去打小怪。')
                # 20分钟内会刷新，去打小怪，不要去打Boss
                return True
            else:
                print(f'VIP boss {union_id} 将在 {time_until_spawn} 秒后刷新。时间还早，去处理其他Boss。')
                return False

    def _process_normal_boss(self):
        """处理普通boss战斗
        Returns:
            str: 下一个游戏状态
        """
        # 先刷新页面获取最新状态
        self._update_info_from_hunt_page()
        challenge_next_cooldown = self.battle_watcher_manager.get_player_challenge_boss_cooldown()
        player_stamina = self.battle_watcher_manager.get_player_stamina()
        idle_seconds = 60

        # 检查冷却时间
        if challenge_next_cooldown > idle_seconds:
            # 如果在冷却中，且体力大于一定值，执行小怪战斗
            if player_stamina >= self.auto_bot_config_manager.keep_stamnia_for_change_stage:
                print(f'冷却中，当前体力：{player_stamina}，于是去练级')
                return 'pvp'
            else:
                print(f'冷却中，当前体力：{player_stamina}，等待{idle_seconds}秒后重试')
                time.sleep(idle_seconds)
                return 'boss'

        print('没有冷却，准备刷boss')
        for boss in self.auto_bot_config_manager.normal_boss_loop_order:
            if boss['union_id'] not in self.battle_watcher_manager.get_all_alive_boss():
                print(f'普通boss {boss["union_id"]} 未出现，跳过')
                continue
            else:
                print(f'普通boss {boss["union_id"]} 已出现，尝试处理')
                # 执行boss战斗动作
                action = self.server_config_manager.all_action_config_by_server.get(f"{boss['plan_action_id']}")
                self.action_executor.execute_actions(self.driver, action)
                time.sleep(5)
                return 'pvp'
        
        # 如果没有可以打的boss，进入PVP状态
        print(f'没有普通boss需要处理, 普通boss清单：{self.auto_bot_config_manager.normal_boss_loop_order}')
        return 'pvp'

    def _on_challenge_boss_finished(self):
        """处理boss战斗完成后的逻辑"""
        # 执行完boss战斗后，刷新页面
        self._update_info_from_hunt_page()
        # 如果刷新后发现没冷却，说明boss没打成功，再打一次。
        if (self.battle_watcher_manager.get_player_challenge_boss_cooldown() == 0):
            print('boss没打成功，再打一次')
            self._process_boss_battle()
            return
        # 否则，执行下一个动作
        self._execute_pvp_action()

    def _execute_pvp_action(self):
        """执行PVP战斗动作"""
        if (self.auto_bot_config_manager.is_challenge_pvp and self.auto_bot_config_manager.pvp_plan_action_id > 0):
            pvp_plan_action_id = self.auto_bot_config_manager.pvp_plan_action_id
            action = self.server_config_manager.all_action_config_by_server.get(f"{pvp_plan_action_id}")
            if action:
                print(f'进行PVP竞技场挑战：{pvp_plan_action_id}')
                self.action_executor.execute_actions(self.driver, action)
        self._challenge_pvp_finished()

    def _challenge_pvp_finished(self):
        """处理PVP竞技场完成后的逻辑"""
        self._execute_world_pvp_action()

    def _execute_world_pvp_action(self):
        """执行世界PVP战斗动作"""
        if (self.auto_bot_config_manager.is_challenge_world_pvp and self.auto_bot_config_manager.world_pvp_plan_action_id > 0):
            world_pvp_plan_action_id = self.auto_bot_config_manager.world_pvp_plan_action_id
            action = self.server_config_manager.all_action_config_by_server.get(f"{world_pvp_plan_action_id}")
            if action:
                print(f'进行世界PVP竞技场挑战：{world_pvp_plan_action_id}')
                self.action_executor.execute_actions(self.driver, action)
        self._on_challenge_world_pvp_finished()

    def _on_challenge_world_pvp_finished(self):
        """处理世界PVP战斗完成后的逻辑"""
        self._execute_normal_stage()

    def _execute_normal_stage(self):
        """执行普通小怪战斗
        Returns:
            str: 下一个游戏状态
        """
        # 刷一下战斗界面，看看剩余体力
        self._update_info_from_hunt_page()
        player_stamina = self.battle_watcher_manager.get_player_stamina()
        if (player_stamina < self.auto_bot_config_manager.keep_stamnia_for_change_stage):
            print(f'体力不足，回boss界面...')
            return 'boss'

        for stage in self.auto_bot_config_manager.normal_stage_loop_order:
            action = self.server_config_manager.all_action_config_by_server.get(f"{stage['plan_action_id']}")
            if action:
                print(f'进行普通小怪挑战：{stage["plan_action_id"]}')
                self.action_executor.execute_actions(self.driver, action)
                time.sleep(5)
        
        # 完成所有小怪战斗后，返回boss状态
        return 'boss'

    def _on_challenge_normal_stage_finished(self):
        """处理普通小怪战斗完成后的逻辑"""
        self._process_boss_battle()

    def _initialize(self):
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
        print(f'auto_bot_config_path: {auto_bot_config_path}')

        self.auto_bot_config_manager = AutoBotConfigManager(auto_bot_config_path)
        self.battle_watcher_manager = BattleWatcherManager()
        self.action_executor = ActionExecutor()
        return True

if __name__ == '__main__':
    bot = HofAutoBot()
    if bot._initialize():
        bot.run()