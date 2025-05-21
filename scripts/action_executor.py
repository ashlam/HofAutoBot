from selenium.webdriver.common.by import By
import time
import re
from scripts.element_finder import find_element_by_html, find_element_by_text_and_url

class ActionExecutor:
    def __init__(self):
        pass
    def execute_action(self, driver, action):
        """执行单个动作"""
        
        # if not action_config:
        #     print(f"\033[91m错误：未找到动作配置，id: {action_id}\033[0m")
        #     return False
            
        # # 执行动作组中的第一个动作
        # if not action_config.get('actions'):
        #     print(f"\033[91m错误：动作配置 {action_id} 没有包含任何动作\033[0m")
        #     return False
        
        print(f'action = {action}')
        element = find_element_by_html(driver, action['element_info'], action['container_info'])
        
        # 如果常规方法找不到元素，尝试使用备用方法
        if not element and action['trigger_type'] == '跳转':
            print("\n使用备用方法查找元素...")
            # 从element_info中提取文本和URL
            html_content = action['element_info']
            text_match = re.search(r'>([^<]+)<', html_content)
            text = text_match.group(1).strip() if text_match else ""
            
            url_match = re.search(r"onclick=\"[^\"]*'([^']+)'|onclick=\"[^\"]*\"([^\"]+)\"", html_content)
            url = url_match.group(1) or url_match.group(2) if url_match else ""
            
            print(f"备用查找: 文本={text}, URL={url}")
            if text and url:
                # 使用文本和URL的一部分来查找元素
                xpath = f"//a[contains(text(),'{text}') and contains(@onclick,'{url}')]" 
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    print(f"备用方法找到 {len(elements)} 个匹配元素")
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            print(f"备用方法找到可用元素: {elem.tag_name}, 文本: {elem.text}")
                            element = elem
                            break
                except Exception as e:
                    print(f"\033[91m备用查找出错: {str(e)}\033[0m")
        
        if element:
            try:
                if action['trigger_type'] == '跳转':
                    element.click()
                elif action['trigger_type'] == '按钮':
                    element.click()
                elif action['trigger_type'] == '复选框':
                    element.click()
                time.sleep(action['wait_time'] / 1000)  # 等待指定时间
                return True  # 动作执行成功
            except Exception as e:
                print(f"\033[91m警告: 元素操作失败: {str(e)}\033[0m")
                print(f"\033[91m失败的动作类型: {action['trigger_type']}\033[0m")
                print(f"\033[91m失败的元素信息: {action['element_info']}\033[0m")
                return False  # 动作执行失败
        else:
            print(f"\033[91m警告: 无法找到元素，跳过动作\033[0m")
            print(f"\033[91m失败的动作类型: {action['trigger_type']}\033[0m")
            print(f"\033[91m失败的元素信息: {action['element_info']}\033[0m")
            return False  # 动作执行失败

    def execute_actions(self, driver, action_config):
        """执行一组动作"""
        print(f"执行动作: {action_config['name']}")
        print(f"说明: {action_config['note']}")
        ae = ActionExecutor()
        
        # 遍历执行每个动作，直到第一个失败的动作
        for i, action in enumerate(action_config['actions']):
            print(f"\n执行第{i+1}个动作: {action['trigger_type']}")
            
            # 对于第一个跳转动作，使用简化的查找方法
            if i == 0 and action['trigger_type'] == '跳转':
                html_content = action['element_info']
                text_match = re.search(r'>([^<]+)<', html_content)
                text = text_match.group(1).strip() if text_match else ""
                
                url_match = re.search(r"'(index2\.php[^']+)'|\"(index2\.php[^\"]+)\"", html_content)
                url_part = url_match.group(1) or url_match.group(2) if url_match else ""
                
                if text and url_part:
                    print(f"\n优先使用简化方法查找元素: 文本={text}, URL部分={url_part}")
                    try:
                        # 尝试最简单的方式 - 仅通过文本查找
                        simple_xpath = f"//a[contains(text(),'{text}')]" 
                        print(f"使用最简单的XPath: {simple_xpath}")
                        elements = driver.find_elements(By.XPATH, simple_xpath)
                        print(f"找到 {len(elements)} 个匹配元素")
                        
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                print(f"找到可用元素: {element.tag_name}, 文本: {element.text}")
                                element.click()
                                time.sleep(action['wait_time'] / 1000)
                                continue  # 继续执行下一个动作
                        
                        # 如果简单方法失败，尝试备用方法
                        element = find_element_by_text_and_url(driver, text, url_part)
                        if element:
                            print("使用备用方法找到元素，点击它...")
                            element.click()
                            time.sleep(action['wait_time'] / 1000)
                            continue  # 继续执行下一个动作
                        
                        # 如果备用方法也失败，尝试常规方法
                        if not ae.execute_action(driver, action):
                            print("所有查找方法都失败，停止执行后续动作")
                            return False
                    except Exception as e:
                        print(f"\033[91m简化查找出错: {str(e)}\033[0m")
                        # 如果简化方法出错，使用常规方法
                        if not ae.execute_action(driver, action):
                            print(f"\033[91m常规方法也失败，停止执行后续动作\033[0m")
                            print(f"\033[91m失败的动作名称: {action_config['name']}\033[0m")
                            return False
                else:
                    # 如果无法提取文本或URL，使用常规方法
                    if not ae.execute_action(driver, action):
                        print(f"\033[91m常规方法失败，停止执行后续动作\033[0m")
                        print(f"\033[91m失败的动作名称: {action_config['name']}\033[0m")
                        return False
            else:
                # 对于其他动作，使用常规方法
                if not ae.execute_action(driver, action):
                    print(f"\033[91m动作执行失败，停止执行后续动作\033[0m")
                    print(f"\033[91m失败的动作名称: {action_config['name']}\033[0m")
                    return False
        
        # 所有动作都执行成功
        return True