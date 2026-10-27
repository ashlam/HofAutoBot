import sys
import os
import time
import types

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 真正的 scripts.hof_auto_bot_main 会 import selenium / 拉起浏览器，
# 而 state 模块只需要 HofAutoBot 这个类型名，这里用 stub 顶掉
_stub = types.ModuleType("scripts.hof_auto_bot_main")


class _HofAutoBot:
    pass


_stub.HofAutoBot = _HofAutoBot
sys.modules["scripts.hof_auto_bot_main"] = _stub

from scripts.states.vip_snipe_state import VipSnipeState

CHAR_IDS = ['char_1', 'char_2', 'char_3', 'char_4', 'char_5']
ACTION_CONFIG = {
    'name': '一服旋风',
    'actions': (
        [{'trigger_type': 'click_button_clear_team', 'value': 'checkDelAll()'}]
        + [{'trigger_type': 'check_box_select_character', 'value': c} for c in CHAR_IDS]
        + [{'trigger_type': 'click_button_start_battle', 'value': 'union_battle'}]
    ),
}


class _FakeLogger:
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
    """只模拟 VipSnipeState 用到的三个动作：get / readyState / 两段脚本。"""

    def __init__(self, has_button=True, can_select=True):
        self.has_button = has_button
        self.can_select = can_select
        self.get_calls = []
        self.warmup_calls = 0
        self.fire_calls = []
        self.current_url = 'https://example.com/hall/'

    def get(self, url):
        self.get_calls.append((time.time(), url))
        self.current_url = url

    def execute_script(self, script, *args):
        if 'document.readyState' in script:
            return 'complete'
        if 'has_form' in script:
            self.warmup_calls += 1
            return {
                'selected': len(args[0]) if self.can_select else 0,
                'expected': len(args[0]),
                'missing': 0 if self.can_select else len(args[0]),
                'has_battle_button': self.has_button,
                'has_form': True,
            }
        self.fire_calls.append(time.time())
        # 页面上有按钮 -> click；没有按钮 -> 就地重建表单 submit
        return 'clicked' if self.has_button else 'submitted'


class _FakeBot:
    def __init__(self, driver, spawn_in=0.3):
        self.logger = _FakeLogger()
        self.auto_bot_config_manager = _FakeConfig()
        self.driver = driver
        self.server_config_manager = types.SimpleNamespace(
            current_server_data={'url': 'https://example.com/hall/'}
        )
        self.challenge_next_cooldown = 0
        self.is_waiting_for_vip_boss = True
        self.next_vip_boss_id = 17
        self.next_vip_boss_spawn_timestamp = int((time.time() + spawn_in) * 1000000)
        self.vip_snipe_last_fire_ts = 0.0
        self.current_state = None
        self.hunt_page_updates = 0

    def _update_info_from_hunt_page(self):
        self.hunt_page_updates += 1

    def reset_waiting_vip_boss_spawn_info(self):
        self.is_waiting_for_vip_boss = False
        self.next_vip_boss_spawn_timestamp = -1

    def switch_to_next_state(self, state):
        self.current_state = state


def _make(has_button=True, can_select=True, spawn_in=0.3):
    driver = _FakeDriver(has_button=has_button, can_select=can_select)
    bot = _FakeBot(driver, spawn_in=spawn_in)
    spawn_ts = bot.next_vip_boss_spawn_timestamp
    state = VipSnipeState(bot, 17, ACTION_CONFIG, spawn_ts)
    return bot, driver, state, spawn_ts / 1000000.0


