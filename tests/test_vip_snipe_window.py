import sys
import os
import time
import types

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 真正的 scripts.hof_auto_bot_main 会 import selenium / 拉起浏览器，
# 而各个 state 模块只需要 HofAutoBot 这个类型名，这里用 stub 顶掉
_stub = types.ModuleType("scripts.hof_auto_bot_main")


class _HofAutoBot:
    pass


_stub.HofAutoBot = _HofAutoBot
sys.modules["scripts.hof_auto_bot_main"] = _stub

from scripts.states.idle_state import IdleState
from scripts.states.normal_stage_state import NormalStageState
from scripts.states.prepare_boss_state import PrepareBossState
from scripts.states.prepare_stage_state import PrepareStageState
from scripts.states.wait_vip_boss_state import WaitVipBossState

SNIPE_WINDOW = 120


class _FakeLogger:
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            pass

        return _noop


class _FakeConfig:
    vip_snipe_window_seconds = SNIPE_WINDOW
    idle_seconds_for_challenge_vip_boss = 40
    idle_seconds_for_challenge_boss = 30
    boss_cost_stamina = 10
    normal_stage_loop_order = [{'stage_name': 'ocean1', 'plan_action_id': 1}]
    keep_stamnia_for_normal_stage = 3000
    is_challenge_time_limited_stage = False
    keep_stamnia_for_time_limited_stage = 1000
    time_limited_stage_need_watch = None


class _FakeBot:
    def __init__(self, remain=None):
        self.logger = _FakeLogger()
        self.auto_bot_config_manager = _FakeConfig()
        self.current_state = None
        self.current_state_str = ''
        self.player_stamina = 4000
        self.challenge_next_cooldown = 0
        self.is_waiting_for_vip_boss = remain is not None
        self.next_vip_boss_spawn_timestamp = (
            int((time.time() + remain) * 1000000) if remain is not None else -1
        )
        self.hunt_page_updates = 0
        self.battle_watcher_manager = types.SimpleNamespace(
            get_player_stamina=lambda: self.player_stamina
        )

    # 与被测代码用的真实接口保持一致
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


def _run(state):
    state.process()
    return state.bot.current_state


def test_prepare_stage_bails_out_inside_snipe_window():
    """刷新前 120 秒内，刷小怪必须先收手，且不能再去刷 hunt 页浪费时间。"""
    bot = _FakeBot(remain=60)
    next_state = _run(PrepareStageState(bot))
    assert isinstance(next_state, PrepareBossState), f'应收手去守刷新，实际跳到 {type(next_state).__name__}'
    assert bot.hunt_page_updates == 0, '收手分支不应再多刷一次 hunt 页'


def test_prepare_stage_keeps_farming_outside_snipe_window():
    """离刷新还早时，仍然照常去刷小怪。"""
    bot = _FakeBot(remain=SNIPE_WINDOW + 300)
    next_state = _run(PrepareStageState(bot))
    assert not isinstance(next_state, PrepareBossState), '离刷新还早，不该去守刷新'
    assert bot.hunt_page_updates == 1, '正常流程应先刷一次 hunt 页确认体力'


def test_normal_stage_interrupts_batch_inside_snipe_window():
    """一批小怪刷到一半，一旦进入狙击窗口也必须立刻中断。"""
    bot = _FakeBot(remain=60)
    next_state = _run(NormalStageState(bot))
    assert isinstance(next_state, PrepareBossState), f'应中断本批小怪，实际跳到 {type(next_state).__name__}'
    assert bot.hunt_page_updates == 0, '中断分支不应再打任何一场小怪'


def test_wait_vip_boss_uses_precise_sleep_inside_snipe_window():
    """40~120 秒这一段原本会被甩去刷小怪（批量动辄一两分钟，直接跨过刷新点），

    现在必须精确睡到刷新时刻。
    """
    bot = _FakeBot(remain=90)
    next_state = _run(WaitVipBossState(bot))
    assert isinstance(next_state, IdleState), f'应精确等待，实际跳到 {type(next_state).__name__}'
    assert 80 <= next_state._idle_time <= 91, f'等待时长应约等于剩余时间，实际 {next_state._idle_time}'


