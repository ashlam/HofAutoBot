"""配置表一致性检查。

目前只查一类问题：loop 配置里引用的行动组 id（plan_action_id）是不是真的存在于
action_config_advanced.json 里。

这类错配不会在启动时报错，只会在跑到那一条循环项时刷「未找到动作配置，没有办法处理boss(x)，
中止处理。」然后一直空转 —— 从日志里要翻很久才看得出来。所以在启动和热重载时各查一遍，
有问题尽早喊出来。

设计上只做"引用 → 是否存在"的检查，不判断哪个 id 才是对的（那是业务判断）。
"""

# 这些顶层字段是"单个动作组 id"，不放在列表里
_SCALAR_ID_SUFFIX = '_plan_action_id'


def collect_action_id_refs(loop_config):
    """从 loop 配置里收集所有 plan_action_id 引用。

    返回 [(来源字段, 对象标识, 动作组id), ...]，
    对象标识优先用 union_id / stage_name，取不到就留空。
    """
    refs = []
    if not isinstance(loop_config, dict):
        return refs

    for field, value in loop_config.items():
        # 列表形式：normal_boss_loop_order / normal_stage_loop_order / vip_boss_need_watch ...
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and 'plan_action_id' in item:
                    label = item.get('union_id', item.get('stage_name', ''))
                    refs.append((field, label, item.get('plan_action_id')))
        # 单个 id 形式：pvp_plan_action_id / world_pvp_plan_action_id ...
        elif isinstance(value, dict) and 'plan_action_id' in value:
            label = value.get('union_id', value.get('stage_name', ''))
            refs.append((field, label, value.get('plan_action_id')))
        elif field.endswith(_SCALAR_ID_SUFFIX) and isinstance(value, (int, str)) and not isinstance(value, bool):
            refs.append((field, '', value))

    return refs


def find_missing_action_ids(loop_config, action_config):
    """返回 loop 里引用了、但动作配置里不存在的动作组。

    结果形如 [{'field': 'normal_boss_loop_order', 'target': 12, 'action_id': 600121}]
    """
    action_keys = set()
    if isinstance(action_config, dict):
        action_keys = {str(k) for k in action_config.keys()}

    missing = []
    for field, target, action_id in collect_action_id_refs(loop_config):
        if action_id is None:
            continue
        if str(action_id) not in action_keys:
            missing.append({'field': field, 'target': target, 'action_id': action_id})
    return missing


def format_missing(missing):
    """把缺失项整理成一行行好读的文案。"""
    lines = []
    for m in missing:
        target = m['target']
        where = f"{m['field']}"
        if target not in ('', None):
            where += f"（boss/关卡 {target}）"
        lines.append(f"{where} 引用了动作组 {m['action_id']}，但动作配置里没有这个 id")
    return lines
