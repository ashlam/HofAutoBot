from .base_state import BaseState
from datetime import datetime
from .state_factory import StateFactory

class PrepareStageState(BaseState):
    def process(self):
        """处理小怪stage战斗逻辑git 
        Returns:
            str: 下一个游戏状态
        """
        self.log('开始处理小怪战斗')
        # 刷一下战斗界面，看看剩余体力
        self.bot._update_info_from_hunt_page()
        player_stamina = self.bot.battle_watcher_manager.get_player_stamina()
        current_minute = datetime.now().minute
        in_time_limited_stage = False
        if self.bot.auto_bot_config_manager.is_challenge_time_limited_stage and self.bot.auto_bot_config_manager.time_limited_stage_need_watch:
            start_minute = self.bot.auto_bot_config_manager.time_limited_stage_need_watch['start_minute']
            end_minute = self.bot.auto_bot_config_manager.time_limited_stage_need_watch['end_minute']
            in_time_limited_stage = start_minute <= current_minute <= end_minute
        threshold = self.bot.auto_bot_config_manager.keep_stamnia_for_time_limited_stage if in_time_limited_stage else self.bot.auto_bot_config_manager.keep_stamnia_for_normal_stage
        if player_stamina < threshold:
            self.log(f'体力不足以打小怪，去看看boss...')
            self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        else:
            if in_time_limited_stage:
                self.log('当前时间在限时阶段')
                self.next_state = StateFactory.create_time_limited_stage_state(self.bot)
            else:
                self.next_state = StateFactory.create_normal_stage_state(self.bot)
        self.on_finish()

    def on_finish(self):
        """准备挑战boss的逻辑
            正常走到这里应该是体力充沛且无冷却的状态
        """
        self.set_state(self.next_state)
