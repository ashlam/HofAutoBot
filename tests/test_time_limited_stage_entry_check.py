import sys
import os
import types

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 屏蔽 advanced_action_executor 的 import 期副作用（已修复，但保持测试独立）
_stub = types.ModuleType("scripts.hof_auto_bot_main")
class _HofAutoBot:
    pass
_stub.HofAutoBot = _HofAutoBot
sys.modules["scripts.hof_auto_bot_main"] = _stub

from scripts.states.time_limited_stage_state import TimeLimitedStageState
import scripts.states.time_limited_stage_state as tls_module


class _FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, msg):
        self.messages.append(msg)

    def error(self, msg):
        self.messages.append(msg)

    def success(self, msg):
        self.messages.append(msg)

    def warning(self, msg):
        self.messages.append(msg)

    def debug(self, msg):
        self.messages.append(msg)


class _FakeConfigManager:
    def __init__(self, stage_cfg):
        self.time_limited_stage_need_watch = stage_cfg
        self.is_challenge_time_limited_stage = True


class _FakeDriver:
    """记录查找过的 xpath，按配置返回元素"""

    def __init__(self, found):
        self.found = found
        self.queried = []

    def find_elements(self, by, xpath):
        self.queried.append(xpath)
        return ['element'] if self.found else []


class _FakeActionManager:
    def __init__(self):
        self.executed = []

    def execute_advanced_action(self, driver, config):
        self.executed.append(config)


class _FakeBot:
    def __init__(self, stage_cfg, found):
        self.logger = _FakeLogger()
        self.auto_bot_config_manager = _FakeConfigManager(stage_cfg)
        self.driver = _FakeDriver(found)
        self.action_manager = _FakeActionManager()
        self.server_config_manager = types.SimpleNamespace(
            all_action_config_by_server={'12': {'name': '限时圣诞关卡', 'actions': []}}
        )
        self.next_state_name = None

    def _capture_state(self, state):
        """捕获 set_state 被调用时传入的状态名"""
        def _set_state(s):
            self.next_state_name = s.__class__.__name__
        state.set_state = _set_state


# 配置里只有 stage_name（没有 state_name），与真实 auto_bot_loop_config.json 一致
STAGE_CFG = {
    'stage_name': 'Christmas',
    'plan_action_id': 12,
    'start_minute': 50,
    'end_minute': 59,
    'description': '每小时最后10分钟内触发',
}


import contextlib
import datetime as _datetime


@contextlib.contextmanager
def _frozen_minute(minute):
    """把模块里的 datetime.now() 冻结到指定分钟，使限时关卡窗口判断稳定"""
    real_datetime = tls_module.datetime

    class _FrozenDatetime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            base = real_datetime.now(tz)
            return base.replace(minute=minute, second=0, microsecond=0)

    tls_module.datetime = _FrozenDatetime
    try:
        yield
    finally:
        tls_module.datetime = real_datetime


def _run(found):
    bot = _FakeBot(dict(STAGE_CFG), found)
    state = TimeLimitedStageState(bot)
    bot._capture_state(state)
    # 限时关卡只在配置的分钟窗口内触发，冻结时间到窗口内
    with _frozen_minute(55):
        state.process()
    return bot, state


def test_checks_stage_entry_using_stage_name():
    """回归测试：应使用配置里的 stage_name 去检查关卡入口是否存在。

    背景：代码读的是 stage.get('state_name')，而真实配置里根本没有
    state_name 字段（只有 stage_name），导致恒为 None，
    「当前页面未找到关卡入口」的前置检查形同虚设 —— 关卡没开放时
    也会照常执行动作，白白消耗体力。
    """
    bot, state = _run(found=False)

    assert bot.driver.queried, "应检查页面上是否存在关卡入口"
    xpath = bot.driver.queried[0]
    assert 'common=Christmas' in xpath, f"应使用 stage_name 构造入口标识，实际: {xpath}"
    assert bot.action_manager.executed == [], "关卡入口不存在时不应执行动作"
    assert any('未找到关卡入口' in m for m in bot.logger.messages), \
        f"应记录未找到入口的日志，实际: {bot.logger.messages}"


def test_executes_when_stage_entry_present():
    """关卡入口存在时应正常执行动作"""
    bot, state = _run(found=True)

    assert bot.action_manager.executed, "关卡入口存在时应执行动作"
    assert any('检测到关卡入口' in m for m in bot.logger.messages), \
        f"应记录检测到入口的日志，实际: {bot.logger.messages}"


def test_explicit_state_name_takes_precedence():
    """若配置里显式提供了 state_name，应优先使用它"""
    cfg = dict(STAGE_CFG)
    cfg['state_name'] = 'Asianata'
    bot = _FakeBot(cfg, found=True)
    state = TimeLimitedStageState(bot)
    bot._capture_state(state)
    with _frozen_minute(55):
        state.process()

    xpath = bot.driver.queried[0]
    assert 'common=Asianata' in xpath, f"显式 state_name 应优先，实际: {xpath}"


if __name__ == "__main__":
    test_checks_stage_entry_using_stage_name()
    test_executes_when_stage_entry_present()
    test_explicit_state_name_takes_precedence()
    print("全部测试通过！")
