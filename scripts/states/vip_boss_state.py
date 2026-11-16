from typing import Dict
from functools import partial
from .base_state import BaseState
from datetime import datetime
from .state_factory import StateFactory
from scripts.hof_auto_bot_main import HofAutoBot
from scripts.states.directly_challenge_boss_state import DirectlyChallengeBossState

class VipBossState(BaseState):

    def __init__(self, bot: HofAutoBot):
        super().__init__(bot)
        self.bot = bot

    def process(self):
        """
        走到vip boss的时候已经是【无cd且体力充足】的状态了，接下来要做的就是：
        1.能打就直接打
        2.进入vip等待（WaitVipBossState），让vip等待状态去执行其他状态的转化
        """
        self.log('开始处理VIP boss')

        for vip_boss in self.bot.auto_bot_config_manager.vip_boss_need_watch:
            union_id = vip_boss['union_id']
            plan_action_id = vip_boss['plan_action_id']
            advanced_action_config = self.bot.server_config_manager.all_action_config_by_server.get(f"{plan_action_id}")
            if not advanced_action_config:
                self.log(f'未找到动作配置，id: {plan_action_id} ，没有办法处理boss({union_id})，找下一条vip boss。')
                continue
            # 检查VIP boss是否出现
            if union_id in self.bot.all_alived_boss_ids:
                # 活着，试着直接干它
                if self._already_fired():
                    # 已经出过手还在存活列表里：说明那次请求被拒了（或者被别人抢先、
                    # 或者服务器还没写完）。这时再打一次，服务器会当成两次合法请求
                    # 各结算一遍，战报里就是同一个人连杀同一只 boss。
                    self.log(f'VIP boss {union_id} 仍在存活列表里，但这一轮已经出过手，'
                             f'不再重复请求，先去做别的')
                    continue
                self.log(f'VIP boss {union_id} 已出现，BEAT IT！！！')
                directly_challenge_boss_state = self._create_dicrect_challenge_boss_state(union_id, advanced_action_config)
                self.set_state(directly_challenge_boss_state)
                return
            else:
                # 去战报里查vip boss被击败的时间
                next_battle_info = self._get_next_vip_boss(vip_boss, union_id)
                if not next_battle_info:
                    # 战报拉不到时，原实现会 continue 走到 NormalBossState，
                    # 顺手把一个普通 boss 打掉、白白烧掉整整一个挑战冷却，
                    # 等于这一轮 VIP 直接报废。这里改成先原地重试几次。
                    streak = getattr(self.bot, 'vip_boss_log_fail_streak', 0) + 1
                    self.bot.vip_boss_log_fail_streak = streak
                    if streak < 3:
                        self.log(f'未找到上次vip boss被击败的时间，id: {union_id}（第{streak}/3次），'
                                 f'暂时不打普通boss，30秒后重试，避免浪费挑战冷却')
                        idle_state = StateFactory.create_idle_state(self.bot)
                        idle_state.set_idle_time(30, partial(self.set_state, StateFactory.create_vip_boss_state(self.bot)))
                        self.set_state(idle_state)
                        return
                    self.bot.vip_boss_log_fail_streak = 0
                    self.log(f'未找到上次vip boss被击败的时间，id: {union_id}，连续{streak}次失败，去处理下一个vip boss。')
                    continue
                else:
                    self.bot.vip_boss_log_fail_streak = 0
                    next_spawn_timestamp = next_battle_info['future_unixtime']
                    next_spawn_time = datetime.fromtimestamp(next_spawn_timestamp / 1000000)
                    # 战报里的时间戳是服务器时钟，本地时钟快慢要扣掉，否则算出来的倒计时整体偏
                    clock_offset = getattr(self.bot, 'server_clock_offset', 0.0) or 0.0
                    time_until_spawn = (next_spawn_time - datetime.now()).total_seconds() - clock_offset
                    seconds = int(time_until_spawn)
                    minutes, seconds = divmod(seconds, 60)
                    self.log(f"vip boss({union_id})将于{next_spawn_time}刷新，距离刷新还有{minutes}分{seconds}秒")
                    # 硬保护窗口只按"失败也锁 20 分钟"算：剩不到这么久就停手，保证
                    # 哪怕打输了也不会把冷却拖过刷新点。打死锁 60 分钟那一档是使用者
                    # 明确接受的风险（运气不好就认），所以不再提前一小时停手。
                    guard_seconds = self._vip_cooldown_guard_seconds()
                    if time_until_spawn <= 0:
                        # 刷新时刻已过：如果这一轮还没出过手，补一次（且只补一次）
                        if self._already_fired():
                            self.log(f'VIP boss {union_id} 刷新时刻已过且本轮已出手过，不再重复请求')
                            continue
                        self.log(f'VIP boss {union_id} 刷新时刻已过，立刻尝试一次')
                        self.set_state(self._create_snipe_state(union_id, advanced_action_config, next_spawn_timestamp))
                        return
                    elif time_until_spawn <= guard_seconds:
                        # 已进入保护窗口：从现在起到刷新为止，绝不碰普通 boss
                        self.log(f'VIP boss {union_id} 将在 {time_until_spawn:.0f} 秒后刷新，'
                                 f'已进入保护窗口（{guard_seconds:.0f} 秒 = 失败冷却20分钟+余量）：'
                                 f'从现在起不打任何普通 boss，专心等刷新')
                        """
                        # 想办法将PrepareBossState设定为等vip模式，一旦到时间就Dicrect或者转到VipBoss，没到时间就去做除打boss以外的事 
                        """
                        self.bot.set_next_vip_boss_spawn_timestamp(union_id, next_spawn_timestamp)
                        wait_vip_boss_state = StateFactory.create_wait_vip_boss_state(self.bot)
                        directly_challenge_boss_state = self._create_dicrect_challenge_boss_state(union_id, advanced_action_config)
                        wait_vip_boss_state.on_challenge_time_up = partial(wait_vip_boss_state.set_state, directly_challenge_boss_state)
                        self.set_state(wait_vip_boss_state)
                        return
                    else:
                        # 还在保护窗口之外，这段时间可以正常打普通 boss；
                        # 每轮结束前还会再查一次，进入窗口就会立刻切成等待
                        continue

        # 走到这里说明所有vip boss都处理过了，接下来不属于vip管辖范围了
        self.set_state(StateFactory.create_normal_boss_state(self.bot))
        # self.set_state(self.next_state)
        self.on_finish()

    def on_finish(self):
        self.log(f"已处理完VIP boss战斗，清空vip监视状态")
        self.bot.reset_waiting_vip_boss_spawn_info()
        # self.set_state(self.next_state)

    def _on_challenge_success(self):
        self.set_state(StateFactory.create_world_pvp_state(self.bot))
        self.on_finish()

    def _on_challange_failed(self):
        # 注意，这里如果直接转向普通boss，可能会触发连击，在服务器没反应过来之前重复打多次boss
        # self.set_state(StateFactory.create_normal_boss_state(self.bot))
        self.set_state(StateFactory.create_prepare_boss_state(self.bot))
        self.on_finish()

    def _create_dicrect_challenge_boss_state(self, union_id, advanced_action_config) -> 'BaseState':
        directly_challenge_boss_state = StateFactory.create_directly_challenge_boss_state(self.bot)
        if isinstance(directly_challenge_boss_state, DirectlyChallengeBossState):
            directly_challenge_boss_state.union_id = union_id
            directly_challenge_boss_state.advanced_action_config = advanced_action_config
            directly_challenge_boss_state.on_challenge_success = self._on_challenge_success
            directly_challenge_boss_state.on_challenge_failed = self._on_challange_failed
            return directly_challenge_boss_state
        else:
            raise None

    def _create_snipe_state(self, union_id, advanced_action_config, spawn_timestamp_us) -> 'BaseState':
        """刷新时刻已过时的补打：同样交给狙击状态，但时间轴已经过期，它会立刻出手一次。"""
        return StateFactory.create_vip_snipe_state(
            self.bot, union_id, advanced_action_config, spawn_timestamp_us
        )

    def _already_fired(self) -> bool:
        checker = getattr(self.bot, 'vip_snipe_already_fired_recently', None)
        return bool(checker()) if callable(checker) else False

    def _get_next_vip_boss(self, vip_boss_dict: Dict, union_id):
        # 使用BossBattleManager的get_next_vip_boss方法
        # 为vip_boss_dict添加server_url
        # 注意：这里要复制一份再添加，避免就地修改 auto_bot_config_manager 里共享的配置字典
        vip_boss_dict = dict(vip_boss_dict)
        vip_boss_dict['server_url'] = self.bot.server_config_manager.current_server_data['url']
        next_battle_info = self.bot.boss_battle_manager.get_next_vip_boss(vip_boss_dict, union_id, self.bot.battle_watcher_manager)
        return next_battle_info
