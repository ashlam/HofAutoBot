import os
import json
import re
from bs4 import BeautifulSoup

def parse_boss_info(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    boss_list = []
    
    # 查找所有的boss信息块
    boss_divs = soup.find_all('div', class_='carpet_frame')
    
    for boss_div in boss_divs:
        # 获取boss名称
        name_div = boss_div.find('div', class_='bold dmg')
        if not name_div:
            continue
        name = name_div.text.strip()
        
        # 获取等级限制
        level_text = boss_div.get_text()
        level_match = re.search(r'限制級別:(\d+)級', level_text)
        if not level_match:
            continue
        level_limit = int(level_match.group(1))
        
        # 获取union_id
        onclick = boss_div.find('a')['onclick']
        union_match = re.search(r'union=(\d+)', onclick)
        if not union_match:
            continue
        union_id = int(union_match.group(1))
        
        # 获取图片路径
        img_tag = boss_div.find('img')
        if not img_tag:
            continue
        image_path = img_tag['src']
        
        boss_info = {
            'name': name,
            'level_limit': level_limit,
            'union_id': union_id,
            'image_path': image_path
        }
        boss_list.append(boss_info)
    
    return boss_list

def update_boss_config():
    try:
        # 读取source_code_boss.txt文件
        source_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'source_codes/source_code_boss')
        with open(source_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 解析boss信息
        boss_list = parse_boss_info(html_content)
        
        # 按union_id排序
        boss_list.sort(key=lambda x: x['union_id'])
        
        # 保存到boss_config.json
        config = {'boss_list': boss_list}
        config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs/boss_config.json')
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            
        print(f'成功更新boss配置，共{len(boss_list)}个boss信息')
        
    except Exception as e:
        print(f'更新boss配置失败: {str(e)}')

if __name__ == '__main__':
    update_boss_config()