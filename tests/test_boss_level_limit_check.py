import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.boss_battle_manager import BossBattleManager


def test_level_exceed_check_works_with_set_server_id():
    """回归测试：等级溢出检查应真正生效。

    背景：normal_boss_state._check_is_action_level_exceed_boss_limit 里
    新建了一个 BossBattleManager() 却没调 set_server_id()，导致
    character_config_path / action_config_path 都是 None，
    get_action_characters() 返回空列表，
    is_action_level_exceed_boss_limit() 恒返回 False —— 检查形同虚设。
    """
    manager = BossBattleManager()
    manager.set_server_id(1)

    # 1服的鸟毛(BOSS ID:8)等级限制是200，而动作 600080 的角色等级和是215
    result = manager.is_action_level_exceed_boss_limit('600080', 8)
    assert result is True, f"等级溢出检查应判定为True（215 > 200），实际: {result}"


def test_get_action_characters_accepts_int_action_id():
    """回归测试：action_id 传 int 时也应能匹配到动作组。

    背景：action_config_advanced.json 的 key 是字符串（"600080"），
    而 auto_bot_loop_config.json 里的 plan_action_id 是 int（600080），
    直接用 int 去查 dict 会匹配不上。
    """
    manager = BossBattleManager()
    manager.set_server_id(1)

    ids_from_str = manager.get_action_characters('600080')
    ids_from_int = manager.get_action_characters(600080)

    assert ids_from_str, "字符串 action_id 应能查到角色"
    assert ids_from_int == ids_from_str, \
        f"int 与 str 的 action_id 应等价：{ids_from_int} != {ids_from_str}"


def test_level_check_uses_current_server_config():
    """不同服务器的角色数据不同，检查应使用当前服务器的配置"""
    m1 = BossBattleManager()
    m1.set_server_id(1)
    m2 = BossBattleManager()
    m2.set_server_id(2)

    assert m1.character_config_path != m2.character_config_path, "两服应加载不同的角色配置"
    assert m1.character_config_path and os.path.exists(m1.character_config_path)
    assert m2.character_config_path and os.path.exists(m2.character_config_path)


if __name__ == "__main__":
    test_level_exceed_check_works_with_set_server_id()
    test_get_action_characters_accepts_int_action_id()
    test_level_check_uses_current_server_config()
    print("全部测试通过！")
