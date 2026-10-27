from functools import partial
from .base_state import BaseState
from scripts.hof_auto_bot_main import HofAutoBot
from .state_factory import StateFactory

class DirectlyChallengeBossState(BaseState):

    def __init__(self, bot: HofAutoBot):
        super().__init__(bot)
        # self.bot = bot
        self.union_id = None
        self.advanced_action_config = None
        self.on_challenge_success = None
        self.on_challenge_failed = None
        self.is_challeged_success = False
        # self.next_state = None
    def process(self):
        union_id = self.union_id
        self.log(f"直接挑战boss {union_id}")
        if not self.advanced_action_config:
            self.log(f'未找到动作配置，没有办法处理boss({union_id})，中止处理。')
            self.is_challaged_success = False
        else:
            # 这里是全工程第二个（也是最后一个）真正发出挑战请求的地方。
            # 服务器对同一只 boss 的两次请求都会按合法处理并公示结果，
            # 所以动手之前必须先过闸门：近期已经发过就绝不再发。
            if not self._claim_shot():
                wait_seconds = self._guard_wait_seconds()
                self.log(f'【闸门】boss({union_id}) 近期已发过挑战请求，'
                         f'此次不再发送，{wait_seconds:.0f}秒后再走常规流程')
                self.is_challaged_success = False
                idle_state = StateFactory.create_idle_state(self.bot)
                idle_state.set_idle_time(
                    wait_seconds,
                    partial(self.set_state, StateFactory.create_prepare_boss_state(self.bot)),
                )
                self.set_state(idle_state)
                return
            url = f"{self.bot.server_config_manager.current_server_data['url']}index.php?union={union_id}#"
            # 检查当前URL是否与目标URL相同，如果相同则刷新页面，否则导航到目标URL
            current_url = self.bot.driver.current_url
            if current_url == url or (f"union={union_id}" in current_url):
                self.bot.driver.refresh()
            else:
                self.bot.driver.get(url)
            self.bot.action_manager.execute_advanced_action(self.bot.driver, self.advanced_action_config)
            self.log(f"锤完了，更新一下信息，看打成功没有（有可能被人抢了）")
            self.bot._update_info_from_hunt_page()
            self.is_challaged_success = self.bot.challenge_next_cooldown > 0
            self._record_shot_result(self.is_challaged_success)
        self.on_finish()

    def _claim_shot(self) -> bool:
        guard = getattr(self.bot, 'boss_challenge_guard', None)
        if guard is None:
            return True
        try:
            return bool(guard.claim(self.union_id, None, 'directly_challenge'))
        except Exception as e:
            # 闸门自己出问题时宁可不出手，也不冒"发两次"的风险
            self.log(f'【闸门】异常（{type(e).__name__}: {e}），放弃本次挑战')
            return False

    def _guard_wait_seconds(self) -> float:
        guard = getattr(self.bot, 'boss_challenge_guard', None)
        remain = 0.0
        if guard is not None:
            try:
                remain = float(guard.seconds_until_allowed(self.union_id) or 0)
            except Exception:
                remain = 0.0
        return max(30.0, min(remain, 600.0))

    def _record_shot_result(self, accepted: bool):
        guard = getattr(self.bot, 'boss_challenge_guard', None)
        if guard is None:
            return
        try:
            guard.record_result(self.union_id, accepted)
        except Exception:
            pass
    def on_finish(self):
        self.log(f"直接挑战 boss 结束, is_success: {self.is_challaged_success}")
        if self.is_challaged_success:
            if self.on_challenge_success is not None and callable(self.on_challenge_success):
                print(f'self.on_challenge_success = {self.on_challenge_success.__name__}')
                self.on_challenge_success()
            else:
                self.log(f"直接挑战 boss 成功，没有设置on_challenge_success，默认跳到world pvp好了。")
                self.set_state(StateFactory.create_world_pvp_state(self.bot))
        else:
            if self.on_challenge_failed is not None and callable(self.on_challenge_failed):
                print(f'self.on_challenge_failed = {self.on_challenge_failed.__name__}')
                self.on_challenge_failed()
            else:
                self.set_state(StateFactory.create_world_pvp_state(self.bot))

