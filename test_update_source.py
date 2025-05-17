#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from selenium import webdriver
import os
import sys
import json

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from scripts.update_character_source import update_character_source
from scripts.parse_characters import CharacterParser

def main():
    # 从server_address.json读取服务器配置
    config_path = os.path.join(os.path.dirname(__file__), 'configs', 'server_address.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        server_config = json.load(f)
    
    # 显示服务器列表供用户选择
    print('请选择要连接的服务器:')
    for server in server_config['server_address']:
        print(f"{server['id']}、{server['name']}")
    
    while True:
        try:
            choice = int(input('请输入服务器序号: '))
            # 检查输入是否有效
            server = next((s for s in server_config['server_address'] if s['id'] == choice), None)
            if server:
                url = server['url']
                break
            else:
                print('无效的选择，请重新输入。')
        except ValueError:
            print('请输入有效的数字。')
    
    driver = webdriver.Chrome()
    driver.get(url)
    print('正在打开浏览器...')
    # 等待用户确认
    while True:
        user_input = input('是否已准备好更新角色数据？(y/yes继续，其他键退出): ').lower()
        if user_input not in ['y', 'yes']:
            print('已取消更新操作')
            break
            
        print('开始更新角色数据...')
        # 更新角色数据源文件
        if not update_character_source(driver, server):
            print('更新角色数据源文件失败，请检查网络连接或登录状态')
            continue
            
        # 执行角色数据解析
        try:
            source_file_name = f'source_code_character_{server["id"]}'
            # 创建解析器实例并执行解析
            parser = CharacterParser(source_file_name, server_id=server['id'])
            if parser.parse():
                print(f'\n角色数据更新完成！\n更新后的配置文件位置: {parser.output_json}')
                break
            
        except Exception as e:
            print(f'解析角色数据时出错: {str(e)}')
            # 关闭浏览器
            driver.quit()
            continue

if __name__ == '__main__':
    main()