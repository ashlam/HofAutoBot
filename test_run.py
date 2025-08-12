from selenium import webdriver
import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.condition_checker import ConditionChecker

def check_page_condition():
    # 测试ID为1的条件配置
    config_path = os.path.join(project_root, 'configs', 'condition_config.json')
    checker = ConditionChecker(config_path)
    
    # 测试场景1：union_id=8且wait_time不为空
    page_content_1 = '''
    <div class="main_content">
        <a href="#" onclick="RA_UseBack('index2.php?union=8')">工会</a>
        <div style="margin:0 20px">離下次戰鬥還需要 : <span class="bold">30分</span></div>
    </div>
    '''
    result_1 = checker.check_condition('1', page_content_1)
    print("测试场景1 - union_id=8且wait_time不为空：")
    print(f"预期结果：10001，实际结果：{result_1}")
    
    # 测试场景2：union_id=8但wait_time为空
    page_content_2 = '''
    <div class="main_content">
        <a href="#" onclick="RA_UseBack('index2.php?union=8')">工会</a>
        <div style="margin:0 20px">離下次戰鬥還需要 : <span class="bold"></span></div>
    </div>
    '''
    result_2 = checker.check_condition('1', page_content_2)
    print("\n测试场景2 - union_id=8但wait_time为空：")
    print(f"预期结果：None，实际结果：{result_2}")
    
    # 测试场景3：union_id不是8
    page_content_3 = '''
    <div class="main_content">
        <a href="#" onclick="RA_UseBack('index2.php?union=7')">工会</a>
        <div style="margin:0 20px">離下次戰鬥還需要 : <span class="bold">30分</span></div>
        <div style="width:40%;float:right"><span class="bold">時間</span> : <span id="mtime">1500</span>/4000</div>
    </div>
    '''
    result_3 = checker.check_condition('1', page_content_3)
    print("\n测试场景3 - union_id不是8且my_time>1000：")
    print(f"预期结果：10002，实际结果：{result_3}")
    
    # 测试场景4：没有匹配的条件
    page_content_4 = '''
    <div class="main_content">
        <a href="#" onclick="RA_UseBack('index2.php?union=7')">工会</a>
        <div style="margin:0 20px">離下次戰鬥還需要 : <span class="bold">30分</span></div>
        <div style="width:40%;float:right"><span class="bold">時間</span> : <span id="mtime">500</span>/4000</div>
    </div>
    '''
    result_4 = checker.check_condition('1', page_content_4)
    print("\n测试场景4 - 所有条件都不满足：")
    print(f"预期结果：None，实际结果：{result_4}")

def test_condition_checker_with_boss_content():
    """使用source_code_boss_full内容测试ConditionChecker"""
    # 读取source_code_boss_full文件内容
    with open(os.path.join(project_root, 'source_codes', 'source_code_boss_full'), 'r', encoding='utf-8') as f:
        boss_content = f.read()
    
    # 初始化条件检查器
    config_path = os.path.join(project_root, 'configs', 'condition_config.json')
    checker = ConditionChecker(config_path)
    
    # 检查条件ID为1的配置
    print("\n使用source_code_boss_full内容测试条件ID=1:")
    result = checker.check_condition('1', boss_content)
    print(f"检查结果: {result}")
    
    # 输出详细检查过程
    # print("\n详细检查过程:")
    # checker.print_check_details('1', boss_content)


if __name__ == '__main__':
    test_condition_checker_with_boss_content()
    # # 初始化浏览器
    # driver = webdriver.Chrome()
    # driver.get('https://pim0110.com/hall/')
    
    # # 等待用户确认
    # while True:
    #     user_input = input('准备好开始执行动作了吗？(y/yes): ').lower()
    #     if user_input in ['y', 'yes']:
    #         break
    
    # # 获取页面内容并检查条件
    # checker = ConditionChecker('configs/condition_config.json')
    # page_content = driver.page_source
    # result = checker.check_condition('1', page_content)
    
    # print("\n检查页面条件结果：")
    # print(f"条件ID：1，检查结果：{result}")
    
    # # 关闭浏览器
    # driver.quit()