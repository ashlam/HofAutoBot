from typing import List, Dict
import json

class AutoBotConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        with open(self.config_path, 'r') as f:
            return json.load(f)

    @property
    def boss_cost_stamina(self) -> int:
        return self.config.get('boss_cost_stamina', 10)

    @property
    def stage_cost_stamina(self) -> int: # 小怪消耗体力
        return self.config.get('stage_cost_stamina', 100)
    @property
    def keep_stamnia_for_normal_stage(self) -> int: # 切换小怪消耗体力
        return self.config.get('keep_stamnia_for_normal_stage', 3000)
    @property
    def keep_stamnia_for_time_limited_stage(self) -> int:
        return self.config.get('keep_stamnia_for_time_limited_stage', 1000)
    @property
    def quest_cost_stamina(self) -> int: # 任务消耗体力
        return self.config.get('quest_cost_stamina', 300)

    @property
    def max_stamnia_limit(self) -> int: # 体力上限
        return self.config.get('max_stamnia_limit', 4000)

    @property
    def is_challenge_vip_boss(self) -> bool:
        return self.config.get('is_challenge_vip_boss', False)

    @property
    def is_challenge_pvp(self) -> bool:
        return self.config.get('is_challenge_pvp', False)

    @property
    def is_keep_pvp_win_rate(self) -> bool:
        return self.config.get('is_keep_pvp_win_rate', False)

    @property
    def is_challenge_world_pvp(self) -> bool:
        return self.config.get('is_challenge_world_pvp', False)

    @property
    def vip_boss_need_watch(self) -> List[Dict]:
        return self.config.get('vip_boss_need_watch', [])
        
    @property
    def time_limited_stage_need_watch(self) -> List[Dict]:
        return self.config.get('time_limited_stage_need_watch', [])

    @property
    def is_challenge_time_limited_stage(self) -> bool:
        return self.config.get('is_challenge_time_limited_stage', False)

    @property
    def normal_boss_loop_order(self) -> List[Dict]:
        return self.config.get('normal_boss_loop_order', [])

    @property
    def normal_stage_loop_order(self) -> List[Dict]:
        return self.config.get('normal_stage_loop_order', [])

    @property
    def pvp_plan_action_id(self) -> int:
        return self.config.get('pvp_plan_action_id', 0)

    @property
    def pvp_prepare_plan_action_id(self) -> int:
        return self.config.get('pvp_prepare_plan_action_id', 0)

    @property
    def world_pvp_plan_action_id(self) -> int:
        return self.config.get('world_pvp_plan_action_id', 0)

    @property
    def challenge_boss_delay_rate(self) -> int:
        return self.config.get('challenge_boss_delay_rate', 0)

    @property
    def challenge_boss_delay_seconds_limit(self) -> int:
        return self.config.get('challenge_boss_delay_seconds_limit', 5)

    @property
    def idle_seconds_for_challenge_boss(self) -> int:
        return self.config.get('idle_seconds_for_challenge_boss', 30)

    @property
    def idle_seconds_for_challenge_vip_boss(self) -> int:
        return self.config.get('idle_seconds_for_challenge_vip_boss', 40)

    @property
    def challenge_boss_cooldown_seconds(self) -> int:
        return self.config.get('challege_boss_cooldown_seconds', 1200)
