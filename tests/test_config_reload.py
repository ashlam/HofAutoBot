# -*- coding: utf-8 -*-
"""热重载（CLI 的 c 命令 / 恢复时的自动重载）回归测试。

背景：挂机中按 c 重载配置表，改了 auto_bot_loop_config.json 与
action_type_config.json 却要重启进程才生效。原因是重载只替换了
auto_bot_loop_config / 动作组配置，动作类型配置被 AdvancedActionManager
缓存在构造时；另外发呆状态一觉睡到底，重载后在下一轮状态切换前看不到变化。
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.server_config_manager import ServerConfigManager
from scripts.states.idle_state import IdleState


def _load_real_bot_class():
    """加载真实的 HofAutoBot。

    其它测试文件会把 scripts.hof_auto_bot_main 替换成桩模块（避免拉起 selenium），
    这里按文件路径单独加载一份真实实现，不受 sys.modules 里的桩影响。
    """
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'scripts', 'hof_auto_bot_main.py',
    )
    spec = importlib.util.spec_from_file_location('_hof_auto_bot_main_real', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HofAutoBot


def _write_configs(cfg_dir):
    loop_config = {
        "challenge_boss_cooldown_seconds": 1200,
        "idle_seconds_for_challenge_boss": 30,
        "vip_snipe_commit_offset_ms": 0,
        "normal_boss_loop_order": [{"union_id": 12, "plan_action_id": 600121}],
        "vip_boss_need_watch": [],
    }
    action_config = {
        "600121": {"name": "boss12", "actions": []},
    }
    (cfg_dir / "auto_bot_loop_config.json").write_text(
        json.dumps(loop_config, ensure_ascii=False), encoding="utf-8")
    (cfg_dir / "action_config_advanced.json").write_text(
        json.dumps(action_config, ensure_ascii=False), encoding="utf-8")


def _make_bot(tmp_path):
    cfg_dir = tmp_path / "server_01"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    _write_configs(cfg_dir)

    # 只借 ServerConfigManager 的两个私有加载方法，绕过真实 server_address.json
    manager = ServerConfigManager.__new__(ServerConfigManager)
    manager.current_server_id = 1
    manager.current_server_data = {
        "id": 1,
        "config_path": str(cfg_dir),
        "auto_bot_loop_config_path": "auto_bot_loop_config.json",
    }
    manager.all_action_config_by_server = None
    manager.auto_bot_config = None

    bot = _load_real_bot_class()()
    bot.server_config_manager = manager
    bot.boss_battle_manager = None
    return bot, cfg_dir


def test_reload_applies_loop_config_and_action_config():
    tmp_path = Path(tempfile.mkdtemp(prefix='hof_reload_'))
    bot, cfg_dir = _make_bot(tmp_path)
    bot.reload_configs()
    assert bot.auto_bot_config_manager.idle_seconds_for_challenge_boss == 30
    assert list(bot.server_config_manager.all_action_config_by_server) == ["600121"]

    # 用户改了配置表并保存
    loop_path = cfg_dir / "auto_bot_loop_config.json"
    data = json.loads(loop_path.read_text(encoding="utf-8"))
    data["idle_seconds_for_challenge_boss"] = 77
    data["normal_boss_loop_order"] = [{"union_id": 25, "plan_action_id": 700000}]
    loop_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (cfg_dir / "action_config_advanced.json").write_text(
        json.dumps({"700000": {"name": "boss25", "actions": []}}, ensure_ascii=False),
        encoding="utf-8")

    epoch_before = bot.config_reload_epoch
    summary = bot.reload_configs()

    assert bot.auto_bot_config_manager.idle_seconds_for_challenge_boss == 77
    assert "700000" in bot.server_config_manager.all_action_config_by_server
    assert bot.config_reload_epoch == epoch_before + 1
    assert summary["normal_boss"] == [25]
    assert summary["action_groups"] == 1
    assert os.path.abspath(summary["path"]) == os.path.abspath(str(loop_path))
    shutil.rmtree(tmp_path, ignore_errors=True)


def test_reload_rebuilds_action_manager_so_action_type_config_refreshes():
    tmp_path = Path(tempfile.mkdtemp(prefix='hof_reload_'))
    bot, _ = _make_bot(tmp_path)
    bot.reload_configs()
    old_manager = bot.action_manager
    bot.reload_configs()
    # 动作类型（每个动作前后的等待毫秒数）缓存要在新实例里，否则只能重启生效
    assert bot.action_manager is not old_manager
    assert bot.action_manager.server_id == 1
    shutil.rmtree(tmp_path, ignore_errors=True)


class _StubLogger:
    def info(self, *args, **kwargs):
        pass


class _StubBot:
    def __init__(self):
        self.is_finished = False
        self.config_reload_epoch = 0
        self.logger = _StubLogger()
        self.switched = None

    def switch_to_next_state(self, state):
        self.switched = state


def test_idle_state_wakes_up_when_config_is_reloaded():
    bot = _StubBot()
    idle = IdleState(bot)
    fired = []

    def _callback():
        fired.append(time.monotonic())

    idle.set_idle_time(10, _callback)
    threading.Timer(0.3, lambda: setattr(bot, "config_reload_epoch", 1)).start()

    started = time.monotonic()
    idle.process()
    elapsed = time.monotonic() - started

    assert elapsed < 3, f"重载后发呆应在 0.5 秒内醒来，实际 {elapsed:.1f} 秒"
    assert fired, "提前醒来后仍然要执行回调，否则状态机会卡死在发呆"


def test_idle_state_sleeps_full_time_when_config_untouched():
    bot = _StubBot()
    idle = IdleState(bot)
    fired = []
    idle.set_idle_time(0.6, lambda: fired.append(True))

    started = time.monotonic()
    idle.process()
    elapsed = time.monotonic() - started

    assert elapsed >= 0.55
    assert fired


def test_usr1_flag_reloads_before_next_step():
    """后台跑的进程 stdin 拿不到，靠 SIGUSR1 置位后由主循环重载。"""
    from scripts.start_up_cli import CLIBotRunner

    calls = []

    class _Bot:
        is_finished = False

        def __init__(self):
            self.steps = 0

        def run_once(self):
            self.steps += 1
            if self.steps >= 3:
                self.is_finished = True

        def reload_configs(self):
            calls.append(self.steps)
            return None

    bot = _Bot()
    runner = CLIBotRunner(bot)
    runner.input_thread = threading.Thread(target=lambda: None)  # 别去读测试的 stdin
    runner.reload_requested.set()

    runner.run()

    assert calls == [0], f"应在第一步之前重载一次，实际 {calls}"
    assert bot.steps == 3


def test_request_reload_runs_immediately():
    """c 命令和 SIGUSR1 都走 request_reload：当场重载，不等主循环下一步。"""
    from scripts.start_up_cli import CLIBotRunner

    class _Bot:
        is_finished = False

        def __init__(self):
            self.reloads = 0

        def reload_configs(self):
            self.reloads += 1
            return None

    bot = _Bot()
    runner = CLIBotRunner(bot)

    runner.request_reload()

    assert bot.reloads == 1
    assert not runner.reload_requested.is_set(), "当场重载成功就不该再留待办给主循环"


def test_request_reload_defers_when_another_reload_is_running():
    """正在重载时不能并发重入，只置位让主循环补做。"""
    from scripts.start_up_cli import CLIBotRunner

    class _Bot:
        is_finished = False

        def reload_configs(self):
            raise AssertionError("锁被占时不该重载")

    runner = CLIBotRunner(_Bot())
    runner._reload_lock.acquire()
    try:
        runner.request_reload()
    finally:
        runner._reload_lock.release()

    assert runner.reload_requested.is_set()


if __name__ == "__main__":
    test_reload_applies_loop_config_and_action_config()
    test_reload_rebuilds_action_manager_so_action_type_config_refreshes()
    test_idle_state_wakes_up_when_config_is_reloaded()
    test_idle_state_sleeps_full_time_when_config_untouched()
    test_usr1_flag_reloads_before_next_step()
    test_request_reload_runs_immediately()
    test_request_reload_defers_when_another_reload_is_running()
    print("all reload tests passed")
