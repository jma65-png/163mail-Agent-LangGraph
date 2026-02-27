import os

from dotenv import load_dotenv

load_dotenv()
from langchain.chat_models import init_chat_model


def get_llm(model_name="gpt-4o"):
    """
    根据传入的模型名称动态初始化 LLM，默认为gpt-4o
    """
    return init_chat_model(
        model_name,
        model_provider="openai",
        temperature=0,
        base_url=os.getenv("OPENAI_API_BASE")
    )


if __name__ == "__main__":
    llm = get_llm("gpt-4o")
    try:
        message = {"role": "user", "content": "请输出你的模型号"}
        response = llm.invoke([message])
        print(response.content)
    except Exception as e:
        print(f"报错了：{e}")
