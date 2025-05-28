import unittest
from unittest.mock import MagicMock, patch
from selenium.webdriver.common.by import By
from scripts.advanced_element_finder import AdvancedElementFinderFactory
from scripts.advanced_action_executor import AdvancedActionManager
import json
import os

class TestAdvancedActionConfig(unittest.TestCase):
    def setUp(self):
        self.driver = MagicMock()
        self.element = MagicMock()
        self.driver.find_element.return_value = self.element
        self.driver.find_elements = MagicMock()
        
        # 读取配置文件
        config_path = os.path.join(os.path.dirname(__file__), '../configs/server_01/action_config_advanced.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            
        self.action_manager = AdvancedActionManager()

    def test_adventure_action_group(self):
        """测试'点一次冒险->伟大航路'动作组"""
        action_group = self.config['1']
        print(f"\n测试动作组: {action_group['name']}")
        print(f"动作组说明: {action_group.get('note', '')}")
        print("匹配源文件: source_code_hunt_page.htm")
        print("动作执行顺序:")
        
        # 测试第一个动作：点击冒险菜单
        action1 = action_group['actions'][0]
        self.assertEqual(action1['trigger_type'], 'click_main_menu')
        self.assertEqual(action1['value'], 'hunt')
        # 设置find_elements返回值
        self.driver.find_elements.return_value = [self.element]
        self.action_manager.execute_action(self.driver, action1)
        self.driver.find_elements.assert_called_with(
            'xpath', "//a[contains(@onclick, 'hunt')]"
        )
        print(f"\n1. 主菜单点击动作:")
        print(f"- 动作类型: {action1['trigger_type']}")
        print(f"- 动作值: {action1['value']}")
        print(f"- 匹配XPath: //a[contains(@onclick, 'hunt')]")
        print(f"- 匹配到的元素数量: {len(self.driver.find_elements.return_value)}")
        
        # 测试第二个动作：点击伟大航路
        action2 = action_group['actions'][1]
        self.assertEqual(action2['trigger_type'], 'click_sub_menu_stage')
        self.assertEqual(action2['value'], 'common=ocean1')
        self.action_manager.execute_action(self.driver, action2)
        self.driver.find_elements.assert_called_with(
            'xpath', "//a[contains(@onclick, 'common=ocean1')]"
        )
        print(f"\n2. 子菜单选择动作:")
        print(f"- 动作类型: {action2['trigger_type']}")
        print(f"- 动作值: {action2['value']}")
        print(f"- 匹配XPath: //a[contains(@onclick, 'common=ocean1')]")
        print(f"- 匹配到的元素数量: {len(self.driver.find_elements.return_value)}")
        
        # 测试第三个动作：点击战斗按钮
        action3 = action_group['actions'][2]
        self.assertEqual(action3['trigger_type'], 'click_button_start_battle')
        self.assertEqual(action3['value'], 'monster_battle')
        self.action_manager.execute_action(self.driver, action3)
        print(f"\n3. 战斗按钮点击动作:")
        print(f"- 动作类型: {action3['trigger_type']}")
        print(f"- 动作值: {action3['value']}")
        print(f"- 匹配到的元素数量: {len(self.driver.find_elements.return_value)}")

    def test_boss_action_group(self):
        """测试'二服炫风'动作组"""
        action_group = self.config['800170']
        print(f"\n测试动作组: {action_group['name']}")
        print(f"动作组说明: {action_group.get('note', '')}")
        print("匹配源文件: source_code_select_character_page.htm")
        print("动作执行顺序:")
        
        # 测试第一个动作：点击BOSS菜单
        action1 = action_group['actions'][0]
        self.assertEqual(action1['trigger_type'], 'click_sub_menu_boss')
        self.assertEqual(action1['value'], 'union=17')
        # 设置find_elements返回值
        self.driver.find_elements.return_value = [self.element]
        self.action_manager.execute_action(self.driver, action1)
        self.driver.find_elements.assert_called_with(
            'xpath', "//a[contains(@onclick, 'union=17')]"
        )
        print(f"\n1. BOSS菜单点击动作:")
        print(f"- 动作类型: {action1['trigger_type']}")
        print(f"- 动作值: {action1['value']}")
        print(f"- 匹配XPath: //a[contains(@onclick, 'union=17')]")
        print(f"- 匹配到的元素数量: {len(self.driver.find_elements.return_value)}")
        
        # 测试第二个动作：清除队伍
        action2 = action_group['actions'][1]
        self.assertEqual(action2['trigger_type'], 'click_button_clear_team')
        self.action_manager.execute_action(self.driver, action2)
        print(f"\n2. 清除队伍按钮点击动作:")
        print(f"- 动作类型: {action2['trigger_type']}")
        print(f"- 匹配到的元素数量: {len(self.driver.find_elements.return_value)}")
        
        # 测试角色选择动作
        character_actions = action_group['actions'][2:7]
        for i, action in enumerate(character_actions, 3):
            self.assertEqual(action['trigger_type'], 'check_box_select_character')
            self.action_manager.execute_action(self.driver, action)
            print(f"\n{i}. 角色选择动作:")
            print(f"- 动作类型: {action['trigger_type']}")
            print(f"- 动作值: {action['value']}")
            print(f"- 角色描述: {action.get('_memo', '')}")
            print(f"- 匹配NAME: {action['value']}")
            print(f"- 匹配到的元素数量: {len(self.driver.find_elements.return_value)}")
        
        # 测试最后一个动作：点击战斗按钮
        action_last = action_group['actions'][-1]
        self.assertEqual(action_last['trigger_type'], 'click_button_start_battle')
        self.assertEqual(action_last['value'], 'union_battle')
        self.action_manager.execute_action(self.driver, action_last)
        print(f"\n7. 战斗按钮点击动作:")
        print(f"- 动作类型: {action_last['trigger_type']}")
        print(f"- 动作值: {action_last['value']}")
        print(f"- 匹配到的元素数量: {len(self.driver.find_elements.return_value)}")

    def test_execute_action_group(self):
        """测试完整动作组执行"""
        # 设置find_elements返回值
        self.driver.find_elements.return_value = [self.element]
        
        # 测试冒险动作组
        result = self.action_manager.execute_advanced_action(self.driver, self.config['1'])
        self.assertTrue(result)
        
        # 测试BOSS动作组
        result = self.action_manager.execute_advanced_action(self.driver, self.config['800170'])
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()