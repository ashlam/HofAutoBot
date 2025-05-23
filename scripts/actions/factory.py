from scripts.actions import ClickActionExecutor, NavigateActionExecutor, CheckboxActionExecutor

class ActionExecutorFactory:
    _executors = {
        '按钮': ClickActionExecutor(),
        '跳转': NavigateActionExecutor(),
        '复选框': CheckboxActionExecutor()
    }

    @classmethod
    def get_executor(cls, trigger_type):
        """根据触发类型获取对应的动作执行器"""
        executor = cls._executors.get(trigger_type)
        if not executor:
            raise ValueError(f'不支持的动作类型: {trigger_type}')
        return executor