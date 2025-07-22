from abc import ABC, abstractmethod
import json
from selenium.webdriver.common.by import By
import time
from datetime import datetime
from scripts.advanced_element_finder import AdvancedElementFinderFactory
from scripts.log_manager import LogManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
import logging
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument('--headless')  # 无头模式
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-extensions')
options.add_argument('--disable-images')  # 可用插件或自定义profile关闭图片加载
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

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
    def __init__(self, meun_key_name):
        super().__init__()
        self.menu_key_name = meun_key_name

    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        try:
            self._wait(idle_before)
            finder = AdvancedElementFinderFactory.get_finder(self.menu_key_name)
            elements = finder.find_elements(driver, value)
            if not elements:
                LogManager.get_instance().error(f'未找到主菜单元素: {value}')
                # 等待页面稳定
                self._wait(self._inner_idle_time_for_web_complate)
                elements = finder.find_elements(driver, value)  # 重新获取元素
                if not elements or len(elements) == 0:
                    LogManager.get_instance().error(f'页面刷新后未找到主菜单元素: {value}')
                    return False
            elements[0].click()
            self._wait(idle_after)
            return True
        except Exception as e:
            LogManager.get_instance().error(f'执行主菜单动作时发生异常: {str(e)}')
            return False

class SubMenuStageActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        try:
            self._wait(idle_before)
            finder = AdvancedElementFinderFactory.get_finder('click_sub_menu_stage')
            elements = finder.find_elements(driver, value)
            if not elements:
                LogManager.get_instance().error(f'未找到子菜单关卡元素: {value}')
                # 等待页面稳定
                self._wait(self._inner_idle_time_for_web_complate)
                elements = finder.find_elements(driver, value)  # 重新获取元素
                if not elements or len(elements) == 0:
                    LogManager.get_instance().error(f'页面刷新后未找到子菜单关卡元素: {value}')
                    return False
            elements[0].click()
            self._wait(idle_after)
            return True
        except Exception as e:
            LogManager.get_instance().error(f'执行子菜单关卡动作时发生异常: {str(e)}')
            return False

class SubMenuBossActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        try:
            self._wait(idle_before)
            finder = AdvancedElementFinderFactory.get_finder('click_sub_menu_boss')
            elements = finder.find_elements(driver, value)
            if not elements or len(elements) == 0:
                LogManager.get_instance().error(f'未找到子菜单BOSS元素: {value}')
                return False
            elements[0].click()
            self._wait(idle_after)
            return True
        except Exception as e:
            LogManager.get_instance().error(f'执行子菜单BOSS动作时发生异常: {str(e)}')
            return False

class CharacterSelectActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        try:
            start = time.time()
            self._wait(idle_before)
            t1 = time.time()
            finder = AdvancedElementFinderFactory.get_finder('check_box_select_character')
            elements = finder.find_elements(driver, value)
            t2 = time.time()
            if not elements or len(elements) == 0:
                LogManager.get_instance().error(f'未找到角色复选框元素: {value}')
                return False
            if not elements[0].is_selected():
                elements[0].click()
            t3 = time.time()
            self._wait(idle_after)
            t4 = time.time()
            logging.info(f"[性能日志] 角色选择动作耗时: idle_before={t1-start:.3f}s, 查找={t2-t1:.3f}s, 点击={t3-t2:.3f}s, idle_after={t4-t3:.3f}s, 总计={t4-start:.3f}s")
            return True
        except Exception as e:
            LogManager.get_instance().error(f'执行角色选择动作时发生异常: {str(e)}')
            return False

    @staticmethod
    def batch_select(driver, char_ids):
        start = time.time()
        driver.execute_script('''
            var ids = arguments[0];
            ids.forEach(function(id){
                var el = document.getElementsByName(id)[0];
                if(el && !el.checked) el.click();
            });
        ''', char_ids)
        t1 = time.time()
        logging.info(f"[性能日志] 批量选择角色: {char_ids}, 总计: {t1-start:.3f}s")
        return True

class ClearTeamActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        try:
            start = time.time()
            self._wait(idle_before)
            t1 = time.time()
            finder = AdvancedElementFinderFactory.get_finder('click_button_clear_team')
            elements = finder.find_elements(driver, value)
            t2 = time.time()
            if not elements or len(elements) == 0:
                LogManager.get_instance().error('未找到清除队伍按钮')
                return False
            elements[0].click()
            t3 = time.time()
            self._wait(idle_after)
            t4 = time.time()
            logging.info(f"[性能日志] 清除队伍动作耗时: idle_before={t1-start:.3f}s, 查找={t2-t1:.3f}s, 点击={t3-t2:.3f}s, idle_after={t4-t3:.3f}s, 总计={t4-start:.3f}s")
            return True
        except Exception as e:
            LogManager.get_instance().error(f'执行清除队伍动作时发生异常: {str(e)}')
            return False

