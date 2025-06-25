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
            time.sleep(self._idle_time)
        self.on_finish()

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