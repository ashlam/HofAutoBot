from scripts.hof_auto_bot_main import HofAutoBot

class BaseState:
    def __init__(self, bot: HofAutoBot):
        self.bot = bot
        self.next_state = None

    def process(self):
        raise NotImplementedError


    def get_next_state(self) -> None:
        return self.next_state

    def _vip_spawn_imminent(self) -> bool:
        """VIP boss 是否马上刷新（已进入狙击窗口）。

        是的话，任何会耗时几十秒的动作（刷小怪、打普通 boss、随机延迟）都该立刻收手，
        否则就会跨过刷新时刻，把"刷出瞬间就出手"拖成"下一次路过才出手"。
        """
        try:
            remain = self.bot.seconds_until_vip_boss_spawn()
            if remain is None:
                return False
            return remain <= self.bot.auto_bot_config_manager.vip_snipe_window_seconds
        except AttributeError:
            # 老版本 bot / 测试桩没有该接口时，按"不受影响"处理
            return False

    def _cap_idle_by_vip_spawn(self, idle_seconds: float) -> float:
        """把一次睡眠截断到 vip 刷新前 1 秒，避免一觉睡过刷新时刻。

        只剩一两秒时不截断：那时候再怎么睡都跨过刷新点了，硬截断只会让
        状态机每秒空转一次（而且这段冷却本来就没结束，打了也是白打）。
        """
        try:
            remain = self.bot.seconds_until_vip_boss_spawn()
        except AttributeError:
            return idle_seconds
        if remain is None or remain <= 2:
            return idle_seconds
        return min(idle_seconds, remain - 1)

    def on_finish(self):
        pass

    def set_state(self, state):
        self.log(f'set_state: \033[91m{self.__class__.__name__} -> \033[93m{state.__class__.__name__}\033[37m')
        self.bot.switch_to_next_state(state)

    def log(self, msg):
        self.bot.logger.info(msg) 