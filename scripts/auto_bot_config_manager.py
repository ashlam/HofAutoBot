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
    def boss_check_max_gap_seconds(self) -> float: # 多久没检查boss就强制回主线，<=0 关闭
        return self.config.get('boss_check_max_gap_seconds', 180)

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
    def vip_snipe_window_seconds(self) -> int:
        """VIP 刷新前多少秒进入"狙击窗口"：不再刷小怪/打普通 boss，只等刷新那一刻出手。"""
        return self.config.get('vip_snipe_window_seconds', 120)

    @property
    def vip_snipe_warmup_lead_seconds(self) -> float:
        """刷新前多少秒开始预热（加载 boss 页 + 清队 + 勾人），这段时间不产生"慢动作"。"""
        return float(self.config.get('vip_snipe_warmup_lead_seconds', 6))

    @property
    def vip_snipe_fire_cost_seconds(self) -> float:
        """最后一次提交预留多少秒往返预算：在 T 之前这么多秒点下去。

        只留一点点就行：早发必失败（boss 还没刷），晚发一点最多被抢 0.1 秒，
        所以宁可贴着 T 发。
        """
        return float(self.config.get('vip_snipe_fire_cost_seconds', 0.03))

    @property
    def vip_snipe_commit_offset_ms(self) -> float:
        """提交时刻整体平移（毫秒）。负值=更早、正值=更晚，按实测偏差微调。"""
        return float(self.config.get('vip_snipe_commit_offset_ms', 0))

    @property
    def vip_snipe_settle_seconds(self) -> float:
        """点完开战后先等几秒再刷新页面确认结果，避免把正在提交的表单打断。"""
        return float(self.config.get('vip_snipe_settle_seconds', 1.0))

    @property
    def boss_challenge_min_interval_seconds(self) -> float:
        """同一个 boss 两次挑战请求之间的最小间隔。

        服务器对同一只 boss 的两次请求都会按合法处理，两次结果都会进战报公示，
        所以这个间隔本质上是"绝不允许对同一只 boss 连发请求"的兜底。
        """
        return float(self.config.get('boss_challenge_min_interval_seconds', 600))

    @property
    def challenge_boss_cooldown_seconds(self) -> int:
        return self.config.get('challege_boss_cooldown_seconds', 1200)
