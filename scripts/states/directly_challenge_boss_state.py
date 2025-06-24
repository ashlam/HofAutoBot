from .base_state import BaseState
from scripts.hof_auto_bot_main import HofAutoBot

class DirectlyChallengeBossState(BaseState):

    def __init__(self, bot: HofAutoBot):
        self.bot = bot
        self.union_id = None
        self.advanced_action_config = None
        self.on_challenge_success = None
        self.on_challenge_failed = None
        self.is_challeged_success = False
    def process(self):
        union_id = self.union_id
        self.log(f"直接挑战boss {union_id}")
        if not self.advanced_action_config:
            self.log(f'未找到动作配置，没有办法处理boss({union_id})，中止处理。')
            self.is_challaged_success = False
        else:
            url = f"{self.bot.server_config_manager.current_server_data['url']}index.php?union={union_id}#"
            self.bot.driver.get(url)
            self.bot.action_manager.execute_advanced_action(self.bot.driver, self.advanced_action_config)
            self.log(f"锤完了，更新一下信息，看打成功没有（有可能被人抢了）")
            self.bot._update_info_from_hunt_page()
            self.is_challaged_success = self.bot.challenge_next_cooldown > 0
        self.on_finish()
    def on_finish(self):
        self.log(f"直接挑战 boss 结束, is_success: {self.is_challaged_success}")
        if self.is_challaged_success:
            if not self.on_challenge_success:
                self.on_challenge_success()
        else:
            if not self.on_challenge_failed:
                self.on_challenge_failed()