from .base_state import BaseState
from .state_factory import StateFactory

class NormalStageState(BaseState):
    def process(self):
        self.log('开始处理普通关卡')
        threshold = self.bot.auto_bot_config_manager.keep_stamnia_for_normal_stage
        executed = 0
        for stage in self.bot.auto_bot_config_manager.normal_stage_loop_order:
            # 每场小怪前都确认一次：vip boss 马上要刷新就别打了，这一批打完可能就错过刷新瞬间
            if self._vip_spawn_imminent():
                self.log('VIP boss 即将刷新，中断本批小怪，回去守刷新时刻')
                self.next_state = StateFactory.create_prepare_boss_state(self.bot)
                self.on_finish()
                return
            self.bot._update_info_from_hunt_page()
            player_stamina = self.bot.battle_watcher_manager.get_player_stamina()
            if (player_stamina < threshold):
                self.log(f'体力不足打小怪（{player_stamina} < {threshold}），去看看boss...')
                break
            advanced_action_config = self.bot.server_config_manager.all_action_config_by_server.get(f"{stage['plan_action_id']}")
            if advanced_action_config:
                self.log(f'进行普通小怪挑战：{stage["plan_action_id"]}')
                self.bot.action_manager.execute_advanced_action(self.bot.driver, advanced_action_config)
                executed += 1

        if executed == 0:
            # 一场都没打成：以前这里回到 PrepareStage，而 PrepareStage 用的是"限时关卡"
            # 的体力阈值（比普通关卡低），于是出现
            # PrepareStage -> TimeLimitedStage -> NormalStage -> PrepareStage 的死循环，
            # 13 秒一圈、什么都不做，boss 一次都不会被检查（实测卡了 5 分钟，
            # VIP boss 17 就站在存活列表里没人打）。这里直接去看 boss。
            self.log('本轮一场小怪都没打成，转去检查boss')
        else:
            # 打完了也要回 boss 主线，而不是原地转回 PrepareStage。
            # 小怪循环是闭环：PrepareStage/TimeLimited/Pvp/WorldPvp 之间来回走，
            # 唯一通向 boss 的出口是"体力低于阈值"。一旦体力刚好够、又撞上限时关卡
            # 的时间窗（每小时 50-59 分），这个闭环就会一直空转，boss 一次都不看，
            # 而 VIP boss 恰好是在整点前后刷新的。
            self.log('本批小怪打完，回boss主线核对一次（避免久不看boss错过刷新）')
        self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)
