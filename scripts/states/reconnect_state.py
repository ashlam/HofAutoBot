from functools import partial
from .base_state import BaseState
from .state_factory import StateFactory
import time

class ReconnectState(BaseState):
    def process(self):
        self.log('进入断线重连状态')
        if not self.bot._is_on_login_page():
            self.set_state(StateFactory.create_prepare_boss_state(self.bot))
            return
        ok = self.bot._auto_login()
        if ok:
            self.log('重新登录成功，恢复流程')
            self.set_state(StateFactory.create_update_character_state(self.bot))
            return
        idle_state = StateFactory.create_idle_state(self.bot)
        idle_state.set_idle_time(5, partial(self.set_state, state=StateFactory.create_reconnect_state(self.bot)))
        self.set_state(idle_state)