def test_warmup_happens_before_spawn_and_only_one_submit():
    """页面加载/选人必须在 T 之前完成，T 之后只允许一次提交。"""
    bot, driver, state, target = _make()

    state.process()

    assert driver.warmup_calls == 1, '预热应当只做一次'
    assert len(driver.fire_calls) == 1, f'T 之后只允许提交一次，实际 {len(driver.fire_calls)} 次'
    assert len(driver.get_calls) == 1, f'页面只应加载一次（预热那次），实际 {len(driver.get_calls)} 次'

    warm_ts = driver.get_calls[0][0]
    assert warm_ts < target - 0.03, f'页面加载必须早于 T，实际 {warm_ts - target:+.3f}s'
    assert abs(driver.fire_calls[0] - target) < 0.15, \
        f'提交应当压在 T 上，实际偏差 {driver.fire_calls[0] - target:+.3f}s'


def test_form_submit_url_points_at_the_vip_boss():
    """预热打开的就是这个 boss 的挑战页，不能打开列表页。"""
    bot, driver, state, _ = _make()
    state.process()
    assert 'union=17' in driver.get_calls[0][1]


def test_missing_battle_button_reuses_same_page_instead_of_reloading():
    """T 之前 boss 还没刷出来、页面上没有开战按钮时：

    不能在 T 之后重新加载一次页面（那要多花一整次页面加载），
    而是就地复用同一个队伍表单提交 —— 页面只加载一次。
    """
    bot, driver, state, target = _make(has_button=False)

    state.process()

    assert len(driver.get_calls) == 1, f'页面只应加载一次（预热），实际 {len(driver.get_calls)} 次'
    assert len(driver.fire_calls) == 1, f'T 之后只允许提交一次，实际 {len(driver.fire_calls)} 次'
    assert state._fire_result == 'submitted', f'应走重建表单提交，实际 {state._fire_result}'
    assert abs(driver.fire_calls[0] - target) < 0.15, \
        f'提交应当压在 T 上，实际偏差 {driver.fire_calls[0] - target:+.3f}s'


def test_warmup_failure_falls_back_to_exactly_one_blind_shot():
    """连队伍表单都勾不上（预热彻底失败）时，到点重载一次并打一下，仅此一次。"""
    bot, driver, state, _ = _make(can_select=False)

    state.process()

    assert len(driver.get_calls) == 2, f'应为"预热一次 + 到点重载一次"，实际 {len(driver.get_calls)} 次'
    assert len(driver.fire_calls) == 1, f'盲试只允许一次，实际 {len(driver.fire_calls)} 次'


def test_success_marks_fire_timestamp_and_clears_waiting_record():
    """出手后要留痕（防止同一轮再打一次），并清掉本轮等待记录。"""
    bot, driver, state, _ = _make()
    bot.challenge_next_cooldown = 0  # 先按"没有冷却"走，靠脚本返回 clicked 判定成功

    state.process()

    assert bot.vip_snipe_last_fire_ts > 0, '必须记录出手时刻，避免同一轮重复请求'
    assert bot.is_waiting_for_vip_boss is False
    assert bot.hunt_page_updates == 1, '出手后要刷新一次页面确认结果'


def test_cooldown_wins_over_script_result():
    """脚本返回成功但服务端没给冷却时，以服务端为准（被抢了就是没打成）。"""
    driver = _FakeDriver(has_button=True)
    bot = _FakeBot(driver)
    state = VipSnipeState(bot, 17, ACTION_CONFIG, bot.next_vip_boss_spawn_timestamp)
    bot.challenge_next_cooldown = 0

    state.process()

    # 失败分支应当回到"准备打 boss"，而不是直接去刷别的
    assert bot.current_state is not None
    assert type(bot.current_state).__name__ == 'PrepareBossState', \
        f'没打成应回到 PrepareBossState，实际 {type(bot.current_state).__name__}'


def test_missing_config_does_not_touch_browser():
    """没有 boss 配置时不应发起任何请求。"""
    driver = _FakeDriver()
    bot = _FakeBot(driver)
    state = VipSnipeState(bot, None, None, bot.next_vip_boss_spawn_timestamp)

    state.process()

    assert driver.get_calls == []
    assert driver.fire_calls == []


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f'  ok  {name}')
    print("测试通过！")
