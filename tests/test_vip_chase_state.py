# -*- coding: utf-8 -*-
"""VIP 追打状态的回归测试。

对应 2026-11-19 15:42 那轮的现场：狙击打空（落地页 not exists），boss 1.3 秒后
才刷出来，而我们把它当成"已经出过手"，整个 20 分钟窗口一次都没再碰。
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

from scripts.states.vip_chase_state import VipChaseState

ACTION_CONFIG = {'actions': []}


class _FakeLogger:
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            pass

        return _noop


class _FakeBot:
    def __init__(self, alive=(), cooldown=0):
        self.logger = _FakeLogger()
        self.current_state = None
        self.current_state_str = ''
        self.challenge_next_cooldown = cooldown
        self.all_alived_boss_ids = list(alive)
        self.hunt_page_updates = 0
        self.waiting_reset = 0
        self.battle_watcher_manager = types.SimpleNamespace(
            get_all_alive_boss=lambda: list(self.all_alived_boss_ids)
        )
        self.auto_bot_config_manager = types.SimpleNamespace(
            idle_seconds_for_challenge_boss=30,
            vip_boss_need_watch=[],
        )

    def _update_info_from_hunt_page(self):
        self.hunt_page_updates += 1

    def reset_waiting_vip_boss_spawn_info(self):
        self.waiting_reset += 1

    def switch_to_next_state(self, state):
        self.current_state = state
        self.current_state_str = state.__class__.__name__


def _make(alive=(), cooldown=0, deadline=None, attempts=0):
    bot = _FakeBot(alive=alive, cooldown=cooldown)
    state = VipChaseState(bot, 17, ACTION_CONFIG, 1795074142257361,
                          deadline if deadline is not None else time.time() + 60, attempts)
    return bot, state


def test_boss_alive_goes_straight_to_direct_challenge():
    """boss 已经在场：立刻直提，而且允许"上一枪被拒"之后的补打。"""
    bot, state = _make(alive=['17', '25'])

    state.process()

    current = bot.current_state
    assert type(current).__name__ == 'DirectlyChallengeBossState', \
        f'应直接进直提状态，实际 {type(current).__name__}'
    assert current.union_id == 17
    assert current.allow_rejected_retry is True, '追打必须走"被拒可补打"通道'
    assert current.purpose == 'vip_chase'


def test_boss_not_alive_keeps_waiting_inside_window():
    """还没刷出：留在窗口里继续盯，不能直接放弃。"""
    bot, state = _make(alive=['25'])

    state.process()

    assert type(bot.current_state).__name__ == 'IdleState', \
        f'窗口内应继续等待，实际 {type(bot.current_state).__name__}'
    assert bot.waiting_reset == 0, '窗口没结束前不要清掉等待记录'


def test_window_expired_gives_up_to_prepare_boss():
    """窗口结束：还给常规流程，不粘着。"""
    bot, state = _make(alive=[], deadline=time.time() - 1)

    state.process()

    assert type(bot.current_state).__name__ == 'PrepareBossState'
    assert bot.waiting_reset == 1


def test_cooldown_means_shot_landed_and_stops_chasing():
    """本号进了冷却 = 真打上了，立刻停手，绝不连击。"""
    bot, state = _make(alive=['17'], cooldown=1199)

    state.process()

    assert type(bot.current_state).__name__ == 'PrepareBossState'
    assert bot.waiting_reset == 1


def test_attempts_capped():
    """补打次数到顶就收手，避免一直粘着同一只 boss 发请求。"""
    bot, state = _make(alive=['17'], attempts=VipChaseState.MAX_ATTACKS)

    state.process()

    assert type(bot.current_state).__name__ == 'PrepareBossState'


def test_success_callback_goes_to_pvp():
    bot, state = _make(alive=['17'])
    state.process()

    state._on_challenge_success()

    assert type(bot.current_state).__name__ == 'WorldPvpState'


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_") and callable(func):
            func()
            print(f'  ok  {name}')
    print("测试通过！")
