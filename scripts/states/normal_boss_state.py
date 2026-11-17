from functools import partial
import time

from scripts.states.directly_challenge_boss_state import DirectlyChallengeBossState
from .base_state import BaseState
from .state_factory import StateFactory
import random
from datetime import datetime

class NormalBossState(BaseState):
    def process(self):
        """处理普通boss战斗
        Returns:
            str: 下一个游戏状态
        """
        # 先刷新页面获取最新状态
        self.bot._update_info_from_hunt_page()

        standard_idle_seconds = self.bot.auto_bot_config_manager.idle_seconds_for_challenge_boss
        # 检查冷却时间
        if self.bot.challenge_next_cooldown > standard_idle_seconds:
            # 冷却时间还长，去干别的
            idle_state = StateFactory.create_idle_state(self.bot)
            idle_state.set_idle_time(standard_idle_seconds, partial(self.set_state, StateFactory.create_world_pvp_state(self.bot)))
            self.next_state = idle_state
        elif self.bot.challenge_next_cooldown > 0:
            # 冷却时间比较短，等一等然后转到prepare boss
            self.log(f'Boss挑战冷却中，还剩{self.bot.challenge_next_cooldown}秒，等待冷却结束')
            idle_state = StateFactory.create_idle_state(self.bot)
            idle_state.set_idle_time(standard_idle_seconds, partial(self.set_state, StateFactory.create_prepare_boss_state(self.bot)))
            self.next_state = idle_state
        else:
            self.log('没有冷却，开刷普通boss')
            # 由于刚发现游戏版规有禁止按键精灵之类的辅助规则，需要加一些随机延迟来避免太过规律
            # 先丢个随机数看本轮是否要故意delay
            next_vip_spawn_seconds = 0
            for vip_boss in self.bot.auto_bot_config_manager.vip_boss_need_watch:
                next_vip_union_id = vip_boss['union_id']
                next_vip_boss_battle_info = self.bot.boss_battle_manager.get_next_vip_boss(vip_boss, next_vip_union_id, self.bot.battle_watcher_manager)
                if next_vip_boss_battle_info:
                    self.log(f'下一个vip boss是{next_vip_union_id}')
                    next_spawn_timestamp = next_vip_boss_battle_info['future_unixtime']
                    next_spawn_time = datetime.fromtimestamp(next_spawn_timestamp / 1000000)
                    # 战报时间戳是服务器时钟，本地时钟的快慢要扣掉
                    clock_offset = getattr(self.bot, 'server_clock_offset', 0.0) or 0.0
                    time_until_spawn = (next_spawn_time - datetime.now()).total_seconds() - clock_offset
                    next_vip_spawn_seconds = int(time_until_spawn)
                    break
            # 硬保护窗口只按"失败也锁 20 分钟"算：剩不到这么久就不打，保证输了也不会
            # 撞上刷新点。打死锁 60 分钟那一档是使用者明确接受的风险（运气不好就认），
            # 所以只在这条线以内额外打一句风险提示，不提前一小时停手。
            guard_seconds = self._vip_cooldown_guard_seconds()
            risk_seconds = self._vip_kill_risk_seconds()
            safe_budget = None
            if next_vip_spawn_seconds > 0:
                safe_budget = max(0, next_vip_spawn_seconds - guard_seconds)
                if next_vip_spawn_seconds <= risk_seconds:
                    self.log(f'风险提示：距vip boss刷新只剩{next_vip_spawn_seconds}秒，够一次失败冷却但不够'
                             f'一次击杀冷却（{risk_seconds:.0f}秒）——这一把照打；若打死，本轮vip就错过了')
            roll_result = random.randint(0, 100)
            elapsed = 0.0
            if roll_result <= self.bot.auto_bot_config_manager.challenge_boss_delay_rate:
                # 再决定要delay多少秒
                delay_seconds = random.randint(1, self.bot.auto_bot_config_manager.challenge_boss_delay_seconds_limit)
                self.log(f'\033[91m({roll_result})本轮有delay {delay_seconds} 秒\033[37m')
                if safe_budget is not None:
                    delay_seconds = min(delay_seconds, safe_budget)
                if delay_seconds > 0:
                    delay_start = time.monotonic()
                    time.sleep(delay_seconds)
                    elapsed = time.monotonic() - delay_start
                # delay完后再刷下boss信息
                self.bot._update_info_from_hunt_page()
            else:
                self.log(f'\033[91m({roll_result})本轮没有delay\033[37m')

            # 延迟、刷新页面之后重新确认一次：现在还该不该打这只普通boss
            if next_vip_spawn_seconds > 0:
                if self._vip_spawn_imminent():
                    self.log('已进入vip狙击窗口，放弃打普通boss，交给vip流程')
                    self.next_state = StateFactory.create_prepare_boss_state(self.bot)
                    self.on_finish()
                    return
                remain = next_vip_spawn_seconds - elapsed
                if remain < guard_seconds:
                    idle_seconds = max(30, remain - guard_seconds + 1)
                    self.log(f'距vip boss刷新只剩{remain:.0f}秒，连一次失败冷却都不够'
                             f'（{guard_seconds:.0f}秒 = 失败20分钟+余量），此时打普通boss'
                             f'无论输赢都会把冷却拖过刷新，先等{idle_seconds:.0f}秒')
                    idle_state = StateFactory.create_idle_state(self.bot)
                    idle_state.set_idle_time(
                        idle_seconds,
                        partial(self.set_state, StateFactory.create_prepare_boss_state(self.bot)),
                    )
                    self.next_state = idle_state
                    self.on_finish()
                    return

            is_challenged = False
            for boss in self.bot.auto_bot_config_manager.normal_boss_loop_order:
                if boss['union_id'] not in self.bot.battle_watcher_manager.get_all_alive_boss():
                    self.log(f'普通boss {boss["union_id"]} 未出现，跳过')
                    continue
                else:
                    self.log(f'普通boss {boss["union_id"]} 已出现，尝试处理')
                    # 闸门还没放行就跳过这一只：它很可能是刚被 VIP 狙击打过、
                    # 或者别的入口刚发过请求。等下去毫无意义，清单里还有别的 boss 可打。
                    guard_wait = self._boss_guard_wait_seconds(boss['union_id'])
                    if guard_wait > 0:
                        self.log(f'普通boss {boss["union_id"]} 距上次挑战请求不足最小间隔'
                                 f'（还差{guard_wait:.0f}秒），这只跳过，先打下一只')
                        continue
                    # 执行boss战斗动作
                    action = self.bot.server_config_manager.all_action_config_by_server.get(f"{boss['plan_action_id']}")
                    # 检查等级是否溢出
                    if self._check_is_action_level_exceed_boss_limit(boss['plan_action_id'], boss['union_id']):
                        self.log(f'角色总等级溢出，无法处理boss({boss["union_id"]})，跳过。')
                        continue
                    directly_challenge_boss_state = StateFactory.create_directly_challenge_boss_state(self.bot)
                    if isinstance(directly_challenge_boss_state, DirectlyChallengeBossState):
                        directly_challenge_boss_state.union_id = boss['union_id']
                        directly_challenge_boss_state.advanced_action_config = action
                        directly_challenge_boss_state.on_challenge_success = self._on_challenge_normal_boss_success
                        directly_challenge_boss_state.on_challenge_failed = self._on_challenge_normal_boss_failed
                        self.next_state = directly_challenge_boss_state
                        is_challenged = True
                        break
            # 如果没有可以打的boss，进入PVP状态 
            if not is_challenged:
                self.log(f'没有普通boss需要处理, 普通boss清单：{self.bot.auto_bot_config_manager.normal_boss_loop_order}')
                self.next_state = StateFactory.create_world_pvp_state(self.bot)
            
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)

    
    def _on_challenge_normal_boss_success(self):
        self.log('普通boss挑战成功')
        self.next_state = StateFactory.create_world_pvp_state(self.bot)
        self.on_finish()
    
    def _on_challenge_normal_boss_failed(self):
        self.log('普通boss挑战失败，重新准备一次')
        self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        self.on_finish()

    def _check_is_action_level_exceed_boss_limit(self, action_id, boss_id):
        # 复用 bot 上已 set_server_id 的 manager，否则角色/动作配置路径为None，检查会失效
        result = self.bot.boss_battle_manager.is_action_level_exceed_boss_limit(action_id, boss_id)
        self.log(f"动作(ID:{action_id})中角色等级之和是否超过Boss(ID:{boss_id})等级限制: {result}")
        return result