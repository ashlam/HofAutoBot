import json
import re

def find_union_links(text):
    # 从配置文件中读取模板
    with open('configs/condition_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
        template = config['1']['conditions'][0]['element_info']
        replace_holder = config['1']['conditions'][0]['validation'][0]['value_of_placeholder']
    
    # 构建正则表达式模式
    print(f"template：{template}")
    print(f"replace_holder：{replace_holder}")
    
    # 从配置文件中获取目标值
    target_value = config['1']['conditions'][0]['validation'][0]['target_value']
    
    # 将模板中的特殊字符转义，但保持HTML属性和引号的结构
    pattern = re.escape(template)  # 转义所有特殊字符
    pattern = pattern.replace(f'={replace_holder}', f'={target_value}')  # 替换union=__union_id__为指定的target_value
    print(f"最终正则表达式：{pattern}")
    
    # 在文本中查找所有匹配项
    matches = re.findall(pattern, text, re.DOTALL)
    return matches

def test_find_union_links():
    # 测试用例1：包含多个有效链接的文本
    test_text_1 = '''
    <div class="main_content">
        <a href="#" onclick="RA_UseBack('index2.php?union=1')">工会1</a>
        <a href="#" onclick="RA_UseBack('index2.php?union=8')">工会8</a>
        <a href="#" onclick="RA_UseBack('index2.php?union=15')">工会15</a>
        <a href="#" onclick="RA_UseBack('index2.php?union=25')">工会25</a>
    </div>
    '''
    print(f"原文：{test_text_1}")
    matches_1 = find_union_links(test_text_1)
    print("测试用例1 - 多个有效链接：")
    print(f"找到 {len(matches_1)} 个匹配项：")
    for match in matches_1:
        print(match)
    
    # 测试用例2：包含无效链接的文本
    test_text_2 = '''
    <div class="main_content">
        <a href="#" onclick="RA_UseBack('index2.php?union=0')">无效工会0</a>
        <a href="#" onclick="RA_UseBack('index2.php?union=26')">无效工会26</a>
        <a href="#" onclick="RA_UseBack('index2.php?union=8')">有效工会8</a>
    </div>
    '''
    
    matches_2 = find_union_links(test_text_2)
    print("\n测试用例2 - 包含无效链接：")
    print(f"找到 {len(matches_2)} 个匹配项：")
    for match in matches_2:
        print(match)
    
    # 测试用例3：空文本
    test_text_3 = ""
    matches_3 = find_union_links(test_text_3)
    print("\n测试用例3 - 空文本：")
    print(f"找到 {len(matches_3)} 个匹配项")

if __name__ == '__main__':
    test_find_union_links()