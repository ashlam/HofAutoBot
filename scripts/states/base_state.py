from scripts.hof_auto_bot_main import HofAutoBot

class BaseState:
    def __init__(self, bot: HofAutoBot):
        self.bot = bot
        self.next_state = None

    def process(self):
        raise NotImplementedError


    def get_next_state(self) -> None:
        return self.next_state

    def on_finish(self):
        pass

    def set_state(self, state):
        self.log(f'set_state: \033[91m{self.__class__.__name__} -> \033[93m{state.__class__.__name__}\033[37m')
        self.bot.switch_to_next_state(state)

    def log(self, msg):
        self.bot.logger.info(msg) 