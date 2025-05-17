from .action_executor import ActionExecutor

def execute_action_group(driver, action_group_configs, group_id, all_action_config_by_server):
    """执行指定ID的动作组"""
    while True:  # 使用无限循环来处理动作组之间的跳转
        # 加载动作组配置
        action_group = action_group_configs.get(f"{group_id}")
        if not action_group:
            return False
        
        print(f"\n开始执行动作组: {action_group['name']}")
        print(f"说明: {action_group['note']}")
        
        # 获取动作配置列表
        group_action_configs = action_group['action_configs']
        if not group_action_configs:
            print("动作组中没有配置动作")
            return False
        
        # 执行第一个动作配置
        current_config_index = 0
        
        while current_config_index < len(group_action_configs):
            # 获取当前要执行的动作配置
            current_action_config = group_action_configs[current_config_index]
            action_id = current_action_config['action_id']
            is_loop = current_action_config['is_loop']
            loop_times = current_action_config['loop_times']
            
            # 加载动作配置
            target_action_config = all_action_config_by_server.get(f"{action_id}")
            if not target_action_config:
                return False
            
            # 如果是循环动作，执行指定次数
            if is_loop:
                # 如果loop_times小于等于0，表示无限循环，这里设置一个较大的值
                actual_loop_times = 999999 if loop_times <= 0 else loop_times
                
                print(f"\n开始循环执行动作 {target_action_config['name']} {actual_loop_times} 次")
                
                for i in range(actual_loop_times):
                    print(f"\n第 {i+1} 次循环执行:")
                    execute_actions(driver, target_action_config)
                    
                    # 如果用户想中断循环，可以在这里添加检查逻辑
                    # 例如检查某个元素是否存在，或者其他条件
            else:
                # 非循环动作，执行一次
                print(f"\n执行单次动作: {target_action_config['name']}")
                action_success = execute_actions(driver, target_action_config)
                
                # 如果动作执行失败且有jump_end_id，直接跳转到下一个动作
                if not action_success:
                    current_config_index += 1
                    next_config_found = True
                    print(f"当前动作（{target_action_config['name']}）执行失败，直接跳到后面的动作: ")
                    continue
            
            # 检查是否需要跳转到其他动作组
            if 'jump_to_action_group_id' in current_action_config:
                next_group_id = current_action_config['jump_to_action_group_id']
                print(f"\n跳转到动作组: {next_group_id}")
                group_id = next_group_id  # 更新group_id，准备执行下一个动作组
                break  # 跳出当前动作组的循环
            
            # 如果没有指定跳转到其他动作组，则继续执行当前动作组中的下一个动作配置
            current_config_index += 1
            if current_config_index >= len(group_action_configs):
                print("已执行完所有动作配置")
                return True  # 如果没有跳转指令，则结束执行