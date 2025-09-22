import random
from .chatbot_model import chatbot_model
from . import prompts
from langchain.schema import HumanMessage, AIMessage, SystemMessage


def get_reply(conversation: dict, model: str) -> tuple[str, bool]:    
    chunk = random.choice(conversation['chunks'])
    messages = _prepare_messages(conversation, chunk['content'])
    client = chatbot_model(model, dummy_reply='Good point')
    reply = client.predict(messages)
    finished = _extract_finished_marker(reply)        
    return reply, finished
    
    
def _prepare_messages(conversation: dict, source: str) -> list:
    system_prompt = prompts.INTERACTIVE_QUIZ_PROMPT.render(source=source)
    messages = [SystemMessage(content=system_prompt)]
    for message in conversation['messages']:
        if message['message_type'] == 'user':
            messages.append(HumanMessage(content=message['text']))
        elif message['message_type'] == 'ai':
            messages.append(AIMessage(content=message['text']))
        else:
            raise ValueError(f'invalid message: {message}')
    return messages


def _extract_finished_marker(reply: str) -> bool:
    return '<FINISHED>' in reply.upper()
