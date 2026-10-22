import unittest
from unittest.mock import MagicMock
from scripts.advanced_action_executor import AdvancedActionManager
import json
import os

class TestAdvancedActionConfig(unittest.TestCase):
    def setUp(self):
        self.driver = MagicMock()
        self.element = MagicMock()
        self.driver.find_elements.return_value = [self.element]

        # 读取1服配置文件
        config_path = os.path.join(os.path.dirname(__file__), '../configs/server_01/action_config_advanced.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.action_manager = AdvancedActionManager(server_id=1)

    def test_adventure_action_group(self):
        """测试'点一次冒险->伟大航路'动作组"""
        action_group = self.config['1']
        actions = action_group['actions']

        # 动作顺序：进入冒险页 -> 城镇 -> 选择关卡 -> 开始战斗
        self.assertEqual(actions[0]['trigger_type'], 'click_main_menu')
        self.assertEqual(actions[0]['value'], 'hunt')
        self.assertEqual(actions[1]['trigger_type'], 'click_main_menu_for_town')
        self.assertEqual(actions[1]['value'], 'hunt')
        self.assertEqual(actions[2]['trigger_type'], 'click_sub_menu_stage')
        self.assertEqual(actions[2]['value'], 'common=ocean1')
        self.assertEqual(actions[3]['trigger_type'], 'click_button_start_battle')
        self.assertEqual(actions[3]['value'], 'monster_battle')

        # 各动作实际使用的元素定位方式
        self.action_manager.execute_action(self.driver, actions[0])
        self.driver.find_elements.assert_called_with('xpath', "//a[contains(@onclick, 'hunt')]")

        self.driver.reset_mock()
        self.action_manager.execute_action(self.driver, actions[2])
        self.driver.find_elements.assert_called_with('xpath', "//a[contains(@onclick, 'common=ocean1')]")

        self.driver.reset_mock()
        self.action_manager.execute_action(self.driver, actions[3])
        self.driver.find_elements.assert_called_with('name', 'monster_battle')

    def test_boss_action_group(self):
        """测试'一服旋风'BOSS动作组"""
        action_group = self.config['600170']
        actions = action_group['actions']

        # 动作顺序：清队 -> 选5个角色 -> 开始战斗
        self.assertEqual(actions[0]['trigger_type'], 'click_button_clear_team')
        self.assertEqual(actions[0]['value'], 'checkDelAll()')
        character_actions = actions[1:-1]
        self.assertEqual(len(character_actions), 5)
        for action in character_actions:
            self.assertEqual(action['trigger_type'], 'check_box_select_character')
        self.assertEqual(actions[-1]['trigger_type'], 'click_button_start_battle')
        self.assertEqual(actions[-1]['value'], 'union_battle')

        # 清队按钮的定位
        self.action_manager.execute_action(self.driver, actions[0])
        self.driver.find_elements.assert_called_with(
            'xpath', '//input[@type="button"][@onclick="checkDelAll()"]'
        )

        # 角色复选框按 name 定位
        self.driver.reset_mock()
        self.action_manager.execute_action(self.driver, character_actions[0])
        self.driver.find_elements.assert_called_with('name', character_actions[0]['value'])

        # 战斗按钮按 name 定位
        self.driver.reset_mock()
        self.action_manager.execute_action(self.driver, actions[-1])
        self.driver.find_elements.assert_called_with('name', 'union_battle')

    def test_execute_action_group(self):
        """测试完整动作组执行"""
        self.driver.find_elements.return_value = [self.element]

        # 冒险动作组
        result = self.action_manager.execute_advanced_action(self.driver, self.config['1'])
        self.assertTrue(result)

        # BOSS动作组：命中「清队+N角色+开始战斗」模式，走单次JS注入
        self.driver.reset_mock()
        result = self.action_manager.execute_advanced_action(self.driver, self.config['600170'])
        self.assertTrue(result)
        self.assertEqual(self.driver.execute_script.call_count, 1)
        args = self.driver.execute_script.call_args[0]
        self.assertEqual(len(args[1]), 5, "应把5个角色ID传给批量脚本")
        self.assertEqual(args[2], 'union_battle')

    def test_batch_path_avoids_individual_selenium_calls(self):
        """BOSS批量战应只注入一次JS，而不是逐个点击"""
        self.driver.find_elements.return_value = [self.element]
        self.action_manager.execute_advanced_action(self.driver, self.config['600170'])
        # 批量路径下不应再单独调用 find_elements
        self.assertEqual(self.driver.find_elements.call_count, 0)

if __name__ == '__main__':
    unittest.main()