def test_wait_vip_boss_keeps_farming_far_from_spawn():
    """离刷新还远的时候仍然交给小怪流程，避免干等被踢。"""
    bot = _FakeBot(remain=SNIPE_WINDOW + 300)
    next_state = _run(WaitVipBossState(bot))
    assert isinstance(next_state, IdleState)
    assert next_state._idle_time <= 40, '远场应先短睡再交棒给刷怪流程'


def test_prepare_boss_never_sleeps_past_vip_spawn():
    """冷却睡眠必须截断在刷新前，否则一觉睡过刷新时刻就等于白等一轮。"""
    # 长冷却分支：本来要睡满 30 秒，但刷新只剩 10 秒
    bot = _FakeBot(remain=10)
    bot.challenge_next_cooldown = 900
    next_state = _run(PrepareBossState(bot))
    assert isinstance(next_state, IdleState)
    assert next_state._idle_time <= 10, f'不应睡过刷新时刻，实际睡 {next_state._idle_time}'

    # 短冷却分支：本来要睡满 20 秒，但刷新只剩 10 秒
    bot = _FakeBot(remain=10)
    bot.challenge_next_cooldown = 20
    next_state = _run(PrepareBossState(bot))
    assert isinstance(next_state, IdleState)
    assert next_state._idle_time <= 10, f'不应睡过刷新时刻，实际睡 {next_state._idle_time}'


def test_seconds_until_vip_boss_spawn_without_waiting_record():
    """没有等待记录时不应凭空空转。"""
    bot = _FakeBot(remain=None)
    assert bot.seconds_until_vip_boss_spawn() is None


class _LogFailingBot(_FakeBot):
    """模拟：hunt 页刷得出来，但 ?ulog 战报一直拉不到。"""

    def __init__(self, fail_streak=0):
        super().__init__(remain=None)
        self.all_alived_boss_ids = []
        self.server_config_manager = types.SimpleNamespace(
            current_server_data={'url': 'https://example.com/hall/'},
            all_action_config_by_server={'600170': {'name': 'fake', 'actions': []}},
        )
        self.auto_bot_config_manager.vip_boss_need_watch = [
            {'union_id': 17, 'plan_action_id': 600170, 'kill_cooldown_seconds': 14400}
        ]
        self.auto_bot_config_manager.is_challenge_vip_boss = True
        self.auto_bot_config_manager.challenge_boss_cooldown_seconds = 1200
        self.vip_boss_log_fail_streak = fail_streak
        self.boss_battle_manager = types.SimpleNamespace(get_next_vip_boss=lambda *a, **k: None)

    def reset_waiting_vip_boss_spawn_info(self):
        self.is_waiting_for_vip_boss = False
        self.next_vip_boss_spawn_timestamp = -1


def test_vip_boss_does_not_burn_cooldown_when_log_fetch_fails():
    """战报拉不到时不能直接去打普通 boss —— 那会白烧一个 20 分钟挑战冷却，整轮 VIP 报废。"""
    from scripts.states.normal_boss_state import NormalBossState
    from scripts.states.vip_boss_state import VipBossState

    bot = _LogFailingBot(fail_streak=0)
    _run(VipBossState(bot))
    assert not isinstance(bot.current_state, NormalBossState), '战报失败不应该立刻去打普通 boss'
    assert isinstance(bot.current_state, IdleState)
    assert bot.vip_boss_log_fail_streak == 1


def test_vip_boss_gives_up_after_three_log_failures():
    """连续失败到上限后必须放行，否则战报挂掉会卡死整个打 boss 流程。"""
    from scripts.states.normal_boss_state import NormalBossState
    from scripts.states.vip_boss_state import VipBossState

    bot = _LogFailingBot(fail_streak=2)
    _run(VipBossState(bot))
    assert isinstance(bot.current_state, NormalBossState), '连续失败到上限后应放行到普通 boss'
    assert bot.vip_boss_log_fail_streak == 0


