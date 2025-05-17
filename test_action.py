from selenium import webdriver
import time
import os
import sys
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

# 全局变量
server_sub_dir = None

from scripts.server_config_manager import ServerConfigManager
from scripts.action_executor import ActionExecutor
from scripts.action_group_executor import execute_action_group

def test_action(driver, all_action_configs, action_id):
    """测试执行单个动作配置"""
    try:
        action_config_by_action_id = all_action_configs.get(action_id)
        if not action_config_by_action_id:
            print(f'未找到ID为{action_id}的动作配置')
            return False
        
        # 执行动作配置中的所有动作
        ae = ActionExecutor()
        ae.execute_actions(driver, action_config_by_action_id)
        return True
    except Exception as e:
        print(f'执行动作出错: {str(e)}')
        return False

def test_action_group(driver, all_action_group_configs, group_id, all_action_conifgs):
    """测试执行动作组"""
    print(f"group_id = {group_id}")
    try:
        # 执行动作组
        result = execute_action_group(driver, all_action_group_configs, group_id, all_action_conifgs)
        print(f"result = {result}")
        return result
    # except Exception as e:
    #     print(f'执行动作组出错: {str(e)}')
    #     return False
    finally:
        print('按回车键退出...，按r键重新开始')

def main():
    # 初始化浏览器
    # 从server_address.json读取服务器地址
    
    

    selected_server_id = None
    
    while True:
        print('请选择要打开的网址:')
        print('1、1服； 2、2服')
        user_input = input('请输入选择(1/2): ')
        if user_input.lower() in ['q', 'no']:
            print('已取消打开网址')
            return
        elif user_input == '1':
            selected_server_id = 1
            break
        elif user_input == '2':
            selected_server_id = 2
            break
        else:
            print('无效的选择，请重新输入。')
    
    server_config_manager = ServerConfigManager()
    server_config_manager.set_current_server_id(selected_server_id)
    current_server_data = server_config_manager.current_server_data
    if not current_server_data:
        print('错误：未找到指定id的服务器数据')
        return
    url = current_server_data.get('url')
    if not url:
        print('错误：服务器URL为空')
        return
    print(f'正在连接服务器：{url}')
    driver = webdriver.Chrome()
    driver.get(url)
    print('正在打开浏览器...')
    # 等待用户确认
    while True:
        user_input = input('准备好开始执行动作了吗？(y/yes)， q/n/no键退出: ').lower()
        if user_input in ['y', 'yes']:
            break
        if user_input in ['n', 'no', 'q']:
            print('已取消执行动作')
            return
    
    try:
        # 选择执行模式
        select_debug_option(driver, server_config_manager)
            
    # except Exception as e:
    #     print(f'执行出错: {str(e)}')
    finally:
        print('按回车键退出...，按r键重新开始')
        if input().lower() == 'r':
            select_debug_option(driver, server_config_manager)
        else:
            # 关闭浏览器
            driver.quit()

def select_debug_option(driver: webdriver.Chrome, server_config_manager: ServerConfigManager):
    import json
    import os

    if not server_config_manager:
        print('错误：未选择服务器')
        return

    action_groups = server_config_manager.all_action_group_config_by_server

    print('\n请选择调试选项:')
    print('1. 执行单个动作配置')
    
    # 动态生成动作组选项
    group_options = []
    for group_id, group_info in action_groups.items():
        group_options.append((group_id, group_info['name']))
    
    # 按照group_id排序
    group_options.sort(key=lambda x: int(x[0]))
    
    # 显示动作组选项
    for i, (group_id, name) in enumerate(group_options, 2):
        print(f'{i}. {name}({group_id})')
    
    max_choice = len(group_options) + 1
    choice = input(f'请输入选择(1-{max_choice}): ')
    
    try:
        choice_num = int(choice)
        if choice_num == 1:
            # 执行单个动作配置
            action_id = int(input('请输入要执行的动作ID: '))
            test_action(driver, server_config_manager.all_action_config_by_server, action_id)
        elif 2 <= choice_num <= max_choice:
            # 执行选择的动作组
            group_id = group_options[choice_num - 2][0]
            test_action_group(driver, server_config_manager.all_action_group_config_by_server, group_id, server_config_manager.all_action_config_by_server)
        else:
            print('无效的选择')
            select_debug_option(driver, server_sub_dir, server_config_manager)
    except ValueError:
        print('请输入有效的数字')
        select_debug_option(driver, server_sub_dir, server_config_manager)

if __name__ == '__main__':
    main()