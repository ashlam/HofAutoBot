import json
import re
from typing import Dict, List, Optional, Union

class ConditionChecker:
    def __init__(self, condition_config_path: str):
        with open(condition_config_path, 'r', encoding='utf-8') as f:
            self.condition_config = json.load(f)
    
    def _extract_placeholder_value(self, element_content: str, element_pattern: str) -> Dict[str, str]:
        """从页面元素内容中提取占位符的值
        
        Args:
            element_content: HTML页面内容
            element_pattern: 包含占位符的模式字符串
            
        Returns:
            包含占位符及其对应值的字典
        """
        print(f"\n开始提取占位符值")
        print(f"元素内容: {element_content}")
        print(f"元素模式: {element_pattern}")
        
        # 找到所有的占位符
        placeholders = re.findall(r'\${([^}]+)}', element_pattern)
        print(f"找到的占位符: {placeholders}")
        
        # 构建正则表达式模式
        pattern = element_pattern
        
        # 转义特殊字符，但保留占位符部分
        pattern_parts = []
        last_end = 0
        for match in re.finditer(r'\${([^}]+)}', element_pattern):
            # 添加占位符之前的部分（需要转义）
            pattern_parts.append(re.escape(element_pattern[last_end:match.start()]))
            # 添加占位符的捕获组，允许匹配任意字符（包括换行符）
            pattern_parts.append(f'(.*?)')
            last_end = match.end()
        # 添加最后一部分（如果有的话）
        if last_end < len(element_pattern):
            pattern_parts.append(re.escape(element_pattern[last_end:]))
        
        # 组合正则表达式，设置re.DOTALL标志以允许.匹配换行符
        pattern = ''.join(pattern_parts)
        print(f"构建的正则表达式: {pattern}")
        
        # 使用正则表达式匹配并提取值，设置re.DOTALL标志以允许.匹配换行符
        match = re.search(pattern, element_content, re.DOTALL)
        if not match:
            print("未找到匹配的内容")
            return {}
        
        # 提取并清理匹配的值
        values = []
        for group in match.groups():
            # 移除引号和多余的空白字符
            cleaned_value = group.strip(' \t\n\r"\'')
            values.append(cleaned_value)
        
        result = dict(zip(placeholders, values))
        print(f"提取的结果: {result}")
        return result
    
    def _validate_condition(self, placeholder_value: str, target_value: Union[str, int], validation_type: str) -> bool:
        """验证提取的值是否满足条件"""
        if validation_type == "EQUAL":
            return str(placeholder_value) == str(target_value)
        elif validation_type == "NOT_EQUAL":
            return str(placeholder_value) != str(target_value)
        elif validation_type == "GREATER_THAN":
            try:
                return float(placeholder_value) > float(target_value)
            except ValueError:
                return False
        elif validation_type == "LESS_THAN":
            try:
                return float(placeholder_value) < float(target_value)
            except ValueError:
                return False
        return False

    def check_condition(self, condition_id: str, page_content: str) -> Optional[int]:
        """检查指定ID的条件组是否满足
        
        Args:
            condition_id: 条件配置的ID
            page_content: 当前页面的HTML内容
            
        Returns:
            如果找到匹配的条件，返回对应的action_group_id；否则返回None
        """
        print(f"\n开始检查条件ID: {condition_id}")
        if condition_id not in self.condition_config:
            print(f"未找到ID为{condition_id}的条件配置")
            return None

        conditions = self.condition_config[condition_id]['conditions']
        print(f"找到{len(conditions)}个条件需要检查")
        
        i = 0
        while i < len(conditions):
            condition = conditions[i]
            print(f"\n正在检查第{i + 1}个条件:")
            print(f"条件内容: {condition}")
            result = condition.get('default_result', False)
            print(f"默认结果: {result}")
            
            # 如果有element_info，则需要进行实际检查
            if condition.get('element_info'):
                # 在页面内容中查找指定元素
                element_pattern = condition['element_info']
                print(f"检查元素模式: {element_pattern}")
                if re.search(element_pattern.replace('${', '.*?').replace('}', '.*?'), page_content):
                    print("找到匹配的元素")
                    # 提取占位符的值
                    placeholder_values = self._extract_placeholder_value(page_content, element_pattern)
                    print(f"提取的占位符值: {placeholder_values}")
                    
                    # 验证所有条件
                    if 'validation' in condition:
                        result = True
                        for validation in condition['validation']:
                            placeholder = validation['value_of_placeholder']
                            print(f"\n验证占位符 '{placeholder}'")
                            if placeholder not in placeholder_values:
                                print(f"未找到占位符 '{placeholder}' 的值，使用默认结果")
                                result = condition.get('default_result', False)
                                break
                            
                            validation_result = self._validate_condition(
                                placeholder_values[placeholder],
                                validation['target_value'],
                                validation['type']
                            )
                            print(f"验证类型: {validation['type']}")
                            print(f"比较值: {placeholder_values[placeholder]} {validation['type']} {validation['target_value']}")
                            print(f"验证结果: {validation_result}")
                            
                            if not validation_result:
                                result = False
                                print("验证失败，终止检查其他条件")
                                break
                else:
                    print("未找到匹配的元素，使用默认结果")
                    result = condition.get('default_result', False)
            
            print(f"\n当前条件最终结果: {result}")
            
            # 如果当前条件满足且需要与下一个条件进行AND操作
            if result and condition.get('contract_below', False) and i + 1 < len(conditions):
                print("条件满足且需要与下一个条件进行AND操作，继续检查")
                i += 1
                continue
            
            # 如果当前条件满足且不需要继续检查，返回对应的action_group_id
            if result:
                action_group_id = condition.get('jump_to_action_group_id')
                print(f"条件满足，跳转到动作组: {action_group_id}")
                return action_group_id
            
            print("条件不满足，检查下一个条件")
            i += 1
        
        print("所有条件检查完毕，未找到匹配的条件")
        return None