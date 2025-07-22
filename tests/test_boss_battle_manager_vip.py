import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.boss_battle_manager import BossBattleManager
from scripts.battle_watcher_manager import BattleWatcherManager

def test_get_next_vip_boss():
    # 创建BossBattleManager和BattleWatcherManager实例
    boss_battle_manager = BossBattleManager()
    battle_watcher_manager = BattleWatcherManager()
    
    # 创建一个模拟的vip_boss_dict
    vip_boss_dict = {
        'union_id': 12345,  # 假设的Boss ID
        'server_url': 'http://example.com',  # 假设的服务器URL
        'kill_cooldown_seconds': 3600  # 假设的冷却时间（1小时）
    }
    
    # 模拟BattleWatcherManager的get_boss_next_battle_real_time方法
    # 这里我们需要使用猴子补丁来模拟方法的返回值
    original_method = battle_watcher_manager.get_boss_next_battle_real_time
    
    try:
        # 使用猴子补丁替换方法
        def mock_get_boss_next_battle_real_time(union_id, seconds_to_add, url):
            print(f"模拟调用get_boss_next_battle_real_time: union_id={union_id}, seconds_to_add={seconds_to_add}, url={url}")
            # 返回一个模拟的时间信息字典
            return {
                'original': '2023-01-01 12:00:00.000000',
                'future': '2023-01-01 13:00:00.000000',
                'original_unixtime': 1672574400000000,  # 假设的时间戳
                'future_unixtime': 1672578000000000  # 假设的未来时间戳
            }
        
        # 替换方法
        battle_watcher_manager.get_boss_next_battle_real_time = mock_get_boss_next_battle_real_time
        
        # 调用被测试的方法
        result = boss_battle_manager.get_next_vip_boss(vip_boss_dict, vip_boss_dict['union_id'], battle_watcher_manager)
        
        # 验证结果
        print("测试结果:")
        print(json.dumps(result, indent=2))
        
        # 检查结果是否符合预期
        assert result is not None, "get_next_vip_boss返回了None"
        assert 'future_unixtime' in result, "结果中缺少future_unixtime字段"
        assert result['future_unixtime'] == 1672578000000000, "future_unixtime值不正确"
        
        print("测试通过！")
        return True
    finally:
        # 恢复原始方法
        battle_watcher_manager.get_boss_next_battle_real_time = original_method

if __name__ == "__main__":
    test_get_next_vip_boss()