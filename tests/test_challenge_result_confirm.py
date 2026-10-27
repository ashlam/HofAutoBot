# -*- coding: utf-8 -*-
"""回归测试：2026-10-27 17:00 那次实际运行暴露的两个问题。

1) 挑战请求发出去之后只看一次 hunt 页就下结论 —— 页面还是提交前的快照，
   于是把"打成了"判成"没打成"。日志证据：
     17:00:10.990 批量boss战（提交）
     17:00:11.783 页面仍是"boss 17 存活 + 无冷却" -> is_success: False
     17:00:12.134 同一页面变成"boss 17 消失 + 冷却 3599 秒"（其实打成了）
2) 体力落在"限时关卡阈值(1000)"和"普通关卡阈值(3000)"之间、且限时关卡入口
   不存在时，PrepareStage -> TimeLimited -> NormalStage -> PrepareStage 死循环，
   13 秒一圈什么都不做，boss 一次都不会被检查（日志里卡了 5 分钟）。
"""
import os
import sys
import time
import types

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_stub = types.ModuleType("scripts.hof_auto_bot_main")


class _HofAutoBot:
    pass


_stub.HofAutoBot = _HofAutoBot
sys.modules["scripts.hof_auto_bot_main"] = _stub

from scripts.states.base_state import BaseState
from scripts.states.normal_stage_state import NormalStageState
from scripts.states.prepare_boss_state import PrepareBossState
from scripts.states.prepare_stage_state import PrepareStageState


class _Logger:
    def __init__(self):
        self.lines = []

    def __getattr__(self, name):
        def _record(*args, **kwargs):
            self.lines.append(' '.join(str(a) for a in args))

        return _record


class _Config:
    keep_stamnia_for_normal_stage = 3000
    keep_stamnia_for_time_limited_stage = 1000
    normal_stage_loop_order = [{'stage_name': 'ocean1', 'plan_action_id': 1}]
    vip_snipe_window_seconds = 120
    boss_cost_stamina = 10
    idle_seconds_for_challenge_boss = 30
    is_challenge_time_limited_stage = False
    time_limited_stage_need_watch = None


class _Bot:
    """只模拟 _confirm_challenge_result / NormalStageState 用到的那几个接口。"""

    def __init__(self, pages):
        self.logger = _Logger()
        self.auto_bot_config_manager = _Config()
        self.current_state = None
        self.player_stamina = 4000
        self.challenge_next_cooldown = 0
        self.all_alived_boss_ids = []
        self.is_waiting_for_vip_boss = False
        self.next_vip_boss_spawn_timestamp = -1
        self._pages = list(pages)
        self.hunt_reads = 0
        self.battle_watcher_manager = types.SimpleNamespace(
            get_player_stamina=lambda: self.player_stamina
        )
        self.server_config_manager = types.SimpleNamespace(
            all_action_config_by_server={'1': {'name': 'fake', 'actions': []}}
        )

    def seconds_until_vip_boss_spawn(self):
        return None

    def switch_to_next_state(self, state):
        self.current_state = state

    def _update_info_from_hunt_page(self):
        """按顺序吐出预置的页面快照，模拟"刚提交完页面还没更新"。"""
        self.hunt_reads += 1
        if not self._pages:
            return
        page = self._pages.pop(0) if len(self._pages) > 1 else self._pages[0]
        self.challenge_next_cooldown = page['cooldown']
        self.all_alived_boss_ids = list(page['alive'])


class _State(BaseState):
    def process(self):
        pass


def _confirm(bot, **kwargs):
    return _State(bot)._confirm_challenge_result(17, **kwargs)


# --------------------------------------------------------------- 结果确认


def test_stale_first_read_does_not_look_like_failure():
    """第一次读到旧快照（boss 还在、无冷却），后面读到冷却 —— 必须判成功。"""
    bot = _Bot([
        {'cooldown': 0, 'alive': ['16', '17']},        # 提交前的快照
        {'cooldown': 3599, 'alive': ['16']},           # 真实结果
    ])
    assert _confirm(bot, attempts=4, interval=0.01, first_wait=0) is True
    assert bot.hunt_reads >= 2


def test_boss_disappeared_counts_as_accepted():
    """没有冷却但有别的 boss 存活、且目标已不在列表 —— 说明页面确实更新了，算受理。"""
    bot = _Bot([{'cooldown': 0, 'alive': ['16', '18']}])
    assert _confirm(bot, attempts=2, interval=0.01, first_wait=0) is True


def test_empty_alive_list_is_not_evidence():
    """页面没解析出任何 boss（登录页/网络异常）不能当成"boss 被打掉了"。"""
    bot = _Bot([{'cooldown': 0, 'alive': []}])
    assert _confirm(bot, attempts=2, interval=0.01, first_wait=0) is False


def test_unchanged_page_reports_failure():
    """一直读到"boss 还在 + 无冷却"，就是真的没打成。"""
    bot = _Bot([{'cooldown': 0, 'alive': ['17']}])
    assert _confirm(bot, attempts=3, interval=0.01, first_wait=0) is False
    assert bot.hunt_reads == 3, f'应轮询 3 次，实际 {bot.hunt_reads}'


# --------------------------------------------------------------- 状态机死循环


def test_normal_stage_without_stamina_goes_to_boss():
    """体力不够刷小怪时应直接去看 boss，而不是回到 PrepareStage 打转。"""
    bot = _Bot([])
    bot.player_stamina = 2904  # 高于限时关卡阈值 1000，低于普通关卡阈值 3000
    NormalStageState(bot).process()
    assert isinstance(bot.current_state, PrepareBossState), \
        f'应转去检查 boss，实际跳到 {type(bot.current_state).__name__}'


def test_no_stage_boss_prepare_ping_pong():
    """还原日志里的死循环：PrepareStage -> TimeLimited -> NormalStage -> ... 必须能走出去。"""
    from scripts.states.time_limited_stage_state import TimeLimitedStageState

    bot = _Bot([])
    bot.player_stamina = 2904
    bot.auto_bot_config_manager.is_challenge_time_limited_stage = True
    bot.auto_bot_config_manager.time_limited_stage_need_watch = {
        'stage_name': 'Christmas', 'plan_action_id': 12,
        'start_minute': 0, 'end_minute': 59,
    }
    # 限时关卡入口找不到 -> TimeLimitedStageState 退回 NormalStageState
    bot.driver = types.SimpleNamespace(find_elements=lambda *a, **k: [])

    states = []
    state = PrepareStageState(bot)
    for _ in range(6):
        state.process()
        state = bot.current_state
        states.append(type(state).__name__)
        if isinstance(state, PrepareBossState):
            break

    assert states[-1] == 'PrepareBossState', \
        f'连续 {len(states)} 步仍未走到 boss 检查，实际轨迹 {states}'


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f'  ok  {name}')
    print("测试通过！")
