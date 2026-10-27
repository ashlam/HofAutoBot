import os
import sys
import tempfile
import time
import types

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_stub = types.ModuleType("scripts.hof_auto_bot_main")


class _HofAutoBot:
    pass


_stub.HofAutoBot = _HofAutoBot
sys.modules["scripts.hof_auto_bot_main"] = _stub

from scripts.boss_challenge_guard import BossChallengeGuard
from scripts.states.vip_snipe_state import VipSnipeState


def _tmp_path():
    handle, path = tempfile.mkstemp(suffix='.json')
    os.close(handle)
    os.unlink(path)
    return path


def _guard(min_interval=600.0, path=None):
    return BossChallengeGuard(
        state_path=path or _tmp_path(),
        min_interval_provider=lambda: min_interval,
    )


def test_second_shot_on_same_boss_is_refused():
    """同一只 boss 紧接着再打一次，必须被拒。"""
    guard = _guard()
    assert guard.claim(17, 1700000000000000, 'vip_snipe') is True
    assert guard.claim(17, 1700000000000000, 'directly_challenge') is False
    assert guard.claim(17, None, 'directly_challenge') is False


def test_same_spawn_epoch_is_refused_even_after_interval():
    """同一轮刷新（spawn 时间戳相同）不论隔多久都只允许出手一次。"""
    guard = _guard(min_interval=0.01)
    spawn = 1700000000000000
    assert guard.claim(17, spawn) is True
    time.sleep(0.03)
    assert guard.claim(17, spawn) is False, '同一轮刷新不允许第二次出手'
    assert guard.claim(17, spawn + 14400 * 1000000) is True, '下一轮刷新应放行'


def test_different_boss_is_not_blocked():
    guard = _guard()
    assert guard.claim(17, None) is True
    assert guard.claim(18, None) is True


def test_release_allows_retry_when_nothing_was_sent():
    """许可拿到了但请求其实没发出去，要能把许可还回来。"""
    guard = _guard()
    assert guard.claim(17, 123) is True
    assert guard.claim(17, 123) is False
    guard.release(17, 123)
    assert guard.claim(17, 123) is True


def test_record_survives_restart():
    """进程重启后仍然记得刚打过，否则重启就是最典型的重复出手场景。"""
    path = _tmp_path()
    first = _guard(path=path)
    assert first.claim(17, 123) is True

    second = _guard(path=path)
    assert second.claim(17, 123) is False
    assert second.last_fire_age(17) is not None


def test_seconds_until_allowed_reports_wait():
    guard = _guard(min_interval=600)
    assert guard.seconds_until_allowed(17) == 0.0
    guard.claim(17, None)
    assert 590 < guard.seconds_until_allowed(17) <= 600


class _NoopLogger:
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            pass

        return _noop


class _FakeConfig:
    vip_snipe_warmup_lead_seconds = 0.05
    vip_snipe_fire_cost_seconds = 0.02
    vip_snipe_commit_offset_ms = 0
    vip_snipe_settle_seconds = 0


class _FakeDriver:
    def __init__(self):
        self.get_calls = []
        self.fire_calls = []

    def get(self, url):
        self.get_calls.append(url)

    def execute_script(self, script, *args):
        if 'document.readyState' in script:
            return 'complete'
        if 'has_form' in script:
            return {
                'selected': len(args[0]),
                'expected': len(args[0]),
                'missing': 0,
                'has_battle_button': True,
                'has_form': True,
            }
        self.fire_calls.append(time.time())
        return 'clicked'


class _FakeBot:
    def __init__(self, driver, guard):
        self.logger = _NoopLogger()
        self.auto_bot_config_manager = _FakeConfig()
        self.driver = driver
        self.server_config_manager = types.SimpleNamespace(
            current_server_data={'url': 'https://example.com/hall/'}
        )
        self.boss_challenge_guard = guard
        self.challenge_next_cooldown = 0
        self.is_waiting_for_vip_boss = True
        self.vip_snipe_last_fire_ts = 0.0
        self.current_state = None

    def _update_info_from_hunt_page(self):
        pass

    def reset_waiting_vip_boss_spawn_info(self):
        self.is_waiting_for_vip_boss = False

    def switch_to_next_state(self, state):
        self.current_state = state


ACTION_CONFIG = {
    'name': '一服旋风',
    'actions': (
        [{'trigger_type': 'click_button_clear_team', 'value': 'checkDelAll()'}]
        + [{'trigger_type': 'check_box_select_character', 'value': f'char_{i}'}
           for i in range(1, 6)]
        + [{'trigger_type': 'click_button_start_battle', 'value': 'union_battle'}]
    ),
}


def test_snipe_never_fires_twice_even_when_replayed():
    """同一个刷新时刻，狙击状态被重复执行也不会发出第二个请求。"""
    driver = _FakeDriver()
    guard = _guard()
    bot = _FakeBot(driver, guard)
    spawn_ts = int((time.time() + 0.2) * 1000000)

    VipSnipeState(bot, 17, ACTION_CONFIG, spawn_ts).process()
    VipSnipeState(bot, 17, ACTION_CONFIG, spawn_ts).process()

    assert len(driver.fire_calls) == 1, f'同一轮刷新只允许一次请求，实际 {len(driver.fire_calls)} 次'


def test_snipe_does_not_fire_when_guard_errors():
    """闸门自身异常时宁可不出手，也不能冒重复请求的风险。"""

    class _BrokenGuard:
        def claim(self, *args, **kwargs):
            raise RuntimeError('state file is read-only')

    driver = _FakeDriver()
    bot = _FakeBot(driver, _BrokenGuard())
    state = VipSnipeState(bot, 17, ACTION_CONFIG, int((time.time() + 0.1) * 1000000))

    state.process()

    assert driver.fire_calls == [], '闸门异常时必须放弃出手'
    assert state._fire_result == 'blocked'


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f'  ok  {name}')
    print("测试通过！")
