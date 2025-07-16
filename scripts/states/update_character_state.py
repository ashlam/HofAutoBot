from .base_state import BaseState
from scripts.update_character_source import update_character_source
from scripts.parse_characters import CharacterParser
from .state_factory import StateFactory

class UpdateCharacterState(BaseState):
    """
    更新角色数据状态
    该状态负责进入对应服务器的index2.php页面，然后更新角色数据
    """
    def __init__(self, bot):
        super().__init__(bot)
        self.next_state = None

    def process(self):
        self.log("process: 正在更新角色数据...")
        
        # 获取当前服务器信息
        current_server = self.bot.server_config_manager.current_server_data
        self.next_state = StateFactory.create_prepare_boss_state(self.bot)
        
        # 更新角色数据
        if not update_character_source(self.bot.driver, current_server):
            self.log("更新角色数据失败，请检查网络连接或登录状态")
            self.on_finish()
            return

        # 解析角色数据
        source_file_name = f'source_code_character_{current_server["id"]}'
        parser = CharacterParser(source_file_name, server_id=current_server['id'])
        if parser.parse():
            self.log(f"角色数据更新完成！配置文件位置: {parser.output_json}")
        else:
            self.log("解析角色数据失败")

        # 完成后调用on_finish
        self.on_finish()

    def on_finish(self):
        self.set_state(self.next_state)

    # def set_next_state(self, state):
    #     """
    #     设置完成后要切换到的下一个状态
    #     """
    #     self.next_state = state