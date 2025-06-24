
from scripts.hof_auto_bot_main import HofAutoBot

class BaseState:
    def __init__(self, bot: HofAutoBot):
        self.bot = bot
        self.next_state = None

    def process(self):
        raise NotImplementedError

    def on_finish(self):
        pass

    def set_state(self, state):
        self.bot._set_state(state)

    def log(self, msg):
        self.bot.logger.info(msg) 