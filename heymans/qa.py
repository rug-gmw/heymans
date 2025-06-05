from sigmund.model import model as chatbot_model
from . import prompts
from langchain.schema import HumanMessage, AIMessage, SystemMessage


def get_reply(qa_conversation: dict, model: str,
              max_source: int) -> tuple[str, list]:
    documentation = 'Roses are yellow'
    messages = _prepare_messages(qa_conversation, documentation)
    client = chatbot_model(None, model)
    reply = client.predict(messages)
    return reply, []
    
    
def _prepare_messages(conversation: dict, documentation: str) -> list:
    system_prompt = prompts.QA_PROMPT.render(documentation=documentation)
    messages = [SystemMessage(content=system_prompt)]
    for message in conversation['qa_messages']:
        if message['role'] == 'user':
            messages.append(HumanMessage(content=message['text']))
        elif message['role'] == 'ai':
            messages.append(AIMessage(content=message['text']))
        else:
            raise ValueError(f'invalid message: {message}')
    return messages
