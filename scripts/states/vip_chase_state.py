# -*- coding: utf-8 -*-
"""VIP 追打：狙击那一枪被服务端拒绝之后，盯着刚刷出来的 boss 再打一次。

背景（2026-11-19 15:42 那轮）：狙击在 T+0.17s 出手，落地页写
"特殊怪物 Defeated or not Exists"——那一刻 boss 还没刷出来。1.3 秒之后
boss 就出现在存活列表里了，但我们把这次"被拒绝"当成"已经出过手"，
接下来的 20 分钟窗口一次都没再碰它（对方第一次也打输了，boss 在原地
活了整整 20 分钟）。

被拒绝的请求不会生成战斗、不进战报、不给冷却，服务端看它跟没发生过一样。
所以这里做的事很简单：在刷新后的一小段时间里盯存活列表，boss 一出现就直提，
直到真的打上（进入冷却）为止。

安全边界（与补枪同一套）：
- 只在"上一枪被服务端明确拒绝"之后由 VipSnipeState 拉起来；
- 最多追打 MAX_ATTACKS 次，两次之间闸门还要求留 retry_gap 秒，请求永远不会同时在飞；
- 本号一旦出现挑战冷却（说明这一枪真打上了）立刻退出，绝不连击；
- 窗口结束（默认 60 秒）就还给常规流程，不会一直粘着。
"""

import time
from functools import partial

from .base_state import BaseState
from .state_factory import StateFactory


class VipChaseState(BaseState):
    """盯着 VIP boss 出现的那一刻补打。"""

    WINDOW_SECONDS = 60.0          # 刷新后追多久
    POLL_SECONDS = 3.0             # 每轮看存活列表的间隔
    MAX_ATTACKS = 3                # 最多补打几次
    RETRY_GAP_SECONDS = 3.0        # 两次补打之间至少隔多久

    def __init__(self, bot, union_id=None, advanced_action_config=None,
                 spawn_timestamp_us=None, deadline_ts=None, attempts=0):
        super().__init__(bot)
        self.union_id = union_id
        self.advanced_action_config = advanced_action_config
        self.spawn_timestamp_us = spawn_timestamp_us
        self.deadline_ts = deadline_ts if deadline_ts else time.time() + self.WINDOW_SECONDS
        self.attempts = attempts

    # ------------------------------------------------------------------ 主流程

    def process(self):
        if getattr(self.bot, 'is_finished', False):
            return
        if not self.union_id or not self.advanced_action_config:
            self.log('VIP追打：缺少 boss 配置，放弃追打')
            return self._give_up()

        try:
            self.bot._update_info_from_hunt_page()
        except Exception as e:
            self.log(f'VIP追打：刷新 boss 信息失败 {type(e).__name__}: {e}')

        cooldown = getattr(self.bot, 'challenge_next_cooldown', 0) or 0
        if cooldown > 0:
            self.log(f'VIP追打：本号已进入挑战冷却（{cooldown}秒），'
                     f'说明这一枪真的打上了，退出追打')
            return self._give_up()

        if self._is_boss_alive():
            if self.attempts >= self.MAX_ATTACKS:
                self.log(f'VIP追打：已经补打 {self.attempts} 次仍未受理，放弃追打（boss 还在场）')
                return self._give_up()
            self.attempts += 1
            self.log(f'VIP追打：boss({self.union_id}) 已在场，立刻直提'
                     f'（第{self.attempts}/{self.MAX_ATTACKS}次，窗口还剩 '
                     f'{max(0.0, self.deadline_ts - time.time()):.0f} 秒）')
            state = StateFactory.create_directly_challenge_boss_state(
                self.bot,
                allow_rejected_retry=True,
                purpose='vip_chase',
                retry_gap=self.RETRY_GAP_SECONDS,
                max_attempts=self.attempts + 1,
            )
            state.union_id = self.union_id
            state.advanced_action_config = self.advanced_action_config
            state.on_challenge_success = self._on_challenge_success
            state.on_challenge_failed = self._on_challenge_failed
            self.set_state(state)
            return

        if time.time() >= self.deadline_ts:
            self.log('VIP追打：窗口结束，boss 始终没出现在存活列表里，放弃追打')
            return self._give_up()

        remain = self.deadline_ts - time.time()
        self.log(f'VIP追打：boss({self.union_id}) 还没出现，'
                 f'{self.POLL_SECONDS:.0f}秒后再看（窗口还剩 {remain:.0f} 秒）')
        idle_state = StateFactory.create_idle_state(self.bot)
        idle_state.set_idle_time(
            self.POLL_SECONDS,
            partial(self.set_state, StateFactory.create_vip_chase_state(
                self.bot, self.union_id, self.advanced_action_config,
                self.spawn_timestamp_us, self.deadline_ts, self.attempts,
            )),
        )
        self.set_state(idle_state)

    # ------------------------------------------------------------------ 回调

    def _on_challenge_success(self):
        self.log('VIP追打：打上了，结束追打')
        self.bot.reset_waiting_vip_boss_spawn_info()
        self.set_state(StateFactory.create_world_pvp_state(self.bot))

    def _on_challenge_failed(self):
        self.log('VIP追打：这一次没打成，回到追打循环')
        self.set_state(StateFactory.create_vip_chase_state(
            self.bot, self.union_id, self.advanced_action_config,
            self.spawn_timestamp_us, self.deadline_ts, self.attempts,
        ))

    # ------------------------------------------------------------------ 工具

    def _is_boss_alive(self) -> bool:
        try:
            alive = self.bot.battle_watcher_manager.get_all_alive_boss() or []
        except Exception as e:
            self.log(f'VIP追打：读存活列表失败 {type(e).__name__}: {e}')
            return False
        return str(self.union_id) in [str(item) for item in alive]

    def _give_up(self):
        self.bot.reset_waiting_vip_boss_spawn_info()
        self.set_state(StateFactory.create_prepare_boss_state(self.bot))
