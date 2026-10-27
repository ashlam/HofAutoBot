from functools import partial
from .base_state import BaseState
from datetime import datetime, timedelta
from scripts.hof_auto_bot_main import HofAutoBot
from .state_factory import StateFactory
import time

# 刷新时刻过了这么久还没出手，就认为这条等待记录已经失效（不再补打）
SNIPE_GRACE_SECONDS = 60

class WaitVipBossState(BaseState):

    def __init__(self, bot: HofAutoBot):
        super().__init__(bot)
        self.on_challenge_time_up = None
    def process(self):
        """
        等待VIP boss刷新
        走到此状态时说明vip boss距刷新已经在一次boss cd内（20分钟），且已经【无CD体力充沛】
        如果没有等待记录，则走PreareBoss流程
        如果离刷新还很远，则交出控制权去刷小怪
        如果进入狙击窗口，交给 VipSnipeState：先预热页面和队伍，刷新那一刻只点一次提交
        """

        self.log('等待VIP boss状态')
        if not self.bot.is_waiting_for_vip_boss:
            self.next_state = StateFactory.create_prepare_boss_state(self.bot)
            self.on_finish()
            return

        remain = self._seconds_until_spawn()
        if remain is None:
            self.next_state = StateFactory.create_prepare_boss_state(self.bot)
            self.on_finish()
            return

        standard_idle_seconds = self.bot.auto_bot_config_manager.idle_seconds_for_challenge_vip_boss
        # 狙击窗口：越接近刷新，越不能再把控制权交出去（刷小怪一批就可能跨过刷新时刻）
        snipe_window = max(standard_idle_seconds, self.bot.auto_bot_config_manager.vip_snipe_window_seconds)

        # 这一轮已经打过，或者刷新时刻已过去太久：作废等待记录，回到常规流程
        if self._already_fired() or remain < -SNIPE_GRACE_SECONDS:
            self.log(f'VIP等待记录失效（距离刷新 {remain:.0f} 秒），回到boss常规流程')
            self.bot.reset_waiting_vip_boss_spawn_info()
            self.next_state = StateFactory.create_prepare_boss_state(self.bot)
            self.on_finish()
            return

        if remain > snipe_window:
            # 时间还早（大于狙击窗口）
            next_active_time = datetime.now() + timedelta(seconds=standard_idle_seconds)
            self.log(f"在等vip boss，还有{remain:.0f}秒才刷新，先干点别的去，省的被踢掉！")
            self.log(f"...但也不能刷太快，等（{next_active_time}）继续行动")
            idle_state = StateFactory.create_idle_state(self.bot)
            # 留14秒左右
            idle_time = max(min(standard_idle_seconds - 14, remain), 0)
            idle_state.set_idle_time(idle_time, partial(self.set_state, state = StateFactory.create_prepare_stage_state(self.bot)))
            self.next_state = idle_state
        else:
            # 进入狙击窗口：交给 VipSnipeState —— 它会把页面加载、清队、勾人这些
            # "慢动作"全部放到刷新之前，到点只点一次提交
            snipe_state = self._create_snipe_state()
            if snipe_state is not None:
                self.log(f'进入狙击窗口，距离vip boss刷新还有{remain:.1f}秒，交给狙击状态')
                self.next_state = snipe_state
            elif remain > 0:
                # 兜底：拿不到 boss 配置就只精确睡到刷新时刻
                self.log(f'进入狙击窗口，但拿不到boss配置，精确等待{remain:.1f}秒')
                idle_state = StateFactory.create_idle_state(self.bot)
                idle_state.set_idle_time(remain, self._invoke_challenge_time_up)
                self.next_state = idle_state
            else:
                self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)

    # ------------------------------------------------------------------ 辅助

    def _seconds_until_spawn(self):
        checker = getattr(self.bot, 'seconds_until_vip_boss_spawn', None)
        if callable(checker):
            return checker()
        timestamp = getattr(self.bot, 'next_vip_boss_spawn_timestamp', 0) or 0
        if timestamp <= 0:
            return None
        return timestamp / 1000000 - time.time()

    def _already_fired(self) -> bool:
        checker = getattr(self.bot, 'vip_snipe_already_fired_recently', None)
        return bool(checker()) if callable(checker) else False

    def _create_snipe_state(self):
        """按当前等待记录构造狙击状态；拿不到配置时返回 None，由调用方兜底。"""
        union_id = getattr(self.bot, 'next_vip_boss_id', None)
        spawn_ts = getattr(self.bot, 'next_vip_boss_spawn_timestamp', 0) or 0
        if not union_id or spawn_ts <= 0:
            return None
        try:
            watch_list = self.bot.auto_bot_config_manager.vip_boss_need_watch
            all_configs = self.bot.server_config_manager.all_action_config_by_server
        except AttributeError:
            return None
        for item in watch_list or []:
            if item.get('union_id') != union_id:
                continue
            action_config = all_configs.get(f"{item.get('plan_action_id')}")
            if not action_config:
                return None
            return StateFactory.create_vip_snipe_state(
                self.bot, union_id, action_config, spawn_ts
            )
        return None

    def _invoke_challenge_time_up(self):
        print("_invoke_challenge_time_up, self = " + self.__class__.__name__)
        if self.on_challenge_time_up is not None and callable(self.on_challenge_time_up):
            print("调用on_challenge_time_up")
            self.on_challenge_time_up()
        else:
            # 刷一下，然后转到vip
            self.set_state(StateFactory.create_vip_boss_state(self.bot))
