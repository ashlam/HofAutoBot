import json
import re

# 输入输出文件路径
input_path = 'configs/server_02/action_config.json'
output_path = 'configs/server_02/action_config_advanced.json'

def convert_action(action):
    """
    将单个action从旧格式转换为advanced格式
    """
    trigger_type = action.get('trigger_type')
    element_info = action.get('element_info', '')
    value = None
    memo = action.get('_memo')
    # 跳转
    if trigger_type == '跳转':
        # union=xx
        m = re.search(r"union=(\d+)", element_info)
        if m:
            return {'trigger_type': 'click_sub_menu_boss', 'value': f'union={m.group(1)}'}
        # hunt
        if 'hunt' in element_info:
            return {'trigger_type': 'click_main_menu', 'value': 'hunt'}
        # common=xxx
        m = re.search(r"common=([a-zA-Z0-9_]+)", element_info)
        if m:
            return {'trigger_type': 'click_sub_menu_stage', 'value': f'common={m.group(1)}'}
        # 其它菜单
        m = re.search(r"menu=([a-zA-Z0-9_]+)", element_info)
        if m:
            return {'trigger_type': 'click_sub_menu_stage', 'value': f'menu={m.group(1)}'}
        # 其它
        return {'trigger_type': 'click_main_menu', 'value': ''}
    # 按钮
    elif trigger_type == '按钮':
        if 'checkDelAll()' in element_info:
            return {'trigger_type': 'click_button_clear_team', 'value': 'checkDelAll()'}
        if 'union_battle' in element_info:
            return {'trigger_type': 'click_button_start_battle', 'value': 'union_battle'}
        if 'monster_battle' in element_info:
            return {'trigger_type': 'click_button_start_battle', 'value': 'monster_battle'}
        return {'trigger_type': 'click_button_start_battle', 'value': ''}
    # 复选框
    elif trigger_type == '复选框':
        m = re.search(r'name="(char_\d+)"', element_info)
        if m:
            result = {'trigger_type': 'check_box_select_character', 'value': m.group(1)}
            if memo:
                result['_memo'] = memo
            return result
        return {'trigger_type': 'check_box_select_character', 'value': ''}
    # 其它
    return {'trigger_type': trigger_type, 'value': ''}

def convert_group(group):
    new_group = {
        'name': group.get('name', ''),
        'note': group.get('note', ''),
    }
    if 'tag' in group:
        new_group['tag'] = group['tag']
    new_group['actions'] = [convert_action(a) for a in group['actions']]
    return new_group

def main():
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    new_data = {}
    for k, v in data.items():
        new_data[k] = convert_group(v)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    print(f'转换完成，输出文件: {output_path}')

if __name__ == '__main__':
    main() 