class _GuardBot(_FakeBot):
    """知道 VIP 刷新时刻、并按真实数值配了"失败 20 分钟 / 击杀 60 分钟"两档的桩。"""

    FAIL_COOLDOWN = 1200
    KILL_COOLDOWN = 3600
    MARGIN = 180
    GUARD = FAIL_COOLDOWN + MARGIN      # 硬保护窗口：剩不到这么久就不打
    RISK = KILL_COOLDOWN + MARGIN       # 风险区上界：可打，但打死就丢本轮 VIP

    def __init__(self, remain_vip, alived=None):
        super().__init__(remain=None)
        cfg = self.auto_bot_config_manager
        cfg.vip_boss_need_watch = [
            {'union_id': 17, 'plan_action_id': 600170, 'kill_cooldown_seconds': 14400}
        ]
        cfg.is_challenge_vip_boss = True
        cfg.challenge_boss_cooldown_seconds = self.FAIL_COOLDOWN   # 失败冷却
        cfg.challenge_boss_kill_cooldown_seconds = self.KILL_COOLDOWN
        cfg.vip_cooldown_guard_margin_seconds = self.MARGIN
        cfg.vip_cooldown_guard_seconds = self.GUARD
        cfg.vip_kill_risk_seconds = self.RISK
        cfg.challenge_boss_delay_rate = -1                  # 永不触发随机延迟
        cfg.normal_boss_loop_order = [{'union_id': 25, 'plan_action_id': 600001}]
        self.all_alived_boss_ids = alived if alived is not None else []
        self.server_clock_offset = 0.0
        self.server_config_manager = types.SimpleNamespace(
            current_server_data={'url': 'https://example.com/hall/'},
            all_action_config_by_server={'600170': {'name': 'vip', 'actions': []}},
        )
        self.boss_battle_manager = types.SimpleNamespace(
            get_next_vip_boss=lambda *a, **k: {
                'future_unixtime': int((time.time() + remain_vip) * 1000000)
            }
        )
        self.vip_boss_log_fail_streak = 0
        self.battle_watcher_manager = types.SimpleNamespace(get_all_alive_boss=lambda: ['25'])

    def set_next_vip_boss_spawn_timestamp(self, union_id, timestamp):
        self.next_vip_boss_spawn_timestamp = timestamp
        self.next_vip_boss_id = union_id
        self.is_waiting_for_vip_boss = True

    def reset_waiting_vip_boss_spawn_info(self):
        self.is_waiting_for_vip_boss = False
        self.next_vip_boss_spawn_timestamp = -1


def test_vip_boss_guard_is_failure_cooldown_and_kill_risk_is_separate():
    """硬保护窗口只按失败冷却（20 分钟）+余量算；击杀 60 分钟那一档单独作为风险区上界。"""
    from scripts.auto_bot_config_manager import AutoBotConfigManager

    mgr = AutoBotConfigManager.__new__(AutoBotConfigManager)
    mgr.config = {'challege_boss_cooldown_seconds': 1200}
    assert mgr.challenge_boss_kill_cooldown_seconds == 3600
    assert mgr.vip_cooldown_guard_seconds == 1200 + 180, '硬窗口必须按失败冷却算，别把击杀冷却绑进来'
    assert mgr.vip_kill_risk_seconds == 3600 + 180, '风险区上界要按击杀冷却算'
    assert mgr.vip_cooldown_guard_seconds < mgr.vip_kill_risk_seconds


def test_vip_boss_enters_guard_window_when_failure_cooldown_would_trip():
    """距刷新 20 分钟（连一次失败冷却都不够）就必须进入保护窗口。"""
    from scripts.states.vip_boss_state import VipBossState

    bot = _GuardBot(remain_vip=_GuardBot.FAIL_COOLDOWN - 200)
    _run(VipBossState(bot))
    assert bot.is_waiting_for_vip_boss, '剩不到一次失败冷却就该进入保护窗口'
    assert isinstance(bot.current_state, WaitVipBossState), \
        f'应转入等待状态，实际 {type(bot.current_state).__name__}'


