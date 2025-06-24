# scripts/states/__init__.py

from scripts.states.base_state import BaseState
from scripts.states.prepare_boss_state import PrepareBossState
from scripts.states.vip_boss_state import VipBossState
from scripts.states.wait_vip_boss_state import WaitVipBossState
from scripts.states.pvp_state import PvpState
from scripts.states.world_pvp_state import WorldPvpState
from scripts.states.normal_stage_state import NormalStageState
from scripts.states.idle_state import IdleState
from scripts.states.directly_challenge_boss_state import DirectlyChallengeBossState
from scripts.states.normal_boss_state import NormalBossState
# 其他状态类依此类推……

__all__ = [
    'BaseState',
    'PrepareBossState',
    'VipBossState',
    'WaitVipBossState',
    'PvpState',
    'WorldPvpState',
    'NormalStageState',
    'IdleState',
    'DirectlyChallengeBossState',
    'NormalBossState',
    # ……其他状态类
]