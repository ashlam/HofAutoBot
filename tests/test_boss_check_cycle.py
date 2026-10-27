import os
import sys
import time
import types
from datetime import datetime as _real_datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 真正的 scripts.hof_auto_bot_main 会 import selenium / 拉起浏览器，
# 而各个 state 模块只需要 HofAutoBot 这个类型名，这里用 stub 顶掉
_stub = types.ModuleType("scripts.hof_auto_bot_main")


class _HofAutoBot:
    pass


_stub.HofAutoBot = _HofAutoBot
sys.modules.setdefault("scripts.hof_auto_bot_main", _stub)

import scripts.states.prepare_stage_state as prepare_stage_state_module
import scripts.states.time_limited_stage_state as time_limited_stage_state_module
from scripts.states.directly_challenge_boss_state import DirectlyChallengeBossState
from scripts.states.normal_stage_state import NormalStageState
from scripts.states.prepare_boss_state import PrepareBossState
from scripts.states.prepare_stage_state import PrepareStageState
from scripts.states.time_limited_stage_state import TimeLimitedStageState
from scripts.states.vip_snipe_state import VipSnipeState
from scripts.states.wait_vip_boss_state import WaitVipBossState

VIP_UNION_ID = 17
VIP_ACTION_ID = 600170
NORMAL_STAGE_ACTION_ID = 1
# 每小时最后 10 分钟是限时关卡窗口——恰好是 VIP boss 刷新的前 10 分钟
TIME_LIMITED_START_MINUTE = 50
TIME_LIMITED_END_MINUTE = 59


class _FrozenDateTime(_real_datetime):
    """把 datetime.now() 钉在指定分钟，避免用例依赖真实时钟。"""

    frozen_minute = 55

    @classmethod
    def now(cls, tz=None):
        base = _real_datetime(2026, 10, 27, 16, cls.frozen_minute, 30)
        return base if tz is None else base.replace(tzinfo=tz)


class _FakeLogger:
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            pass

        return _noop


class _FakeActionManager:
    def __init__(self, bot):
        self.bot = bot

    def execute_advanced_action(self, driver, config):
        # 每刷一场小怪扣 100 体力，跟游戏里的消耗对齐
        self.bot.player_stamina -= 100


class _FakeDriver:
    def __init__(self, stage_entry_found=False):
        self.stage_entry_found = stage_entry_found

    def find_elements(self, *args, **kwargs):
        # 限时关卡入口：2服实际不存在（Christmas 没开）；用例里可以打开
        return ['element'] if self.stage_entry_found else []


class _FakeConfig:
    vip_snipe_window_seconds = 120
    idle_seconds_for_challenge_vip_boss = 40
    idle_seconds_for_challenge_boss = 30
    boss_cost_stamina = 10
    normal_stage_loop_order = [{'stage_name': 'ocean1', 'plan_action_id': NORMAL_STAGE_ACTION_ID}]
    keep_stamnia_for_normal_stage = 3000
    keep_stamnia_for_time_limited_stage = 1000
    is_challenge_time_limited_stage = True
    time_limited_stage_need_watch = {
        'stage_name': 'Christmas',
        'plan_action_id': 12,
        'start_minute': TIME_LIMITED_START_MINUTE,
        'end_minute': TIME_LIMITED_END_MINUTE,
    }
    is_challenge_vip_boss = True
    vip_boss_need_watch = [{'union_id': VIP_UNION_ID, 'plan_action_id': VIP_ACTION_ID}]


class _FakeBot:
    def __init__(self, stamina=3600, remain=None, stage_entry_found=False):
        self.logger = _FakeLogger()
        self.auto_bot_config_manager = _FakeConfig()
        self.player_stamina = stamina
        self.challenge_next_cooldown = 0
        self.all_alived_boss_ids = []
        self.is_waiting_for_vip_boss = remain is not None
        self.next_vip_boss_spawn_timestamp = (
            int((time.time() + remain) * 1000000) if remain is not None else -1
        )
        self.next_vip_boss_id = VIP_UNION_ID if remain is not None else -1
        self.hunt_page_updates = 0
        self.current_state = None
        self.current_state_str = ''
        self.driver = _FakeDriver(stage_entry_found)
        self.action_manager = _FakeActionManager(self)
        self.battle_watcher_manager = types.SimpleNamespace(
            get_player_stamina=lambda: self.player_stamina
        )
        self.server_config_manager = types.SimpleNamespace(
            all_action_config_by_server={
                str(NORMAL_STAGE_ACTION_ID): {'actions': []},
                str(VIP_ACTION_ID): {'actions': []},
                '12': {'actions': []},
            }
        )

    def seconds_until_vip_boss_spawn(self):
        if not self.is_waiting_for_vip_boss:
            return None
        if not self.next_vip_boss_spawn_timestamp or self.next_vip_boss_spawn_timestamp <= 0:
            return None
        return self.next_vip_boss_spawn_timestamp / 1000000 - time.time()

    def switch_to_next_state(self, state):
        self.current_state = state
        self.current_state_str = state.__class__.__name__

    def _update_info_from_hunt_page(self):
        self.hunt_page_updates += 1


