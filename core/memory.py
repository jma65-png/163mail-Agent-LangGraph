from dotenv import load_dotenv
import json
import os
from langgraph.store.base import BaseStore
from langchain_core.messages import SystemMessage
from core.models import get_llm
from core.scheme import Userpreference
from agents.memory_prompt import memory_instructions
from agents.agent_prompt import default_triage_instructions, default_response_preferences, default_cal_preferences

load_dotenv()
llm = get_llm()

CURRENT_FILE_PATH = os.path.abspath(__file__)
CURRENT_DIR = os.path.dirname(CURRENT_FILE_PATH)
MEMORY_FILE = os.path.normpath(os.path.join(CURRENT_DIR, "..", "long_term_memory.json"))


def save_to_disk(store: BaseStore):
    """把内存里的所有抽屉同步到 JSON 文件里"""
    data = {}
    namespaces = [
        ("email_assistant", "triage_preferences"),
        ("email_assistant", "response_preferences"),
        ("email_assistant", "cal_preferences")
    ]
    for ns in namespaces:
        item = store.get(ns, "preferences")
        if item:
            data["|".join(ns)] = item.value["preferences"]

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"数据已写入硬盘文件: {MEMORY_FILE}")


def load_from_disk(store: BaseStore):
    """程序启动时，把 JSON 文件里的内容塞回内存档案柜"""
    if not os.path.exists(MEMORY_FILE):
        return

    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        for key, value in data.items():
            # 把字符串 Key 还原回原来的 namespace 元组
            ns = tuple(key.split("|"))
            store.put(ns, "preferences", {"preferences": value})
    print(f"已从硬盘恢复历史档案。")


def get_memory(store: BaseStore, namespace: tuple, default_content: str) -> str:
    """
    辅助函数：去指定的抽屉（namespace）拿档案，没有就用默认值
    """

    memory_item = store.get(namespace, "preferences")

    if memory_item:
        return memory_item.value.get("preferences", default_content)
    else:
        # 如果是新抽屉，先把默认的规矩塞进去打底，防止下次来还是空的
        store.put(namespace, "preferences", {"preferences": default_content})
        return default_content


def update_memory(store: BaseStore, namespace: tuple, messages: list):
    """
    辅助函数：分析指定的对话，即时更新专属抽屉（namespace）的记忆

    """
    print(f"正在更新专属档案库: {namespace[1]} ...")

    # 1. 拿出旧档案
    current_prefs = get_memory(store, namespace, "")

    # 2. “三明治强化提示词”
    memory = memory_instructions.format(current_prefs=current_prefs)
    # 3. 调用模型做总结
    llm = get_llm()
    structured_llm = llm.with_structured_output(Userpreference)
    result = structured_llm.invoke([SystemMessage(content=memory)] + messages)

    # 4. 把新档案放回抽屉
    new_prefs = result.preferences
    store.put(namespace, "preferences", {"preferences": new_prefs})

    print(f"档案 {namespace[1]} 已更新！\n思考过程：{result.reasoning}")
    save_to_disk(store)


if __name__ == '__main__':
    from langgraph.store.memory import InMemoryStore

    mock_store = InMemoryStore()
    test_data = {
        ("email_assistant", "triage_preferences"): default_triage_instructions,
        ("email_assistant", "response_preferences"): default_response_preferences,
        ("email_assistant", "cal_preferences"): default_cal_preferences
    }
    for ns, content in test_data.items():
        mock_store.put(ns, "preferences", {"preferences": content})

    save_to_disk(mock_store)

    load_from_disk(mock_store)
    test_namespace = ("email_assistant", "response_preferences")
    default_text = default_response_preferences
    first_call = get_memory(mock_store, test_namespace, default_text)

    print(f"获取到的偏好内容前50字: {first_call[:50]}...")

    test_messages = [
        {"role": "user", "content": "以后给面试邀请回信时，落款不要写‘张煦’了，请改写成‘小张’，这样显得亲切一点。"}
    ]

    update_memory(mock_store, test_namespace, test_messages)

    updated_call = get_memory(mock_store, test_namespace, default_text)
    print(f"更新后的偏好全文预览：\n{updated_call}")
