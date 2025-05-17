#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from bs4 import BeautifulSoup

# 配置
CHARACTER_PAGE_URL = 'index2.php'
# OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), f'source_codes/source_code_character')

def update_character_source(driver, server):
    if not server:
        server = get_default_server_info()
    if not server:
        print('未找到默认服务器信息，请检查配置文件')
        return False
    server_id = server['id']
    server_url = server['url']
    source_url = f'{server_url}{CHARACTER_PAGE_URL}'
    output_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), f'source_codes/source_code_character_{server_id}')
    print(source_url)
    try:
        # 导航到角色数据页面
        driver.get(source_url)
        
        # 使用BeautifulSoup解析页面源码
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 提取目标div内容
        content_div = soup.find('div', id='Jq_Conten')
        if not content_div:
            raise ValueError('未找到目标内容块(div id="Jq_Conten")')
        
        # 保存到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(str(content_div))
            
        print(f'成功更新角色数据源文件: {output_file}')
        return True
        
    except Exception as e:
        print(f'更新角色数据源文件失败: {str(e)}')
        return False

def get_default_server_info():
    config_path = os.path.join(os.path.dirname(__file__), 'configs','server_address.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        server_config = json.load(f)
        return server_config['server_address'][0]


if __name__ == '__main__':
    update_character_source()