def _freeze_minute(minute):
    _FrozenDateTime.frozen_minute = minute
    prepare_stage_state_module.datetime = _FrozenDateTime
    time_limited_stage_state_module.datetime = _FrozenDateTime


def _run_until_boss(bot, max_hops=6):
    """从 PrepareStage 起走小怪闭环，看能不能回到 boss 主线。"""
    state = PrepareStageState(bot)
    trail = []
    for _ in range(max_hops):
        state.process()
        trail.append(state.__class__.__name__)
        state = bot.current_state
        if isinstance(state, PrepareBossState):
            return True, trail
        if not isinstance(state, (PrepareStageState, TimeLimitedStageState, NormalStageState)):
            return False, trail
    return False, trail


def test_stage_loop_rechecks_boss_when_stamina_is_plentiful():
    """体力够打小怪时，闭环也必须回到 boss 主线。

    修复前：PrepareStage -> TimeLimited(无入口) -> NormalStage(打了1场) -> PrepareStage，
    小怪一打完就原地转圈，boss 永远不被检查；限时关卡窗口正好覆盖 VIP 刷新前的 10 分钟。
    """
    _freeze_minute(55)
    bot = _FakeBot(stamina=3600)
    reached, trail = _run_until_boss(bot)
    assert reached, f'小怪闭环没有回到 boss 主线，实际路径：{trail}'


def test_stage_loop_rechecks_boss_when_stamina_is_below_stage_threshold():
    """体力低于普通关卡阈值、但够限时关卡（1000）时也必须回到 boss 主线。

    这正是 2服 2026-10-27 16:55~17:00 卡住的形态：一圈 13 秒空转，
    VIP boss 17 已经刷出来了却没人打。
    """
    _freeze_minute(55)
    bot = _FakeBot(stamina=2500)
    reached, trail = _run_until_boss(bot)
    assert reached, f'空转闭环没有回到 boss 主线，实际路径：{trail}'
    assert bot.player_stamina == 2500, '这个形态下一场小怪都不该打出去'


def test_can_afford_boss_with_stage_reserve_stamina_goes_to_boss():
    """体力只够打 boss（2400 < 小怪阈值 3000）、无冷却、boss 在场时，必须立刻去打。

    这是 2026-10-27 16:55 的真实形态：打 boss 只要 10 点体力，2400 完全够，
    机器人却在小怪闭环里空转 5 分钟，VIP boss 17 就站在存活列表里。
    """
    _freeze_minute(55)
    bot = _FakeBot(stamina=2400)
    bot.all_alived_boss_ids = [VIP_UNION_ID]

    trail = []
    state = PrepareStageState(bot)
    for _ in range(6):
        state.process()
        trail.append(state.__class__.__name__)
        state = bot.current_state
        if isinstance(state, DirectlyChallengeBossState):
            break

    assert isinstance(state, DirectlyChallengeBossState), f'应立刻去打 boss，实际路径：{trail}'


def test_time_limited_stage_loop_also_returns_to_boss():
    """限时关卡入口存在时，打完也必须回 boss 主线。

    修复前：PrepareStage -> TimeLimited(打了) -> PrepareStage -> TimeLimited ...，
    两个状态之间死循环，boss 一次都不看（体力、冷却都不是理由）。
    """
    _freeze_minute(55)
    bot = _FakeBot(stamina=3600, stage_entry_found=True)
    reached, trail = _run_until_boss(bot)
    assert reached, f'限时关卡闭环没有回到 boss 主线，实际路径：{trail}'
    assert bot.player_stamina == 3500, f'这一轮应当打了一场限时关卡，体力 {bot.player_stamina}'


def test_vip_wait_record_survives_stage_loop_and_hands_over_to_snipe():
    """已进入狙击窗口时，从刷小怪入口一路交棒到狙击状态。"""
    _freeze_minute(55)
    bot = _FakeBot(stamina=3600, remain=100)

    PrepareStageState(bot).process()
    assert isinstance(bot.current_state, PrepareBossState), \
        f'应回到 boss 主线，实际 {type(bot.current_state).__name__}'

    bot.current_state.process()
    assert isinstance(bot.current_state, WaitVipBossState), \
        f'有等待记录就该交给等待状态，实际 {type(bot.current_state).__name__}'

    bot.current_state.process()
    assert isinstance(bot.current_state, VipSnipeState), \
        f'进入 120 秒窗口就该交给狙击状态，实际 {type(bot.current_state).__name__}'


def test_wait_state_keeps_record_while_farming_before_window():
    """离刷新还早时允许去刷小怪，但不能把等待记录弄丢。"""
    _freeze_minute(40)
    bot = _FakeBot(stamina=3600, remain=600)

    WaitVipBossState(bot).process()
    assert bot.is_waiting_for_vip_boss, '等待记录不能被随手清掉'
    assert bot.current_state is not None
