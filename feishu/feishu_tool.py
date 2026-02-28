import os
import json
import requests
from dotenv import load_dotenv
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from core.gp import workflow

load_dotenv()
APP_ID = os.getenv("FEISHU_APP_ID")
APP_SECRET = os.getenv("FEISHU_APP_SECRET")

mock_store = InMemoryStore()
memory_saver = MemorySaver()
# from core.memory import load_from_disk
# load_from_disk(mock_store)
agent_app = workflow.compile(store=mock_store, checkpointer=memory_saver)


def get_tenant_access_token() -> str:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {"app_id": APP_ID, "app_secret": APP_SECRET}
    response = requests.post(url, json=payload, proxies={"http": None, "https": None})
    # response = requests.post(url, json=payload)
    data = response.json()
    print(f"DEBUG - Token 响应内容: {data}")
    if data.get("code") != 0:
        print(f"获取 Token 失败: {data.get('msg')}")
        return ""
    return data.get("tenant_access_token")


def send_feishu_card(receive_id: str, card_json: dict):
    token = get_tenant_access_token()
    if not token: return

    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": json.dumps(card_json)
    }
    response = requests.post(url, headers=headers, json=payload, proxies={"http": None, "https": None})
    print(f"发送卡片结果: {response.json()}")


def send_feishu_text(receive_id: str, text: str):
    token = get_tenant_access_token()
    if not token: return
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"receive_id": receive_id, "msg_type": "text", "content": json.dumps({"text": text})}
    response = requests.post(url, json=payload, proxies={"http": None, "https": None})


def build_interrupt_card(interrupt_data: dict) -> dict:
    config = interrupt_data.get("config", {})
    description = interrupt_data.get("description", "暂无详细内容")
    action_req = interrupt_data.get("action_request", {})
    action_name = action_req.get("action", "邮件助手提醒")
    curr_thread_id = interrupt_data.get("thread_id")
    if not curr_thread_id:
        curr_thread_id = action_req.get("args", {}).get("thread_id")

    card_json = {
        "config": {"wide_screen_mode": True},
        "header": {"title": {"tag": "plain_text", "content": f"📧 {action_name}"}, "template": "blue"},
        "elements": [
            {"tag": "markdown", "content": f"**待处理内容：**\n\n{description}"},
            {"tag": "hr"}
        ]
    }

    if config.get("allow_respond") or config.get("allow_edit"):
        card_json["elements"].append({
            "tag": "textarea",
            "name": "user_input_text",
            "placeholder": {
                "tag": "plain_text",
                "content": "如需提供修改意见或直接修改内容，请在此输入..."
            }
        })

    action_elements = []
    if config.get("allow_accept"):
        action_elements.append(
            {"tag": "button", "text": {"tag": "plain_text", "content": "直接发送 / 确认"}, "type": "primary",
             "value": {"type": "accept", "action": action_name, "thread_id": curr_thread_id}})

    if config.get("allow_respond"):
        action_elements.append(
            {"tag": "button", "text": {"tag": "plain_text", "content": "提交修改意见"}, "type": "default",
             "value": {"type": "response", "action": action_name, "thread_id": curr_thread_id}})

    if config.get("allow_edit"):
        action_elements.append(
            {"tag": "button", "text": {"tag": "plain_text", "content": "作为最终版本发送 (Edit)"}, "type": "primary",
             "value": {"type": "edit", "action": action_name, "thread_id": curr_thread_id}})

    if config.get("allow_ignore"):
        action_elements.append(
            {"tag": "button", "text": {"tag": "plain_text", "content": "忽略"}, "type": "danger",
             "value": {"type": "ignore", "action": action_name, "thread_id": curr_thread_id}})

    if action_elements:
        card_json["elements"].append({"tag": "action", "actions": action_elements})

    return card_json


def run_agent_process(thread_id: str, input_data: dict = None, resume_command: Command = None):
    config = {"configurable": {"thread_id": thread_id}}
    run_args = resume_command if resume_command else input_data

    print(f"开始运行 Agent，Thread ID: {thread_id}")
    try:
        for event_data in agent_app.stream(run_args, config=config):
            if "__interrupt__" in event_data:
                interrupt_val = event_data["__interrupt__"][0].value
                actual_data = interrupt_val[0] if isinstance(interrupt_val, list) else interrupt_val

                print(f"触发中断，准备发送飞书卡片...")
                card_json = build_interrupt_card(actual_data)
                target_user_id = actual_data.get("user_id")
                send_feishu_card(receive_id=target_user_id, card_json=card_json)
                return

        send_feishu_text(thread_id, "邮件处理流程已结束。")

    except Exception as e:
        import traceback
        print(f"Agent 运行出错明细:\n{traceback.format_exc()}")  # 打印具体的行号


if __name__ == '__main__':
    token = get_tenant_access_token()
    if token:
        print(f"验证成功！拿到的 Token 是: {token}")
    else:
        print("验证失败")
