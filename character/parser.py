from bs4 import BeautifulSoup
from typing import List
from .models import Character

class CharacterParser:
    @staticmethod
    def parse_html(html_data: str) -> List[Character]:
        soup = BeautifulSoup(html_data, 'html.parser')
        characters = []
        
        for li in soup.find_all('li', attrs={'data-id': True}):
            try:
                # 获取角色顺序
                order = li['data-id'].split('-')[1]
                
                # 获取角色ID
                checkbox = li.find('input', type='checkbox')
                char_id = checkbox['name'].replace('char_', '')
                
                # 获取角色名和职业信息
                text_div = li.find('div', id=lambda x: x and x.startswith('text'))
                name = text_div.contents[0].strip()
                job_info = text_div.contents[-1].strip()
                
                # 获取详细信息
                info_div = li.find('div', style='display:none')
                level = info_div.find('span', attrs={'data-type': 'level'}).text
                job_type = li['data-type']
                
                character = Character(
                    id=char_id,
                    name=name,
                    order=int(order),
                    job_info=job_info,
                    level=level,
                    type=job_type
                )
                characters.append(character)
            except Exception as e:
                print(f"解析错误: {str(e)}")
        
        # 按顺序排序
        characters.sort(key=lambda x: x.order)
        return characters 