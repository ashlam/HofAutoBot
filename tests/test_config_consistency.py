"""配置一致性检查的单元测试。

对应线上真实踩过的坑：loop 里 boss 12 写了 plan_action_id=600121，
但 action_config_advanced.json 里只有 600122，于是跑到 boss 12 只会刷
「未找到动作配置，没有办法处理boss(12)，中止处理。」然后一直空转。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config_consistency import find_missing_action_ids, format_missing


def test_detects_wrong_boss_action_id():
    loop = {
        'normal_boss_loop_order': [
            {'union_id': 17, 'plan_action_id': 600170},
            {'union_id': 12, 'plan_action_id': 600121},
        ],
    }
    acts = {'600170': {}, '600122': {}}

    missing = find_missing_action_ids(loop, acts)

    assert len(missing) == 1
    assert missing[0]['field'] == 'normal_boss_loop_order'
    assert missing[0]['target'] == 12
    assert missing[0]['action_id'] == 600121


def test_no_problem_when_everything_matches():
    loop = {
        'normal_boss_loop_order': [{'union_id': 12, 'plan_action_id': 600122}],
        'vip_boss_need_watch': [{'union_id': 17, 'plan_action_id': 600170}],
        'normal_stage_loop_order': [{'stage_name': 'ocean1', 'plan_action_id': 1}],
        'pvp_plan_action_id': 2,
        'challenge_boss_cooldown_seconds': 1200,
    }
    acts = {'600122': {}, '600170': {}, '1': {}, '2': {}}

    assert find_missing_action_ids(loop, acts) == []


def test_scalar_plan_action_id_fields_are_checked():
    loop = {
        'pvp_plan_action_id': 2,
        'world_pvp_plan_action_id': 3,
        'challenge_boss_delay_rate': 0.5,
    }
    acts = {'2': {}}

    missing = find_missing_action_ids(loop, acts)

    assert [m['field'] for m in missing] == ['world_pvp_plan_action_id']
    assert missing[0]['target'] == ''


def test_int_and_str_action_ids_are_treated_as_same():
    loop = {'normal_boss_loop_order': [{'union_id': 12, 'plan_action_id': 600122}]}
    acts = {600122: {}}  # JSON 里 key 一定是 str，这里故意给 int

    assert find_missing_action_ids(loop, acts) == []


def test_format_missing_mentions_field_and_id():
    missing = find_missing_action_ids(
        {'normal_boss_loop_order': [{'union_id': 12, 'plan_action_id': 600121}]},
        {'600122': {}},
    )
    text = '\n'.join(format_missing(missing))

    assert 'normal_boss_loop_order' in text
    assert '600121' in text
    assert '12' in text


if __name__ == '__main__':
    test_detects_wrong_boss_action_id()
    test_no_problem_when_everything_matches()
    test_scalar_plan_action_id_fields_are_checked()
    test_int_and_str_action_ids_are_treated_as_same()
    test_format_missing_mentions_field_and_id()
    print('ok')
