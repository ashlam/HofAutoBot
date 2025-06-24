from .base_state import BaseState
from .state_factory import StateFactory

class WorldPvpState(BaseState):
    def process(self):
        """执行世界PVP战斗动作"""
        if (self.bot.auto_bot_config_manager.is_challenge_world_pvp and self.bot.auto_bot_config_manager.world_pvp_plan_action_id > 0):
            world_pvp_plan_action_id = self.bot.auto_bot_config_manager.world_pvp_plan_action_id
            advanced_action_config = self.bot.server_config_manager.all_action_config_by_server.get(f"{world_pvp_plan_action_id}")
            if advanced_action_config:
                self.log(f'进行世界PVP竞技场挑战：{world_pvp_plan_action_id}')
                self.bot.action_manager.execute_advanced_action(self.bot.driver, advanced_action_config)
        self.on_finish()

    def on_finish(self):
        self.set_state(StateFactory.create_pvp_state(self.bot))