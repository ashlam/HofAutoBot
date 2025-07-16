from functools import partial

from scripts.states.directly_challenge_boss_state import DirectlyChallengeBossState
from .base_state import BaseState
from .state_factory import StateFactory
from scripts.boss_battle_manager import BossBattleManager

class NormalBossState(BaseState):
    def process(self):
        """处理普通boss战斗
        Returns:
            str: 下一个游戏状态
        """
        # 先刷新页面获取最新状态
        self.bot._update_info_from_hunt_page()

        # 检查冷却时间
        if self.bot.challenge_next_cooldown > self.bot.IDLE_SECONDS_FOR_CHALLENGE_BOSS:
            # 冷却时间还长，去干别的
            idle_state = StateFactory.create_idle_state(self.bot)
            idle_state.set_idle_time(self.bot.IDLE_SECONDS_FOR_CHALLENGE_BOSS, partial(self.set_state, StateFactory.create_world_pvp_state(self.bot)))
            self.next_state = idle_state
        elif self.bot.challenge_next_cooldown > 0:
            # 冷却时间比较短，等一等然后转到prepare boss
            self.log(f'Boss挑战冷却中，还剩{self.bot.challenge_next_cooldown}秒，等待冷却结束')
            idle_state = StateFactory.create_idle_state(self.bot)
            idle_state.set_idle_time(self.bot.IDLE_SECONDS_FOR_CHALLENGE_BOSS, partial(self.set_state, StateFactory.create_prepare_boss_state(self.bot)))
            self.next_state = idle_state
        else:
            self.log('没有冷却，开刷普通boss')
            is_challenged = False
            for boss in self.bot.auto_bot_config_manager.normal_boss_loop_order:
                if boss['union_id'] not in self.bot.battle_watcher_manager.get_all_alive_boss():
                    self.log(f'普通boss {boss["union_id"]} 未出现，跳过')
                    continue
                else:
                    self.log(f'普通boss {boss["union_id"]} 已出现，尝试处理')
                    # 执行boss战斗动作
                    action = self.bot.server_config_manager.all_action_config_by_server.get(f"{boss['plan_action_id']}")
                    # 检查等级是否溢出
                    if self._check_is_action_level_exceed_boss_limit(boss['plan_action_id'], boss['union_id']):
                        self.log(f'角色总等级溢出，无法处理boss({boss["union_id"]})，跳过。')
                        continue
                    directly_challenge_boss_state = StateFactory.create_directly_challenge_boss_state(self.bot)
                    if isinstance(directly_challenge_boss_state, DirectlyChallengeBossState):
                        directly_challenge_boss_state.union_id = boss['union_id']
                        directly_challenge_boss_state.advanced_action_config = action
                        directly_challenge_boss_state.on_challenge_success = self._on_challenge_normal_boss_success
                        directly_challenge_boss_state.on_challenge_failed = self._on_challenge_normal_boss_failed
                        self.next_state = directly_challenge_boss_state
                        is_challenged = True
                        break
            # 如果没有可以打的boss，进入PVP状态 
            if not is_challenged:
                self.log(f'没有普通boss需要处理, 普通boss清单：{self.bot.auto_bot_config_manager.normal_boss_loop_order}')
                self.next_state = StateFactory.create_world_pvp_state(self.bot)
            
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)

    
    def _on_challenge_normal_boss_success(self):
        self.log('普通boss挑战成功')
        self.next_state = StateFactory.create_world_pvp_state(self.bot)
        self.on_finish()
    
    def _on_challenge_normal_boss_failed(self):
        self.log('普通boss挑战失败，重新准备一次')
        self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        self.on_finish()

    def _check_is_action_level_exceed_boss_limit(self, action_id, boss_id):
        manager = BossBattleManager()
        # action_id = "600080"  # 一服鸟毛
        result = manager.is_action_level_exceed_boss_limit(action_id, boss_id)  # 鳥巢
        print(f"动作(ID:{action_id})中角色等级之和是否超过Boss(ID:8)等级限制: {result}")
        return result