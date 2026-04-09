import time
from sigmund.model import model as sigmund_model
from sigmund import static
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


def static_predict(prompt: str, model: str, json: bool,
                   dummy_reply: str = 'dummy reply') -> str:
    """Predicts a static reply for a given model.  This is used for testing
    purposes.
    """
    static.db_initialized = True
    if config.dummy_model:
        return dummy_reply
    return static.predict(prompt, model, json)
