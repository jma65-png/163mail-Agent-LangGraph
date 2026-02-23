
from dotenv import load_dotenv
import json
import os
from langgraph.store.base import BaseStore
from langchain_core.messages import SystemMessage
from core.apimodels import get_model_gpt
from core.state import UserPreferences
load_dotenv()

llm = get_model_gpt()
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# MEMORY_FILE = "long_term_memory.json"
MEMORY_FILE = os.path.join(CURRENT_DIR, "..", "long_term_memory.json")

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
    :param store:
    :param namespace:
    :param default_content:
    :return:
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
    :param store:
    :param namespace:
    :param messages:
    :return:
    """
    print(f"正在更新专属档案库: {namespace[1]} ...")

    # 1. 拿出旧档案
    current_prefs = get_memory(store, namespace, "")

    # 2. “三明治强化提示词”
    memory_instructions = f"""你是一个专门负责管理用户偏好的高级档案管理员。

以下是用户当前的偏好档案：
<current_preferences>
{current_prefs}
</current_preferences>

请分析对话记录并更新档案。
【严格要求】：
1. 永远不要覆盖整个配置，只针对性地添加新信息，如果新信息是档案中没有的，请追加到末尾。
2. 只有当用户的最新反馈直接反驳了旧偏好时，才修改旧偏好。
3. 必须原封不动地保留档案中的其他所有现有信息。
4. 保持与原始档案一致的格式。
5. 绝对不要包含 <current_preferences> 或 <updated_preferences> 等任何标签。
6. 绝对不要包含任何开场白或解释文字。
"""

    # 3. 调用模型做总结
    structured_llm = llm.with_structured_output(UserPreferences)
    result = structured_llm.invoke([SystemMessage(content=memory_instructions)] + messages)

    # 4. 把新档案放回抽屉
    new_prefs = result.user_preferences
    store.put(namespace, "preferences", {"preferences": new_prefs})

    print(f"档案 {namespace[1]} 已更新！\n思考过程：{result.chain_of_thought}")
    save_to_disk(store)
