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
                self.log(f'VIP boss {union_id} 已出现，BEAT IT！！！')
                directly_challenge_boss_state = self._create_dicrect_challenge_boss_state(union_id, advanced_action_config)
                self.set_state(directly_challenge_boss_state)
                return
            else:
                # 去战报里查vip boss被击败的时间
                next_battle_info = self._get_next_vip_boss(vip_boss, union_id)
                if not next_battle_info:
                    self.log(f'未找到上次vip boss被击败的时间，id: {union_id} ，没有办法处理boss({union_id})，去处理下一个vip boss。')
                    continue
                else:
                    next_spawn_timestamp = next_battle_info['future_unixtime']
                    next_spawn_time = datetime.fromtimestamp(next_spawn_timestamp / 1000000)
                    time_until_spawn = (next_spawn_time - datetime.now()).total_seconds()
                    seconds = int(time_until_spawn)
                    minutes, seconds = divmod(seconds, 60)
                    self.log(f"vip boss({union_id})将于{next_spawn_time}刷新，距离刷新还有{minutes}分{seconds}秒")
                    # TODO: 这里有过期的风险，会一直等
                    wait_time = min(self.bot.auto_bot_config_manager.challenge_boss_cooldown_seconds, max(0, time_until_spawn))
                    self.log(f"{'将于%.2f秒后暂停' % wait_time if wait_time > 0 else '已暂停' }挑战普通boss行为，专心等vip")
                    if time_until_spawn <= 0:
                        # 说明可能过期了，死马当活马医，试着直接打一下
                        directly_challenge_boss_state = self._create_dicrect_challenge_boss_state(union_id, advanced_action_config)
                        self.set_state(directly_challenge_boss_state)
                        return
                    elif time_until_spawn <= wait_time:
                        # 等待时间较少（20分钟内）
                        self.log(f'VIP boss {union_id} 将在 {time_until_spawn} 秒后刷新。注意不要打其他Boss，去干别的。')
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
                        # 20分钟以上，看看有没有其他vip boss
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
            directly_challenge_boss_state.on_challage_success = self._on_challenge_success
            directly_challenge_boss_state.on_challenge_failed = self._on_challange_failed
            return directly_challenge_boss_state
        else:
            raise None

    def _get_next_vip_boss(self, vip_boss_dict: Dict, union_id):
        # 使用BossBattleManager的get_next_vip_boss方法
        # 为vip_boss_dict添加server_url
        vip_boss_dict['server_url'] = self.bot.server_config_manager.current_server_data['url']
        next_battle_info = self.bot.boss_battle_manager.get_next_vip_boss(vip_boss_dict, union_id, self.bot.battle_watcher_manager)
        return next_battle_info
