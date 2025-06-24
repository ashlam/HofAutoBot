from .base_state import BaseState
from .state_factory import StateFactory

class PvpState(BaseState):
    def process(self):
        self.log('开始处理PVP')
        if (self.bot.auto_bot_config_manager.is_challenge_pvp and self.bot.auto_bot_config_manager.pvp_plan_action_id > 0):
            pvp_plan_action_id = self.bot.auto_bot_config_manager.pvp_plan_action_id
            advanced_action_config = self.bot.server_config_manager.all_action_config_by_server.get(f"{pvp_plan_action_id}")
            if advanced_action_config:
                self.log(f'进行PVP竞技场挑战：{pvp_plan_action_id}')
                self.bot.action_manager.execute_advanced_action(self.bot.driver, advanced_action_config)
        self.on_finish()

    def on_finish(self):
        self.set_state(StateFactory.create_normal_stage_state(self.bot))