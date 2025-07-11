import re
import os

def test_pvp_regex():
    # 读取HTML文件
    html_path = os.path.join('source_codes', 'source_code_pvp_prepare_page.htm')
    with open(html_path, 'r', encoding='utf-8') as f:
        content_text = f.read()
    
    # 测试当前用户名匹配
    user_pattern = r'<div id="menu2">\s*<div style="width:100%">\s*<div style="width:30%;float:left">(.*?)</div>\s*<div style="width:60%;float:right">\s*<div style="width:40%;float:left"><span class="bold">資金</span>.*?<span class="bold">時間</span>'
    user_match = re.search(user_pattern, content_text, re.DOTALL)
    if user_match:
        current_user = user_match.group(1)
        print(f"当前用户名匹配成功: {current_user}")
    else:
        print("当前用户名匹配失败")
        # 尝试使用更宽松的匹配模式
        backup_user_pattern = r'<div id="menu2">\s*<div[^>]*>\s*<div[^>]*>(.*?)</div>'
        backup_user_match = re.search(backup_user_pattern, content_text, re.DOTALL)
        if backup_user_match:
            current_user = backup_user_match.group(1).strip()
            print(f"使用备用模式匹配到当前用户名: {current_user}")
        else:
            print("备用模式也未能匹配到当前用户名")
            return
    
    # 测试第一名用户匹配 - 使用TOP 5特征
    first_place_pattern = r'<div class="u">TOP 5</div>[\s\S]*?<td class="td7"[^>]*>\s*<img src="\./image/icon/crown01\.png"[^>]*></td><td class="td8">\s*([^(]+?)\s*\('
    first_place_match = re.search(first_place_pattern, content_text, re.DOTALL)
    if first_place_match:
        first_place_user = first_place_match.group(1).strip()
        print(f"第一名用户匹配成功(TOP 5特征): {first_place_user}")
    else:
        print("第一名用户匹配失败(TOP 5特征)")
        # 尝试备用模式
        backup_pattern = r'<img src="\./image/icon/crown01\.png"[^>]*>[^<]*</td><td class="td8">\s*([^(]+?)\s*\('
        backup_match = re.search(backup_pattern, content_text, re.DOTALL)
        if backup_match:
            first_place_user = backup_match.group(1).strip()
            print(f"第一名用户匹配成功(备用模式): {first_place_user}")
        else:
            print("第一名用户匹配失败(备用模式)")
            # 尝试最宽松的匹配模式
            last_resort_pattern = r'crown01\.png[^<]*</td><td[^>]*>\s*([^<(]+?)\s*\('
            last_resort_match = re.search(last_resort_pattern, content_text, re.DOTALL)
            if last_resort_match:
                first_place_user = last_resort_match.group(1).strip()
                print(f"第一名用户匹配成功(最宽松模式): {first_place_user}")
            else:
                print("所有匹配模式都失败")
                # 检查HTML中是否包含关键特征
                print("\n检查HTML中的关键特征:")
                if 'crown01.png' in content_text:
                    print("HTML中包含crown01.png图标")
                if 'TOP 5' in content_text:
                    print("HTML中包含TOP 5文本")
                if 'td8' in content_text:
                    print("HTML中包含td8类")
                return
    
    # 比较是否相同
    is_first = current_user == first_place_user
    print(f"用户是否为第一名: {is_first} (当前用户: '{current_user}', 第一名: '{first_place_user}')")

    # 打印HTML中的关键部分，帮助调试
    print("\n检查HTML中的关键部分:")
    # 查找TOP 5部分
    top5_pattern = r'<div class="u">TOP 5</div>[\s\S]*?<tr><td class="td7"[^>]*>\s*<img src="\./image/icon/crown01\.png"[^>]*></td><td class="td8">([\s\S]*?)</td></tr>'
    top5_match = re.search(top5_pattern, content_text, re.DOTALL)
    if top5_match:
        print("找到TOP 5部分:")
        print(top5_match.group(0)[:200] + "...")
    else:
        print("未找到TOP 5部分")
        
    # 测试最宽松的匹配模式
    print("\n测试最宽松的匹配模式:")
    last_resort_pattern = r'crown01\.png[^<]*</td><td[^>]*>\s*([^<(]+?)\s*\('
    last_resort_match = re.search(last_resort_pattern, content_text, re.DOTALL)
    if last_resort_match:
        print(f"最宽松模式匹配成功: {last_resort_match.group(1).strip()}")
    else:
        print("最宽松模式匹配失败")

if __name__ == "__main__":
    test_pvp_regex()