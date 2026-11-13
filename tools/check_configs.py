"""配置自检：不开浏览器，把每个服的配置表引用关系检查一遍。

用法：
    .venv/bin/python tools/check_configs.py          # 检查 configs/server_address.json 里的所有服
    .venv/bin/python tools/check_configs.py 1        # 只查 1 服

主要查「loop 里的 plan_action_id 在动作配置里不存在」这类错配。
这种错配启动时不会有任何提示，要等挂机跑到那一项时才刷
「未找到动作配置，没有办法处理boss(x)，中止处理。」，然后一直空转。
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.config_consistency import find_missing_action_ids, format_missing


def main():
    wanted = set(sys.argv[1:])
    address_path = os.path.join(BASE_DIR, 'configs', 'server_address.json')
    with open(address_path, 'r', encoding='utf-8') as f:
        servers = json.load(f).get('server_address', [])

    total_problems = 0
    for server in servers:
        if wanted and str(server.get('id')) not in wanted:
            continue
        cfg_dir = os.path.join(BASE_DIR, server.get('config_path', ''))
        loop_path = os.path.join(cfg_dir, server.get('auto_bot_loop_config_path', 'auto_bot_loop_config.json'))
        action_path = os.path.join(cfg_dir, 'action_config_advanced.json')
        print(f"=== {server.get('name')}（{server.get('config_path')}） ===")

        for p in (loop_path, action_path):
            if not os.path.exists(p):
                print(f'  缺文件: {os.path.relpath(p, BASE_DIR)}')
                total_problems += 1

        if not (os.path.exists(loop_path) and os.path.exists(action_path)):
            continue

        with open(loop_path, 'r', encoding='utf-8') as f:
            loop_config = json.load(f)
        with open(action_path, 'r', encoding='utf-8') as f:
            action_config = json.load(f)

        print(f"  loop 配置: {os.path.relpath(loop_path, BASE_DIR)}")
        print(f"  动作组数量: {len(action_config)}")

        missing = find_missing_action_ids(loop_config, action_config)
        if missing:
            total_problems += len(missing)
            print('  ⚠ 配置对不上：')
            for line in format_missing(missing):
                print(f'    - {line}')
        else:
            print('  ✓ 所有动作组引用都能对上')
        print()

    if total_problems:
        print(f'共发现 {total_problems} 处问题')
        return 1
    print('检查完成，没有发现问题')
    return 0


if __name__ == '__main__':
    sys.exit(main())