class StartBattleActionExecutor(AdvancedActionExecutor):
    def execute(self, driver, value=None, idle_before=0, idle_after=100):
        try:
            start = time.time()
            self._wait(idle_before)
            t1 = time.time()
            finder = AdvancedElementFinderFactory.get_finder('click_button_start_battle')
            elements = finder.find_elements(driver, value)
            t2 = time.time()
            if not elements or len(elements) == 0:
                LogManager.get_instance().error(f'未找到战斗按钮: {value}')
                return False
            elements[0].click()
            t3 = time.time()
            self._wait(idle_after)
            t4 = time.time()
            logging.info(f"[性能日志] 开始战斗动作耗时: idle_before={t1-start:.3f}s, 查找={t2-t1:.3f}s, 点击={t3-t2:.3f}s, idle_after={t4-t3:.3f}s, 总计={t4-start:.3f}s")
            return True
        except Exception as e:
            LogManager.get_instance().error(f'执行开始战斗动作时发生异常: {str(e)}')
            return False

class AdvancedActionExecutorFactory:
    _executors = {
        'click_main_menu': MainMenuActionExecutor('click_main_menu'),
        'click_main_menu_for_town': MainMenuActionExecutor('click_main_menu_for_town'),
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
        self.action_type_config = self._load_action_type_config()

    def _load_action_type_config(self):
        """加载动作类型配置"""
        try:
            import os
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs', 'server_01', 'action_type_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 将配置转换为以type为key的字典，方便查找
                return {item['type']: item for item in config['action_type_config']}
        except Exception as e:
            print(f"加载动作类型配置出错: {str(e)}")
            return {}

    def get_action_type_config(self, action_type):
        """获取动作类型的配置"""
        return self.action_type_config.get(action_type, {})

    def execute_action(self, driver, action):
        """执行单个动作"""
        print("action = " + str(action))
        action_type = action['trigger_type']
        executor = self.factory.get_executor(action_type)
        
        # 获取动作类型的配置
        type_config = self.get_action_type_config(action_type)
        
        # 使用动作类型配置中的等待时间
        idle_before = type_config.get('idle_before_operation', 0)
        idle_after = type_config.get('idle_after_operation', 100)
        
        return executor.execute(
            driver=driver,
            value=action.get('value'),
            idle_before=idle_before,
            idle_after=idle_after
        )

    def batch_selected_characters_actions(self, driver, actions):
        """
        批量处理boss战：清队+批量选人+开始战斗
        """
        char_ids = [a['value'] for a in actions[1:-1]]
        start_battle_value = actions[-1]['value']
        js = '''
        // 清除队伍
        var clearBtn = document.querySelector("input[onclick='checkDelAll()']");
        if(clearBtn) clearBtn.click();
        // 勾选角色
        var ids = arguments[0];
        ids.forEach(function(id){
            var el = document.getElementsByName(id)[0];
            if(el && !el.checked) el.click();
        });
        // 点击开始战斗
        var battleBtn = document.getElementsByName(arguments[1])[0];
        if(battleBtn) battleBtn.click();
        '''
        import time
        t0 = time.time()
        driver.execute_script(js, char_ids, start_battle_value)
        t1 = time.time()
        import logging
        logging.info(f"[性能日志] boss战批量处理: 清队+{len(char_ids)}角色+战斗, 总计: {t1-t0:.3f}s, 角色: {char_ids}")
        print(f"[批量boss战] 清队+{len(char_ids)}角色+战斗, 总计: {t1-t0:.3f}s, 角色: {char_ids}")
        return True

    def execute_advanced_action(self, driver, action_group):
        print(f"执行动作组: {action_group['name']}")
        print(f"说明: {action_group.get('note', '')}")

        actions = action_group['actions']
        # 检查是否为boss战批量场景：清队+N个角色选择+开始战斗
        if (len(actions) >= 3 and
            actions[0]['trigger_type'] == 'click_button_clear_team' and
            all(a['trigger_type'] == 'check_box_select_character' for a in actions[1:-1]) and
            actions[-1]['trigger_type'] == 'click_button_start_battle'):
            return self.batch_selected_characters_actions(driver, actions)

        i = 0
        while i < len(actions):
            action = actions[i]
            # 检查是否为连续的角色选择动作，批量处理
            if action['trigger_type'] == 'check_box_select_character':
                batch_ids = []
                j = i
                while j < len(actions) and actions[j]['trigger_type'] == 'check_box_select_character':
                    batch_ids.append(actions[j]['value'])
                    j += 1
                if len(batch_ids) > 1:
                    print(f"\n[{datetime.now()}] 批量执行第{i+1}~{j}个动作: check_box_select_character")
                    CharacterSelectActionExecutor.batch_select(driver, batch_ids)
                    i = j
                    continue
                else:
                    print(f"\n[{datetime.now()}] 执行第{i+1}个动作: {action['trigger_type']}")
                    if not self.execute_action(driver, action):
                        print(f"动作组执行失败，停止执行后续动作")
                        print(f"失败的动作组: {action_group['name']}")
                        return False
                    i += 1
                    continue
            print(f"\n[{datetime.now()}] 执行第{i+1}个动作: {action['trigger_type']}")
            if not self.execute_action(driver, action):
                print(f"动作组执行失败，停止执行后续动作")
                print(f"失败的动作组: {action_group['name']}")
                return False
            i += 1
        return True