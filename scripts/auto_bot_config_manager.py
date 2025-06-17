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
    def keep_stamnia_for_change_stage(self) -> int: # 切换小怪消耗体力
        return self.config.get('keep_stamnia_for_change_stage', 1000)
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
    def is_challenge_world_pvp(self) -> bool:
        return self.config.get('is_challenge_world_pvp', False)

    @property
    def vip_boss_need_watch(self) -> List[Dict]:
        return self.config.get('vip_boss_need_watch', [])

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
    def world_pvp_plan_action_id(self) -> int:
        return self.config.get('world_pvp_plan_action_id', 0)