def test_vip_boss_leaves_kill_risk_zone_to_normal_boss_flow():
    """距刷新 50 分钟：够一次失败冷却、不够一次击杀冷却——继续放行普通 boss。"""
    from scripts.states.vip_boss_state import VipBossState

    bot = _GuardBot(remain_vip=3000)
    _run(VipBossState(bot))
    assert not bot.is_waiting_for_vip_boss, '距刷新 50 分钟已超出硬保护窗口，应交还普通 boss 流程'


def test_normal_boss_refuses_to_burn_failure_cooldown_before_spawn():
    """剩不到一次失败冷却时普通 boss 也不能打：输了锁 20 分钟，正好跨过刷新点。"""
    from scripts.states.normal_boss_state import NormalBossState

    bot = _GuardBot(remain_vip=_GuardBot.FAIL_COOLDOWN - 200)
    next_state = _run(NormalBossState(bot))
    assert isinstance(next_state, IdleState), \
        f'距刷新不足一次失败冷却，不该打普通 boss，实际跳到 {type(next_state).__name__}'


def test_normal_boss_fights_inside_kill_risk_zone_with_warning():
    """距刷新 50 分钟：照打普通 boss（击杀风险已接受），但日志必须写明打死就丢本轮 VIP。"""
    from scripts.states.normal_boss_state import NormalBossState

    logs = []
    bot = _GuardBot(remain_vip=3000)
    bot.logger.info = lambda msg: logs.append(str(msg))
    # 存活列表留空，直接走到"没有普通boss需要处理"，避免这里牵扯动作/等级判定
    bot.battle_watcher_manager = types.SimpleNamespace(get_all_alive_boss=lambda: [])
    next_state = _run(NormalBossState(bot))
    assert not isinstance(next_state, IdleState), '风险区内应放行普通 boss'
    assert any('本轮vip就错过了' in m for m in logs), f'应打出击杀风险提示，实际日志：{logs}'


def test_normal_boss_skips_guard_blocked_boss_and_picks_next():
    """17 刚被 VIP 狙击打过（闸门还差 586 秒）时，普通流程要跳过它去打下一只。

    回归：2026-11-17 11:17 那轮，VIP 狙击提交后 14 秒普通流程又选中 17，
    直提状态里被闸门拦下后按剩余间隔睡了 585 秒，整段挂机白停。
    """
    from scripts.states.directly_challenge_boss_state import DirectlyChallengeBossState
    from scripts.states.normal_boss_state import NormalBossState

    logs = []
    bot = _GuardBot(remain_vip=3000)
    bot.logger.info = lambda msg: logs.append(str(msg))
    bot.auto_bot_config_manager.normal_boss_loop_order = [
        {'union_id': 17, 'plan_action_id': 600170},
        {'union_id': 25, 'plan_action_id': 600001},
    ]
    bot.battle_watcher_manager = types.SimpleNamespace(get_all_alive_boss=lambda: [17, 25])
    bot.boss_challenge_guard = types.SimpleNamespace(
        seconds_until_allowed=lambda union_id: 586.0 if int(union_id) == 17 else 0.0
    )
    bot.server_config_manager.all_action_config_by_server['600001'] = {'name': 'normal', 'actions': []}
    bot.boss_battle_manager.is_action_level_exceed_boss_limit = lambda *a, **k: False

    next_state = _run(NormalBossState(bot))
    assert isinstance(next_state, DirectlyChallengeBossState), \
        f'应跳过被挡的 17 去打 25，实际跳到 {type(next_state).__name__}'
    assert next_state.union_id == 25, f'应选中 25，实际 {next_state.union_id}'
    assert any('这只跳过' in m for m in logs), f'应打出跳过日志，实际：{logs}'


def test_prepare_boss_warns_when_cooldown_swallows_spawn():
    """冷却会盖过刷新时刻时必须有明确提示，否则看起来像"根本没触发 VIP 流程"。"""
    logs = []
    bot = _FakeBot(remain=600)
    bot.challenge_next_cooldown = 1800
    bot.logger.info = lambda msg: logs.append(str(msg))
    _run(PrepareBossState(bot))
    assert any('本轮vip会错过' in m for m in logs), f'应提示会错过，实际日志：{logs}'


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f'  ok  {name}')
    print("测试通过！")
