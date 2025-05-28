from abc import ABC, abstractmethod
from selenium.webdriver.common.by import By

class AdvancedElementFinder(ABC):
    @abstractmethod
    def find_elements(self, driver, value=None):
        pass

class MainMenuElementFinder(AdvancedElementFinder):
    def find_elements(self, driver, value=None):
        return driver.find_elements('xpath', f"//a[contains(@onclick, '{value}')]")

class SubMenuStageElementFinder(AdvancedElementFinder):
    def find_elements(self, driver, value=None):
        return driver.find_elements('xpath', f"//a[contains(@onclick, '{value}')]")

class SubMenuBossElementFinder(AdvancedElementFinder):
    def find_elements(self, driver, value=None):
        return driver.find_elements('xpath', f"//a[contains(@onclick, '{value}')]")

class CharacterSelectElementFinder(AdvancedElementFinder):
    def find_elements(self, driver, value=None):
        return driver.find_elements('name', value)

class ClearTeamElementFinder(AdvancedElementFinder):
    def find_elements(self, driver, value=None):
        ## <input type="button" class="btn" onclick="checkDelAll()" value="清除">
        return driver.find_elements('xpath', f'//input[@type="button"][@onclick="{value}"]')

class StartBattleElementFinder(AdvancedElementFinder):
    def find_elements(self, driver, value=None):
        if value == 'monster_battle':
            return driver.find_elements('name', 'monster_battle')
        elif value == 'union_battle':
            return driver.find_elements('name', 'union_battle')
        else:
            return driver.find_elements('xpath', "//input[@type='submit'][@value='戰鬥!']")

class AdvancedElementFinderFactory:
    _finders = {
        'click_main_menu': MainMenuElementFinder(),
        'click_sub_menu_stage': SubMenuStageElementFinder(),
        'click_sub_menu_boss': SubMenuBossElementFinder(),
        'check_box_select_character': CharacterSelectElementFinder(),
        'click_button_clear_team': ClearTeamElementFinder(),
        'click_button_start_battle': StartBattleElementFinder()
    }

    @classmethod
    def get_finder(cls, action_type):
        """根据动作类型获取对应的查找器"""
        finder = cls._finders.get(action_type)
        if not finder:
            raise ValueError(f'不支持的动作类型: {action_type}')
        return finder