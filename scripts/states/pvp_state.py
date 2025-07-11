from .base_state import BaseState
from .state_factory import StateFactory

class PvpState(BaseState):
    def process(self):
        self.log('开始处理PVP')
        if (self.bot.auto_bot_config_manager.is_challenge_pvp and self.bot.auto_bot_config_manager.pvp_plan_action_id > 0):
            # 要打PvP的话，先转到竞技场页面
            pvp_prepare_plan_action_id = self.bot.auto_bot_config_manager.pvp_prepare_plan_action_id
            enter_pvp_prepare_page_action = self.bot.server_config_manager.all_action_config_by_server.get(f"{pvp_prepare_plan_action_id}")
            if enter_pvp_prepare_page_action:
                self.bot.action_manager.execute_advanced_action(self.bot.driver, enter_pvp_prepare_page_action)
                if not self.bot._check_is_user_pvp_first_rank() and self.bot.auto_bot_config_manager.is_keep_pvp_win_rate:
                    self.log('当前用户不是PVP第1名，且需要保持胜率，于是不打PvP了')
                else:
                    pvp_plan_action_id = self.bot.auto_bot_config_manager.pvp_plan_action_id
                    advanced_action_config = self.bot.server_config_manager.all_action_config_by_server.get(f"{pvp_plan_action_id}")
                    if advanced_action_config:
                        self.log(f'进行PVP竞技场挑战：{pvp_plan_action_id}')
                        self.bot.action_manager.execute_advanced_action(self.bot.driver, advanced_action_config)
        self.on_finish()

    def on_finish(self):
        self.set_state(StateFactory.create_prepare_stage_state(self.bot))