from functools import partial
from .base_state import BaseState
from datetime import datetime, timedelta
from scripts.hof_auto_bot_main import HofAutoBot
from .state_factory import StateFactory
import time

class WaitVipBossState(BaseState):

    def __init__(self, bot: HofAutoBot):
        super().__init__(bot)
        self.on_challenge_time_up = None
    def process(self):
        """
        等待VIP boss刷新
        走到此状态时说明vip boss距刷新已经在一次boss cd内（20分钟），且已经【无CD体力充沛】
        如果没有等待记录，则走PreareBoss流程
        如果有等待记录，且等待时间已过，清除记录并走Vip流程
        如果有等待记录，但时间还早，则走小怪流程
        如果有等待记录，但时间接近（30秒以内），走vip流程。
        """


        self.log('等待VIP boss状态')
        if not self.bot.is_waiting_for_vip_boss:
            # self.set_state(BossState(self.bot))
            self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        elif self.bot.next_vip_boss_spawn_timestamp <= datetime.now().timestamp() * 1000000:
            # 记录的vip boss时间已过期
            self.bot.reset_waiting_vip_boss_spawn_info()
            self.next_state = StateFactory.create_vip_boss_state(self.bot)
        else:
            diff_time = datetime.fromtimestamp(self.bot.next_vip_boss_spawn_timestamp / 1000000) - datetime.now()
            idle_state = StateFactory.create_idle_state(self.bot)
            diff_seconds = diff_time.total_seconds()
            standard_idle_seconds = self.bot.auto_bot_config_manager.idle_seconds_for_challenge_vip_boss
            if diff_seconds > standard_idle_seconds:
                # 时间还早（大于40秒）
                next_active_time = datetime.now() + timedelta(seconds=standard_idle_seconds)
                self.log("在等vip boss，但时间太久了，干点别的去，省的被踢掉！")
                self.log(f"...但也不能刷太快，等（{next_active_time}）继续行动")
                # 留10秒钟左右
                idle_time = min(standard_idle_seconds - 14, diff_time.total_seconds())
                idle_time = max(idle_time, 0)
                idle_state.set_idle_time(idle_time, partial(self.set_state, state = StateFactory.create_prepare_stage_state(self.bot)))
                self.next_state = idle_state
            elif diff_seconds < 0:
                self.next_state = StateFactory.create_prepare_boss_state(self.bot)
            else:
                # 时间快到了（30秒内）
                after_idle_callback = lambda: {
                    self.set_state(StateFactory.create_wait_vip_boss_state(self.bot)),
                    self._invoke_challenge_time_up()
                }
                idle_state.set_idle_time(diff_seconds, after_idle_callback)
                self.next_state = idle_state
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)

    def _invoke_challenge_time_up(self):
        print("_invoke_challenge_time_up, self = " + self.__class__.__name__)
        if self.on_challenge_time_up is not None and callable(self.on_challenge_time_up):
            print("调用on_challenge_time_up")
            self.on_challenge_time_up()
        else:
            # 刷一下，然后转到vip
            self.set_state(StateFactory.create_vip_boss_state(self.bot))


