import sys
import os
import types

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# advanced_action_executor 在模块级就会 new 一个 Chrome（已知问题），
# 而 scripts.hof_auto_bot_main 会 import 它，这里用 stub 屏蔽避免导入时拉起浏览器
_stub = types.ModuleType("scripts.hof_auto_bot_main")
class _HofAutoBot:
    pass
_stub.HofAutoBot = _HofAutoBot
sys.modules["scripts.hof_auto_bot_main"] = _stub

from scripts.states.vip_boss_state import VipBossState


class _FakeLogger:
    def info(self, msg):
        pass

    def error(self, msg):
        pass

    def success(self, msg):
        pass

    def warning(self, msg):
        pass

    def debug(self, msg):
        pass


class _FakeBot:
    def __init__(self, url):
        self.server_config_manager = types.SimpleNamespace(current_server_data={'url': url})
        self.logger = _FakeLogger()
        self.boss_battle_manager = None
        self.battle_watcher_manager = None


def test_get_next_vip_boss_does_not_pollute_shared_config():
    """回归测试：vip_boss_state._get_next_vip_boss 不应就地修改传入的配置字典。

    背景：原实现直接 vip_boss_dict['server_url'] = ...，而传入的是
    auto_bot_config_manager.vip_boss_need_watch 里的同一个 dict 对象，
    会把共享配置污染掉（并让 bug 表现成"顺序依赖"）。
    """
    bot = _FakeBot('https://pim0110.com/hall/')
    state = VipBossState(bot)

    shared_vip_boss_dict = {
        'union_id': 17,
        'plan_action_id': 600170,
        'kill_cooldown_seconds': 14400,
    }
    captured = {}

    class _FakeManager:
        def get_next_vip_boss(self, vip_boss_dict, union_id, watcher):
            captured['dict'] = vip_boss_dict
            captured['union_id'] = union_id
            return {'future_unixtime': 1792581595272499}

    bot.boss_battle_manager = _FakeManager()
    bot.battle_watcher_manager = object()

    result = state._get_next_vip_boss(shared_vip_boss_dict, 17)

    assert result is not None, "应返回刷新时间信息"
    assert 'server_url' not in shared_vip_boss_dict, "共享配置字典被污染了（不应出现 server_url 字段）"
    assert captured['dict'] is not shared_vip_boss_dict, "应传入副本而不是原字典"
    assert captured['dict']['server_url'] == 'https://pim0110.com/hall/', "副本上应正确带上 server_url"
    assert captured['union_id'] == 17, "union_id 传递不正确"


if __name__ == "__main__":
    test_get_next_vip_boss_does_not_pollute_shared_config()
    print("测试通过！")
