from selenium.webdriver.common.by import By
import time
import re
from scripts.element_finders import HtmlElementFinder, TextAndUrlElementFinder, SimpleTextElementFinder
from scripts.actions.factory import ActionExecutorFactory

class ActionExecutor:
    def __init__(self):
        self.html_finder = HtmlElementFinder()
        self.text_url_finder = TextAndUrlElementFinder()
        self.simple_text_finder = SimpleTextElementFinder()

    def _execute_action(self, driver, action):
        """执行单个动作"""
        print(f'action = {action}')
        
        # 尝试使用主要查找方法
        element = self.html_finder.find_element(
            driver, 
            action['element_info'], 
            action.get('container_info')
        )
        
        # 如果是跳转动作且主要方法失败，尝试备用方法
        if not element and action['trigger_type'] == '跳转':
            print("\n使用备用方法查找元素...")
            html_content = action['element_info']
            text_match = re.search(r'>([^<]+)<', html_content)
            text = text_match.group(1).strip() if text_match else ""
            
            url_match = re.search(r"onclick=\"[^\"]*'([^']+)'|onclick=\"[^\"]*\"([^\"]+)\"", html_content)
            url = url_match.group(1) or url_match.group(2) if url_match else ""
            
            if text and url:
                print(f"备用查找: 文本={text}, URL={url}")
                element = self.text_url_finder.find_element(driver, text, url)
        
        if element:
            try:
                # 使用工厂获取对应的执行器
                executor = ActionExecutorFactory.get_executor(action['trigger_type'])
                return executor.execute(driver, element, action)
            except Exception as e:
                print(f"\033[91m警告: 动作执行失败: {str(e)}\033[0m")
                print(f"\033[91m失败的动作类型: {action['trigger_type']}\033[0m")
                print(f"\033[91m失败的元素信息: {action['element_info']}\033[0m")
                return False
        else:
            print(f"\033[91m警告: 无法找到元素，跳过动作\033[0m")
            print(f"\033[91m失败的动作类型: {action['trigger_type']}\033[0m")
            print(f"\033[91m失败的元素信息: {action['element_info']}\033[0m")
            return False

    def execute_actions(self, driver, action_config):
        """执行一组动作"""
        print(f"执行动作: {action_config['name']}")
        print(f"说明: {action_config['note']}")
        
        for i, action in enumerate(action_config['actions']):
            print(f"\n执行第{i+1}个动作: {action['trigger_type']}")
            
            # 对于第一个跳转动作，优先使用简化的查找方法
            if i == 0 and action['trigger_type'] == '跳转':
                html_content = action['element_info']
                text_match = re.search(r'>([^<]+)<', html_content)
                text = text_match.group(1).strip() if text_match else ""
                
                if text:
                    print(f"\n优先使用简化方法查找元素: 文本={text}")
                    try:
                        # 使用简单文本查找
                        element = self.simple_text_finder.find_element(driver, text)
                        if element:
                            executor = ActionExecutorFactory.get_executor(action['trigger_type'])
                            if executor.execute(driver, element, action):
                                continue
                    except Exception as e:
                        print(f"\033[91m简化查找出错: {str(e)}\033[0m")
            
            # 如果简化方法失败或不是第一个跳转动作，使用标准方法
            if not self._execute_action(driver, action):
                print(f"\033[91m动作执行失败，停止执行后续动作\033[0m")
                print(f"\033[91m失败的动作名称: {action_config['name']}\033[0m")
                return False
        
        return True