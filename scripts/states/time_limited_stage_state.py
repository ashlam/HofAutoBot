from datetime import datetime
from .base_state import BaseState
from .state_factory import StateFactory

class TimeLimitedStageState(BaseState):
    def process(self):
        self.log('开始处理限时关卡')
        
        # 获取当前时间的分钟数
        current_minute = datetime.now().minute
        
        # 检查是否配置了限时关卡监控和是否允许挑战
        if not (self.bot.auto_bot_config_manager.is_challenge_time_limited_stage and 
                self.bot.auto_bot_config_manager.time_limited_stage_need_watch):
            self.log('未配置限时关卡监控或未启用限时关卡挑战')
            self.next_state = StateFactory.create_prepare_boss_state(self.bot)
            self.on_finish()
            return
            
        # 遍历需要监控的限时关卡
        stage = self.bot.auto_bot_config_manager.time_limited_stage_need_watch
        start_minute = stage.get('start_minute', 50)
        end_minute = stage.get('end_minute', 59)
        
        # 检查当前时间是否在指定的时间范围内
        if start_minute <= current_minute <= end_minute:
            self.log(f'当前时间在VIP关卡开放时间范围内 ({start_minute}-{end_minute}分)')
            
            # 获取关卡动作配置
            plan_action_id = stage.get('plan_action_id')
            if not plan_action_id:
                self.log(f'未找到关卡 {stage.get("stage_name")} 的动作配置')
                self.next_state = StateFactory.create_normal_stage_state(self.bot)
            else:   
                advanced_action_config = self.bot.server_config_manager.all_action_config_by_server.get(str(plan_action_id))
                if not advanced_action_config:
                    self.log(f'未找到关卡 {stage.get("stage_name")} 的高级动作配置')
                    self.next_state = StateFactory.create_normal_stage_state(self.bot)
                else:    
                    # 执行VIP关卡动作
                    self.log(f'开始执行VIP关卡 {stage.get("stage_name")} 的动作')
                    self.bot.action_manager.execute_advanced_action(self.bot.driver, advanced_action_config)
                    self.next_state = StateFactory.create_prepare_stage_state(self.bot)
        else:
            self.log(f'当前时间不在VIP关卡开放时间范围内 ({start_minute}-{end_minute}分)')
            self.next_state = StateFactory.create_normal_stage_state(self.bot)
        
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)