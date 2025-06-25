from .base_state import BaseState
from .state_factory import StateFactory
import time

class NormalStageState(BaseState):
    def process(self):
        self.log('开始处理普通关卡')
        for stage in self.bot.auto_bot_config_manager.normal_stage_loop_order:
            self.bot._update_info_from_hunt_page()
            player_stamina = self.bot.battle_watcher_manager.get_player_stamina()
            if (player_stamina < self.bot.auto_bot_config_manager.keep_stamnia_for_change_stage):
                self.log(f'体力不足打小怪...')
                # self.next_state = PrepareBossState(self.bot)
                # break
                continue
            advanced_action_config = self.bot.server_config_manager.all_action_config_by_server.get(f"{stage['plan_action_id']}")
            if advanced_action_config:
                self.log(f'进行普通小怪挑战：{stage["plan_action_id"]}')
                self.bot.action_manager.execute_advanced_action(self.bot.driver, advanced_action_config)
                # time.sleep(5)
        self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)