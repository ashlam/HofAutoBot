#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from scripts.boss_battle_manager import BossBattleManager

def test_boss_battle_manager():
    # 创建BossBattleManager实例
    manager = BossBattleManager()
    
    # 设置服务器ID
    manager.set_server_id(1)  # 使用server_01
    
    # 测试获取Boss等级限制
    boss_id = 0  # 黑龍軍團
    level_limit = manager.get_boss_level_limit(boss_id)
    print(f"Boss(ID:{boss_id})的等级限制为: {level_limit}")
    
    # 测试获取角色等级
    character_id = "1340513102982626"  # 小熊熊
    level = manager.get_character_level(character_id)
    print(f"角色(ID:{character_id})的等级为: {level}")
    
    # 测试获取动作中的角色ID列表
    action_id = "600000"  # 一服黑龙
    character_ids = manager.get_action_characters(action_id)
    print(f"动作(ID:{action_id})中包含的角色ID: {character_ids}")
    
    # 测试计算角色等级之和是否超过Boss等级限制
    result = manager.is_action_level_exceed_boss_limit(action_id, boss_id)
    print(f"动作(ID:{action_id})中角色等级之和是否超过Boss(ID:{boss_id})等级限制: {result}")
    
    # 测试另一个动作
    action_id = "600080"  # 一服鸟毛
    result = manager.is_action_level_exceed_boss_limit(action_id, 8)  # 鳥巢
    print(f"动作(ID:{action_id})中角色等级之和是否超过Boss(ID:8)等级限制: {result}")

if __name__ == "__main__":
    test_boss_battle_manager()