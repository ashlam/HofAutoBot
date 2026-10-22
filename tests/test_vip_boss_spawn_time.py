import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.boss_battle_manager import BossBattleManager
from scripts.battle_watcher_manager import BattleWatcherManager

SERVER_URLS = {1: 'https://pim0110.com/hall/?ulog', 2: 'https://pim0110.com/hall02/?ulog'}


def _vip_boss_dict():
    """模拟 auto_bot_loop_config.json 中 vip_boss_need_watch 的一条条目
    注意：真实配置里【没有】server_url 字段
    """
    return {
        'union_id': 17,
        'plan_action_id': 600170,
        'quick_action_id': 600171,
        'kill_cooldown_seconds': 14400,
    }


def _mock_watcher(captured):
    """构造假的 BattleWatcherManager，记录传入的url并返回固定时间"""
    watcher = BattleWatcherManager()

    def mock_get_boss_next_battle_real_time(union_id, seconds_to_add, url):
        captured.update({'union_id': union_id, 'seconds_to_add': seconds_to_add, 'url': url})
        return {
            'original': '2026-10-21 15:19:55.272499',
            'future': '2026-10-21 19:19:55.272499',
            'original_unixtime': 1792567195272499,
            'future_unixtime': 1792581595272499,
        }

    watcher.get_boss_next_battle_real_time = mock_get_boss_next_battle_real_time
    return watcher


def test_get_next_vip_boss_without_server_url_uses_manager_server():
    """回归测试：vip_boss_need_watch 里没有 server_url 时，
    get_next_vip_boss 应回退到 manager 自己所属服务器的URL，而不是返回None。

    复现场景：normal_boss_state.py 调用 get_next_vip_boss 时未注入 server_url，
    导致 VIP BOSS 刷新时间永远取不到（next_vip_spawn_seconds 恒为 0）。
    """
    for server_id, expected_url in SERVER_URLS.items():
        manager = BossBattleManager()
        manager.set_server_id(server_id)

        captured = {}
        watcher = _mock_watcher(captured)

        result = manager.get_next_vip_boss(_vip_boss_dict(), 17, watcher)

        assert result is not None, f"{server_id}服 get_next_vip_boss 返回了 None，VIP刷新时间取不到"
        assert result['future_unixtime'] == 1792581595272499, "future_unixtime值不正确"
        assert captured.get('url') == expected_url, \
            f"{server_id}服战报URL不正确: {captured.get('url')}"


def test_get_next_vip_boss_explicit_server_url_still_wins():
    """显式传入的 server_url 优先级最高（vip_boss_state 现有行为不能被破坏）"""
    manager = BossBattleManager()
    manager.set_server_id(1)

    captured = {}
    watcher = _mock_watcher(captured)

    vip_boss_dict = _vip_boss_dict()
    vip_boss_dict['server_url'] = 'https://pim0110.com/hall02/'

    result = manager.get_next_vip_boss(vip_boss_dict, 17, watcher)

    assert result is not None, "显式 server_url 时不应返回 None"
    assert captured.get('url') == 'https://pim0110.com/hall02/?ulog', \
        f"显式 server_url 未生效: {captured.get('url')}"


def test_get_next_vip_boss_without_server_id_returns_none():
    """未 set_server_id 且未提供 server_url 时，仍应返回 None（无法猜服务器）"""
    manager = BossBattleManager()

    captured = {}
    watcher = _mock_watcher(captured)

    result = manager.get_next_vip_boss(_vip_boss_dict(), 17, watcher)

    assert result is None, "既无 server_id 又无 server_url 时不应返回有效结果"
    assert not captured, "不应发起战报请求"


if __name__ == "__main__":
    test_get_next_vip_boss_without_server_url_uses_manager_server()
    test_get_next_vip_boss_explicit_server_url_still_wins()
    test_get_next_vip_boss_without_server_id_returns_none()
    print("全部测试通过！")
