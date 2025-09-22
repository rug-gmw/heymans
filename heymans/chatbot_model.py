import time
from sigmund.model import model as sigmund_model
from . import config


class Dummy:
    def __init__(self, reply='dummy reply', delay=0):
        self.reply = reply
        self.delay = delay

    def predict(self, *args, **kwargs):
        time.sleep(self.delay)
        return self.reply


def chatbot_model(model: str, dummy_reply: str = 'dummy reply') -> object:
    """Initializes a Sigmund chatbot model, or a dummy model if we're running
    in dummy mode. 
    """
    if config.dummy_model:
        return Dummy(reply=dummy_reply, delay=config.dummy_delay)
    return sigmund_model(None, model)
