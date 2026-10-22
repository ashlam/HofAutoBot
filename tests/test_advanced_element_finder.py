import unittest
from unittest.mock import MagicMock
from selenium.webdriver.common.by import By
from scripts.advanced_element_finder import (
    AdvancedElementFinderFactory,
)

class TestAdvancedElementFinder(unittest.TestCase):
    def setUp(self):
        self.driver = MagicMock()
        self.element = MagicMock()
        self.driver.find_elements.return_value = [self.element]

    def test_main_menu_finder(self):
        finder = AdvancedElementFinderFactory.get_finder('click_main_menu')
        finder.find_elements(self.driver, 'adventure')
        self.driver.find_elements.assert_called_with(
            'xpath', "//a[contains(@onclick, 'adventure')]"
        )

    def test_sub_menu_stage_finder(self):
        finder = AdvancedElementFinderFactory.get_finder('click_sub_menu_stage')
        finder.find_elements(self.driver, 'stage_1')
        self.driver.find_elements.assert_called_with(
            'xpath', "//a[contains(@onclick, 'stage_1')]"
        )

    def test_sub_menu_boss_finder(self):
        finder = AdvancedElementFinderFactory.get_finder('click_sub_menu_boss')
        finder.find_elements(self.driver, 'boss_1')
        self.driver.find_elements.assert_called_with(
            'xpath', "//a[contains(@onclick, 'boss_1')]"
        )

    def test_character_select_finder(self):
        finder = AdvancedElementFinderFactory.get_finder('check_box_select_character')
        finder.find_elements(self.driver, 'character_1')
        self.driver.find_elements.assert_called_with(
            'name', 'character_1'
        )

    def test_clear_team_finder(self):
        finder = AdvancedElementFinderFactory.get_finder('click_button_clear_team')
        finder.find_elements(self.driver, 'checkDelAll()')
        self.driver.find_elements.assert_called_with(
            'xpath', '//input[@type="button"][@onclick="checkDelAll()"]'
        )

    def test_start_battle_finder_monster(self):
        finder = AdvancedElementFinderFactory.get_finder('click_button_start_battle')
        finder.find_elements(self.driver, 'monster_battle')
        self.driver.find_elements.assert_called_with(
            'name', 'monster_battle'
        )

    def test_start_battle_finder_union(self):
        finder = AdvancedElementFinderFactory.get_finder('click_button_start_battle')
        finder.find_elements(self.driver, 'union_battle')
        self.driver.find_elements.assert_called_with(
            'name', 'union_battle'
        )

    def test_start_battle_finder_default(self):
        finder = AdvancedElementFinderFactory.get_finder('click_button_start_battle')
        finder.find_elements(self.driver, None)
        self.driver.find_elements.assert_called_with(
            'xpath', "//input[@type='submit'][@value='戰鬥!']"
        )

    def test_invalid_action_type(self):
        with self.assertRaises(ValueError):
            AdvancedElementFinderFactory.get_finder('invalid_action_type')

if __name__ == '__main__':
    unittest.main()
