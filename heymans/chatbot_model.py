import time
import random
from sigmund.model import model as sigmund_model
from sigmund import static
from . import config


class Dummy:
    def __init__(self, reply='dummy reply'):
        self.reply = reply

    def predict(self, *args, **kwargs):
        time.sleep(random.uniform(*config.dummy_delay_range))
        return self.reply


def chatbot_model(model: str, dummy_reply: str = 'dummy reply') -> object:
    """Initializes a Sigmund chatbot model, or a dummy model if we're running
    in dummy mode. 
    """
    if config.dummy_model:
        return Dummy(reply=dummy_reply)
    return sigmund_model(None, model, strip_thinking_blocks=True)


def static_predict(prompt: str, model: str, json: bool,
                   dummy_reply: str = 'dummy reply') -> str:
    """Predicts a static reply for a given model.  This is used for testing
    purposes.
    """
    static.db_initialized = True
    if config.dummy_model:
        time.sleep(random.uniform(*config.dummy_delay_range))
        return dummy_reply    
    return static.predict(prompt, model, json)
