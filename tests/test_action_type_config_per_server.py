import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.advanced_action_executor import AdvancedActionManager


def test_action_type_config_uses_given_server():
    """回归测试：AdvancedActionManager 应按 server_id 加载对应服务器的动作类型配置。

    背景：原实现硬编码读取 configs/server_01/action_type_config.json，
    导致2服（测试服）一直在用1服的等待时间参数。而两服的配置实际不同：
        click_main_menu_for_town : 1服 0/3000  vs  2服 2000/3000
        click_sub_menu_stage     : 1服 1000/200 vs 2服 1000/800
        click_sub_menu_boss      : 1服 0/200   vs  2服 0/100
        click_button_start_battle: 1服 0/1000  vs  2服 0/100
    """
    mgr1 = AdvancedActionManager(server_id=1)
    mgr2 = AdvancedActionManager(server_id=2)

    cfg1 = mgr1.get_action_type_config('click_sub_menu_stage')
    cfg2 = mgr2.get_action_type_config('click_sub_menu_stage')

    assert cfg1.get('idle_after_operation') == 200, f"1服参数不对: {cfg1}"
    assert cfg2.get('idle_after_operation') == 800, f"2服参数不对（仍在用1服的）: {cfg2}"

    cfg1 = mgr1.get_action_type_config('click_button_start_battle')
    cfg2 = mgr2.get_action_type_config('click_button_start_battle')
    assert cfg1.get('idle_after_operation') == 1000, f"1服参数不对: {cfg1}"
    assert cfg2.get('idle_after_operation') == 100, f"2服参数不对（仍在用1服的）: {cfg2}"


def test_default_server_is_one():
    """未指定 server_id 时默认用1服（保持向后兼容）"""
    mgr = AdvancedActionManager()
    cfg = mgr.get_action_type_config('click_sub_menu_stage')
    assert cfg.get('idle_after_operation') == 200, f"默认应加载1服配置: {cfg}"


def test_invalid_server_id_falls_back_gracefully():
    """服务器配置缺失时应回退到默认配置，而不是抛异常"""
    mgr = AdvancedActionManager(server_id=99)
    # 不应崩溃，且应仍能返回某种默认配置
    cfg = mgr.get_action_type_config('click_main_menu')
    assert isinstance(cfg, dict), f"应返回dict，实际: {type(cfg)}"


if __name__ == "__main__":
    test_action_type_config_uses_given_server()
    test_default_server_is_one()
    test_invalid_server_id_falls_back_gracefully()
    print("全部测试通过！")
