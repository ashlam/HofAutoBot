from abc import ABC, abstractmethod
from selenium.webdriver.common.by import By
import time
from datetime import datetime
from scripts.advanced_element_finder import AdvancedElementFinderFactory
from scripts.log_manager import LogManager

class AdvancedActionExecutor(ABC):
    def __init__(self):
        self._inner_idle_time_for_web_complate = 100
    @abstractmethod
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        pass

    def _wait(self, seconds):
        """等待指定的毫秒数"""
        if seconds > 0:
            time.sleep(seconds / 1000)

class MainMenuActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=500, idle_after=100):
        self._wait(idle_before)
        finder = AdvancedElementFinderFactory.get_finder('click_main_menu')
        elements = finder.find_elements(driver, value)
        if not elements:
            LogManager.get_instance().error(f'未找到主菜单元素: {value}')
            # 等待页面稳定
        self._wait(self._inner_idle_time_for_web_complate)
        elements = finder.find_elements(driver, value)  # 重新获取元素
        if not elements:
            raise ValueError(f'页面刷新后未找到主菜单元素: {value}')
        elements[0].click()
        self._wait(idle_after)
        return True

class SubMenuStageActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=500, idle_after=100):
        self._wait(idle_before)
        finder = AdvancedElementFinderFactory.get_finder('click_sub_menu_stage')
        elements = finder.find_elements(driver, value)
        if not elements:
            LogManager.get_instance().error(f'未找到子菜单关卡元素: {value}')
            # 等待页面稳定
        self._wait(self._inner_idle_time_for_web_complate)
        elements = finder.find_elements(driver, value)  # 重新获取元素
        if not elements:
            raise ValueError(f'页面刷新后未找到子菜单关卡元素: {value}')
        elements[0].click()
        self._wait(idle_after)
        return True

class SubMenuBossActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        self._wait(idle_before)
        finder = AdvancedElementFinderFactory.get_finder('click_sub_menu_boss')
        elements = finder.find_elements(driver, value)
        if not elements:
            raise ValueError(f'未找到子菜单BOSS元素: {value}')
        elements[0].click()
        self._wait(idle_after)
        return True

class CharacterSelectActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        self._wait(idle_before)
        finder = AdvancedElementFinderFactory.get_finder('check_box_select_character')
        elements = finder.find_elements(driver, value)
        if not elements:
            raise ValueError(f'未找到角色复选框元素: {value}')
        if not elements[0].is_selected():
            elements[0].click()
        self._wait(idle_after)
        return True

class ClearTeamActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        self._wait(idle_before)
        finder = AdvancedElementFinderFactory.get_finder('click_button_clear_team')
        elements = finder.find_elements(driver, value)
        if not elements:
            raise ValueError('未找到清除队伍按钮')
        elements[0].click()
        self._wait(idle_after)
        return True

class StartBattleActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        self._wait(idle_before)
        finder = AdvancedElementFinderFactory.get_finder('click_button_start_battle')
        elements = finder.find_elements(driver, value)
        if not elements:
            raise ValueError(f'未找到战斗按钮: {value}')
        elements[0].click()
        self._wait(idle_after)
        return True

class AdvancedActionExecutorFactory:
    _executors = {
        'click_main_menu': MainMenuActionExecutor(),
        'click_sub_menu_stage': SubMenuStageActionExecutor(),
        'click_sub_menu_boss': SubMenuBossActionExecutor(),
        'check_box_select_character': CharacterSelectActionExecutor(),
        'click_button_clear_team': ClearTeamActionExecutor(),
        'click_button_start_battle': StartBattleActionExecutor()
    }

    @classmethod
    def get_executor(cls, action_type):
        """根据动作类型获取对应的执行器"""
        executor = cls._executors.get(action_type)
        if not executor:
            raise ValueError(f'不支持的动作类型: {action_type}')
        return executor

class AdvancedActionManager:
    def __init__(self):
        self.factory = AdvancedActionExecutorFactory()

    def execute_action(self, driver, action):
        """执行单个动作"""
        print("action = " + str(action))
        executor = self.factory.get_executor(action['trigger_type'])
        return executor.execute(
            driver=driver,
            value=action.get('value'),
            idle_before=action.get('idle_before_operation', 0),
            idle_after=action.get('idle_after_operation', 100)
        )

    def execute_advanced_action(self, driver, action_group):
        """执行动作组"""
        print(f"执行动作组: {action_group['name']}")
        print(f"说明: {action_group.get('note', '')}")

        for i, action in enumerate(action_group['actions']):
            print(f"\n[{datetime.now()}] 执行第{i+1}个动作: {action['trigger_type']}")
            if not self.execute_action(driver, action):
                print(f"动作组执行失败，停止执行后续动作")
                print(f"失败的动作组: {action_group['name']}")
                return False

        return True