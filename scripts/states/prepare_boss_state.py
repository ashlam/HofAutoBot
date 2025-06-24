from functools import partial
from .base_state import BaseState
from datetime import datetime
from .state_factory import StateFactory
import time

class PrepareBossState(BaseState):
    def process(self):
        """处理boss战斗逻辑
        Returns:
            str: 下一个游戏状态
        """

        self.log('开始处理boss战斗')
        # 检查挑战boss冷却时间
        self.bot._update_info_from_hunt_page()
        
        # 如果体力不足，但这是个小概率事件
        if self.bot.player_stamina < self.bot.auto_bot_config_manager.boss_cost_stamina:
            recover_time = self.bot._get_recover_stamina_time(self.bot.player_stamina, self.bot.auto_bot_config_manager.boss_cost_stamina)
            self.log(f'体力不足，无法挑战boss，等待{recover_time}秒后重试')
            idle_state = StateFactory.create_idle_state(self.bot)
            idle_state.set_idle_time(recover_time, partial(self.set_state, state = StateFactory.create_prepare_boss_state(self.bot)))
            self.set_state(idle_state)
            return
        
        # 处理冷却时间
        if self.bot.challenge_next_cooldown > 0:
            idle_state = StateFactory.create_idle_state(self.bot)
            # 冷却时间还久的很
            if self.bot.challenge_next_cooldown >= self.bot.IDLE_SECONDS_FOR_CHALLENGE_BOSS:
                # 如果在冷却中，去干点别的
                next_challange_real_time = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S.%f')
                self.log(f'BOSS冷却还早，当前体力：{self.bot.player_stamina}，下次boss挑战时间：{next_challange_real_time}，于是去干别的')
                # self._set_state(self.GAME_STATE_PVP)
                idle_state.set_idle_time(self.bot.IDLE_SECONDS_FOR_CHALLENGE_BOSS, partial(self.set_state, state = StateFactory.create_world_pvp_state(self.bot)))
                self.set_state(idle_state)
                return
                
            # 耐心等一下就能打boss了
            else:
                self.log(f'Boss挑战冷却中，还剩{self.bot.challenge_next_cooldown}秒，等待冷却结束')
                idle_state.set_idle_time(self.bot.challenge_next_cooldown, partial(self.set_state, state = StateFactory.create_prepare_boss_state(self.bot)))
                self.set_state(idle_state)
                return
        
        self.log('没有冷却时间，进入boss选择流程')
        
        if self.bot.is_waiting_for_vip_boss:
            # 如果正在等待vipboss，则交出管辖权
            self.next_state = StateFactory.create_wait_vip_boss_state(self.bot)
        elif self.bot.auto_bot_config_manager.is_challenge_vip_boss:
            self.next_state = StateFactory.create_vip_boss_state(self.bot)
        else:
            self.next_state = StateFactory.create_normal_boss_state(self.bot)
        # 如果没有冷却时间，直接打boss
        self.on_finish()
        


    def on_finish(self):
        """准备挑战boss的逻辑
            正常走到这里应该是体力充沛且无冷却的状态
        """
        self.set_state(self.next_state)