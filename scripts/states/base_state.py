import time

from scripts.hof_auto_bot_main import HofAutoBot

# 确认挑战结果时的轮询节奏（测试里会改小，避免拖慢用例）
CONFIRM_FIRST_WAIT_SECONDS = 0.8
CONFIRM_INTERVAL_SECONDS = 0.8
CONFIRM_ATTEMPTS = 6

class BaseState:
    def __init__(self, bot: HofAutoBot):
        self.bot = bot
        self.next_state = None

    def process(self):
        raise NotImplementedError

    def _confirm_challenge_result(self, union_id, attempts=None, interval=None, first_wait=None):
        """挑战请求发出去之后，确认服务端到底受理没有。

        为什么不能立刻读一次就下结论：实测（2服 2026-10-27 17:00:11.783 与
        17:00:12.134）同一只 boss 前后两次读取结论完全相反——第一次"还在、无冷却"，
        0.35 秒后"已消失、冷却 3599 秒"。那一次击杀是人工手动打的，正好说明
        请求发出去之后服务端写库有可见延迟，只看第一次会把"打成了"判成"没打成"，
        上层于是又走"没打成"的分支，白折腾一轮，甚至补发第二次请求。

        这里只读页面、不发任何挑战请求，所以多轮询几次没有副作用。
        """
        if attempts is None:
            attempts = CONFIRM_ATTEMPTS
        if interval is None:
            interval = CONFIRM_INTERVAL_SECONDS
        if first_wait is None:
            first_wait = CONFIRM_FIRST_WAIT_SECONDS
        if first_wait > 0:
            time.sleep(first_wait)

        alive_ids = []
        for i in range(max(1, attempts)):
            try:
                self.bot._update_info_from_hunt_page()
            except Exception as e:  # 页面读取失败不该反过来判成"打成了"
                self.log(f'挑战结果确认：读取boss信息失败（{type(e).__name__}），继续重试')

            cooldown = getattr(self.bot, 'challenge_next_cooldown', 0) or 0
            alive_ids = getattr(self.bot, 'all_alived_boss_ids', None) or []
            alive_ids = [str(x) for x in alive_ids]
            boss_gone = str(union_id) not in alive_ids

            if cooldown > 0:
                self.log(f'挑战结果确认：已进入冷却（{cooldown}秒），第{i + 1}次读取确认受理')
                return True
            # "boss 不在存活列表"只有在页面确实解析出了别的 boss 时才算证据，
            # 否则可能是页面没解析出来（登录页/网络错误），不能据此报成功
            if boss_gone and alive_ids:
                self.log(f'挑战结果确认：boss({union_id}) 已不在存活列表，第{i + 1}次读取确认受理')
                return True

            if i < attempts - 1:
                time.sleep(interval)

        self.log(f'挑战结果确认：{attempts}次读取（约{attempts * interval + first_wait:.1f}秒）'
                 f'仍未见冷却或boss消失，按未受理处理')
        return False


    def get_next_state(self) -> None:
        return self.next_state

    def _mark_boss_checked(self):
        """告诉看门狗：boss 主线刚刚被检查过（每次读完 hunt 页就该报一次）。"""
        watchdog = getattr(self.bot, 'boss_check_watchdog', None)
        marker = getattr(watchdog, 'mark_checked', None)
        if callable(marker):
            try:
                marker()
            except Exception:
                pass

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