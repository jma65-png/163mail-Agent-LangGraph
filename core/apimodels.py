import os
from langchain.chat_models import init_chat_model

def get_model_gpt():
    return init_chat_model(
        "gpt-4o",
        model_provider="openai",
        temperature=0,
        base_url=os.getenv("OPENAI_API_BASE")
    )


