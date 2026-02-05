from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.hof_auto_bot_main import HofAutoBot
    from .base_state import BaseState
    from .prepare_boss_state import PrepareBossState
    from .normal_stage_state import NormalStageState
    from .pvp_state import PvpState
    from .world_pvp_state import WorldPvpState
    from .vip_boss_state import VipBossState
    from .wait_vip_boss_state import WaitVipBossState
    from .directly_challenge_boss_state import DirectlyChallengeBossState
    from .idle_state import IdleState
    from .normal_boss_state import NormalBossState
    from .update_character_state import UpdateCharacterState

class StateFactory:
    @staticmethod
    def create_prepare_boss_state(bot: 'HofAutoBot') -> 'BaseState':
        from .prepare_boss_state import PrepareBossState
        return PrepareBossState(bot)

    @staticmethod
    def create_normal_stage_state(bot: 'HofAutoBot') -> 'BaseState':
        from .normal_stage_state import NormalStageState
        return NormalStageState(bot)

    @staticmethod
    def create_pvp_state(bot: 'HofAutoBot') -> 'BaseState':
        from .pvp_state import PvpState
        return PvpState(bot)

    @staticmethod
    def create_world_pvp_state(bot: 'HofAutoBot') -> 'BaseState':
        from .world_pvp_state import WorldPvpState
        return WorldPvpState(bot)

    @staticmethod
    def create_vip_boss_state(bot: 'HofAutoBot') -> 'BaseState':
        from .vip_boss_state import VipBossState
        return VipBossState(bot)

    @staticmethod
    def create_wait_vip_boss_state(bot: 'HofAutoBot') -> 'BaseState':
        from .wait_vip_boss_state import WaitVipBossState
        return WaitVipBossState(bot)

    @staticmethod
    def create_directly_challenge_boss_state(bot: 'HofAutoBot') -> 'BaseState':
        from .directly_challenge_boss_state import DirectlyChallengeBossState
        return DirectlyChallengeBossState(bot)

    @staticmethod
    def create_idle_state(bot: 'HofAutoBot') -> 'BaseState':
        from .idle_state import IdleState
        return IdleState(bot)

    @staticmethod
    def create_normal_boss_state(bot: 'HofAutoBot') -> 'BaseState':
        from .normal_boss_state import NormalBossState
        return NormalBossState(bot)
        
    @staticmethod
    def create_time_limited_stage_state(bot: 'HofAutoBot') -> 'BaseState':
        from .time_limited_stage_state import TimeLimitedStageState
        return TimeLimitedStageState(bot)

    @staticmethod
    def create_prepare_stage_state(bot: 'HofAutoBot') -> 'BaseState':
        from .prepare_stage_state import PrepareStageState
        return PrepareStageState(bot)
        
    @staticmethod
    def create_update_character_state(bot: 'HofAutoBot') -> 'BaseState':
        from .update_character_state import UpdateCharacterState
        return UpdateCharacterState(bot)
    @staticmethod
    def create_reconnect_state(bot: 'HofAutoBot') -> 'BaseState':
        from .reconnect_state import ReconnectState
        return ReconnectState(bot)
