from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic

client = Anthropic()
model = "claude-sonnet-4-5"

# The default system prompt is defined below, but can be overridden via parameters:
# system_prompt = "You are a patient math tutor. Do not give the answer directly, but guide the user to the answer. Guide them to an answer step by step."

def chat(messages, system_prompt: str = ""):
    params = {
        "model": model,
        "max_tokens": 1000,
        "messages": messages,
    }
    if system_prompt:
        params["system"] = system_prompt
    message = client.messages.create(**params)

    return message.content[0].text

def add_user_message(messages, text):
    user_message = {"role": "user", "content": text}
    messages.append(user_message)

def add_assistant_message(messages, text):
    assistant_message = {"role": "assistant", "content": text}
    messages.append(assistant_message)