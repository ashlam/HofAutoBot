#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from math import fabs
import re
import os
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path

class CharacterParser:
    def __init__(self, source_file_name = 'source_code_character_1', server_id = 1, download_images=False):
        # 配置
        self.html_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'source_codes', source_file_name)
        # 从server_address.json读取服务器配置
        server_address_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'configs/server_address.json')
        with open(server_address_file, 'r', encoding='utf-8') as f:
            server_config = json.load(f)
            # 根据server_id获取对应服务器配置
            server = next((s for s in server_config['server_address'] if s['id'] == server_id), None)
            if not server:
                raise ValueError(f'未找到ID为{server_id}的服务器配置')
            self.base_url = server['url']
            self.output_json = os.path.join(os.path.dirname(os.path.dirname(__file__)), server['config_path'], 'character_config.json')
        self.image_dir = 'images/characters'
        self.download_images = download_images
        self.characters = []

        # 确保图片目录存在
        if self.download_images:
            os.makedirs(self.image_dir, exist_ok=True)

    def read_html_content(self):
        """读取HTML文件内容"""
        with open(self.html_file, 'r', encoding='utf-8') as f:
            return f.read()

    def parse_job_name(self, li, name, level):
        """解析职业名称"""
        text_content = li.get_text()
        job_match = re.search(fr'{name}.*?Lv\.{level}\s+(.*?)(?:\s*\*|\s*$|\s*<)', text_content)
        if job_match:
            return job_match.group(1).strip()

        # 备用方法：从所有文本中查找
        text_parts = [t for t in li.stripped_strings]
        for part in text_parts:
            if 'Lv.' in part and level in part:
                return part.replace(f'Lv.{level}', '').strip()
        return "未知"

    def get_image_paths(self, img_url):
        """获取图片相关路径"""
        if img_url.startswith('./image/'):
            img_path = img_url[8:]  # 移除 './image/' 前缀
            full_img_url = f"{self.base_url}image/{img_path}"
        else:
            full_img_url = self.base_url + img_url

        img_filename = os.path.basename(img_url)
        local_img_path = os.path.join(os.getcwd(), self.image_dir, img_filename)
        relative_img_path = os.path.join(self.image_dir, img_filename)
        return full_img_url, local_img_path, relative_img_path

    def download_image(self, full_img_url, local_img_path):
        """下载角色图片"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(full_img_url, headers=headers, timeout=10)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(local_img_path), exist_ok=True)
                with open(local_img_path, 'wb') as img_file:
                    img_file.write(response.content)
                print(f"下载图片成功: {os.path.basename(local_img_path)} 到 {local_img_path}")
                return True
            else:
                print(f"下载图片失败: {full_img_url}, 状态码: {response.status_code}")
                return False
        except Exception as e:
            print(f"下载图片出错: {full_img_url}, 错误: {str(e)}")
            return False

    def parse_character(self, li):
        """解析单个角色信息"""
        try:
            # 提取角色ID
            onclick_attr = li.select_one('a[onclick]')['onclick']
            udid = re.search(r'RA_Charback\(([0-9]+)\)', onclick_attr).group(1)
            
            # 提取装备信息
            equipment = li.select_one('a[title]')['title']
            
            # 提取图片URL
            img_url = li.select_one('img')['src']
            
            # 提取角色名称
            name = li.select_one('span[data-type="name"]').text.strip()
            name = re.sub(r'\s*\*\s*', '', name).strip()
            
            # 提取等级
            level = li.select_one('span[data-type="level"]').text.strip()
            
            # 提取职业名称
            job_name = self.parse_job_name(li, name, level)
            
            # 提取基础属性和职业ID
            base = li.select_one('span[data-type="base"]').text
            job = li.select_one('span[data-type="job"]').text
            
            # 处理图片相关路径
            full_img_url, local_img_path, relative_img_path = self.get_image_paths(img_url)
            
            # 下载图片（如果启用）
            if self.download_images:
                if self.download_image(full_img_url, local_img_path):
                    local_img_path = relative_img_path
                else:
                    local_img_path = ""
            else:
                local_img_path = ""

            # 创建角色数据
            return {
                "name": name,
                "job_name": job_name,
                "level": level,
                "job": job,
                "udid": udid,
                "base": base,
                "equipment": equipment,
                "img_url": full_img_url,
                "local_img": local_img_path
            }
        except Exception as e:
            print(f"处理角色信息时出错: {str(e)}")
            return None

    def save_to_json(self):
        """保存角色数据到JSON文件"""
        try:
            # 检查是否已存在配置文件
            existing_data = {}
            if os.path.exists(self.output_json):
                try:
                    with open(self.output_json, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        print(f"读取现有配置文件: {self.output_json}")
                except json.JSONDecodeError:
                    print(f"现有配置文件格式错误，将创建新文件")

            # 更新或创建角色数据
            existing_data["characters"] = self.characters

            # 写入JSON文件
            with open(self.output_json, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)

            print(f"成功提取 {len(self.characters)} 个角色信息并保存到 {self.output_json}")
            if self.download_images:
                print(f"角色图片已保存到 {self.image_dir} 目录")
        except Exception as e:
            print(f"保存JSON文件时出错: {str(e)}")

    def parse(self):
        """执行角色数据解析的主要流程"""
        try:
            # 读取并解析HTML
            html_content = self.read_html_content()
            soup = BeautifulSoup(html_content, 'html.parser')
            li_elements = soup.select('li[data-id]')

            # 解析每个角色信息
            for li in li_elements:
                character = self.parse_character(li)
                if character:
                    self.characters.append(character)

            # 保存到JSON文件
            self.save_to_json()
            print("处理完成！")
            return True
        # except Exception as e:
        #     print(f"解析过程出错: {str(e)}")
        #     return False
        finally:
            print("处理fffffff处理完成！")
            return True

def main(download_images=False):
    parser = CharacterParser(download_images)
    parser.parse()

if __name__ == '__main__':
    main()