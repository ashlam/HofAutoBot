from abc import ABC, abstractmethod
import time

class ActionExecutor(ABC):
    @abstractmethod
    def execute(self, driver, element, action):
        pass

class ClickActionExecutor(ActionExecutor):
    def execute(self, driver, element, action):
        try:
            element.click()
            time.sleep(action['wait_time'] / 1000)
            return True
        except Exception as e:
            print(f"\033[91m警告: 点击操作失败: {str(e)}\033[0m")
            return False

class NavigateActionExecutor(ActionExecutor):
    def execute(self, driver, element, action):
        try:
            element.click()
            time.sleep(action['wait_time'] / 1000)
            return True
        except Exception as e:
            print(f"\033[91m警告: 跳转操作失败: {str(e)}\033[0m")
            return False

class CheckboxActionExecutor(ActionExecutor):
    def execute(self, driver, element, action):
        try:
            element.click()
            time.sleep(action['wait_time'] / 1000)
            return True
        except Exception as e:
            print(f"\033[91m警告: 复选框操作失败: {str(e)}\033[0m")
            return False