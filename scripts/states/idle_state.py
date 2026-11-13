from .base_state import BaseState
from .state_factory import StateFactory
import time

class IdleState(BaseState):

    def __init__(self, bot):
        super().__init__(bot)
        self._idle_time = 0
        self._callback = None
        # self.next_state = None
    def process(self):
        self.log("process: 正在发呆...")
        if self._idle_time > 0:
            self.log(f"即将将发呆{self._idle_time}秒...")
            reason = self._sleep(self._idle_time)
            if reason == 'reload':
                # 配置表刚被重载：不再把旧配置算出来的等待走完，立刻回上层重新决策
                self.log("配置已重载，结束本次发呆，按新配置重新决策")
            elif reason == 'finished':
                return
        self.on_finish()

    def _sleep(self, seconds):
        """分片睡觉，返回提前醒来的原因（''=睡满，'reload'=配置重载，'finished'=退出）。

        原来是一觉睡到底，这期间改了配置表、按了 c 也只能等这一觉睡完
        （最长 20 分钟），看上去就像"重载没生效"。
        """
        epoch = getattr(self.bot, 'config_reload_epoch', 0)
        end = time.monotonic() + seconds
        while True:
            remain = end - time.monotonic()
            if remain <= 0:
                return ''
            if getattr(self.bot, 'is_finished', False):
                return 'finished'
            if getattr(self.bot, 'config_reload_epoch', 0) != epoch:
                return 'reload'
            time.sleep(min(remain, 0.5))

    def on_finish(self):
        if self._callback is not None:
            self.log(f"on_finish -> call_back = {self._callback}")
            self._callback()
        else:
            # 随便给一个状态，用于循环
            self.log("on_finish: 状态切换为: idle_state")
            self.set_state(StateFactory.create_world_pvp_state(self.bot))

    def set_idle_time(self, idle_time, callback = None):
        self._idle_time = idle_time
        self._callback = callback

        self.log(f"设置发呆时间： {self._idle_time}秒, callback = {self._callback}")
