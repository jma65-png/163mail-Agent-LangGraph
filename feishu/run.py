import sys
import os
from fastapi import FastAPI, Request, BackgroundTasks
import uvicorn
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.gp import workflow
from feishu.feishu_tool import run_agent_process, send_feishu_card, build_interrupt_card, send_feishu_text
from utils.email_163 import fetch_latest_163_email

app = FastAPI()

agent_app = workflow.compile(store=InMemoryStore(), checkpointer=MemorySaver())


def run_agent_worker(thread_id: str, input_data: dict = None, resume_command: Command = None, user_id: str = None):
    config = {"configurable": {"thread_id": thread_id}}
    run_args = resume_command if resume_command else input_data
    # {
    #     "__interrupt__": (
    #         Interrupt(
    #             value={
    #                 "user_id": "ou_xxx",
    #                 "action": "confirm_email",
    #                 "draft": "亲爱的张同学..."
    #             },
    #             resumable=True,
    #             ns=["node_name:execution_id"]
    #         ),
    #     )
    # }
    for event_data in agent_app.stream(run_args, config=config):
        if "__interrupt__" in event_data:
            interrupt_val = event_data["__interrupt__"][0].value
            actual_data = interrupt_val[0] if isinstance(interrupt_val, list) else interrupt_val
            card_json = build_interrupt_card(actual_data)
            target_user_id = actual_data.get("user_id") or user_id
            send_feishu_card(receive_id=target_user_id, card_json=card_json)
            return
    if user_id:
        send_feishu_text(user_id, "流程处理完毕。")


@app.post("/webhook/event")
async def event_handler(request: Request, background_tasks: BackgroundTasks):
    print("收到飞书事件请求！")
    body = await request.json()
    if "challenge" in body:
        return {"challenge": body["challenge"]}
    event = body.get("event", {})
    open_id = event.get("sender", {}).get("sender_id", {}).get("open_id")

    if open_id:
        send_feishu_text(open_id, "正在为您拉取 163 邮箱的最新邮件，请稍候...")
        email_data = fetch_latest_163_email()
        if isinstance(email_data, dict):
            current_thread_id = email_data.get("thread_id")
            email_data["user_id"] = open_id
            real_input = {"email_input": email_data}
            background_tasks.add_task(
                run_agent_worker,
                thread_id=current_thread_id,
                input_data=real_input,
                user_id=open_id
            )
        else:
            send_feishu_text(open_id, f"拉取邮件失败:\n{email_data}")
    return {"msg": "ok"}


# import uuid
#
#
#
# @app.post("/webhook/event")
# async def event_handler(request: Request, background_tasks: BackgroundTasks):
#     print("(本地 Mock 测试模式)")
#     body = await request.json()
#     if "challenge" in body:
#         return {"challenge": body["challenge"]}
#
#     event = body.get("event", {})
#     open_id = event.get("sender", {}).get("sender_id", {}).get("open_id")
#
#     if open_id:
#         send_feishu_text(open_id, "本地 Mock")
#
#
#         new_thread_id = str(uuid.uuid4())
#         mock_email_data = {
#             "author": "面试官 <2606075@qq.com>",
#             "to": "majan04@163.com",
#             "subject": "【Mock测试】Python开发工程师面试邀约",
#             "email_thread": "张同学你好：\n\n很高兴收到你的简历。你的 AI Agent 项目经历与我们非常契合。想邀请你本周五下午 14:00 进行远程面试。\n\n请确认是否方便？",
#             "thread_id": new_thread_id,  # 找“事”的 ID
#             "user_id": open_id  # 找“人”的 ID
#         }
#
#         real_input = {"email_input": mock_email_data}
#         background_tasks.add_task(
#             run_agent_worker,
#             thread_id=new_thread_id,
#             input_data=real_input,
#             user_id=open_id
#         )
#
#     return {"msg": "ok"}

@app.post("/webhook/card")
async def card_handler(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        return {"error": "Invalid JSON"}

    if isinstance(body, dict) and "challenge" in body:
        return {"challenge": body["challenge"]}

    if body.get("schema") != "2.0":
        return {"toast": {"type": "info", "content": "忽略V1"}}

    event_data = body.get("event", {})
    open_id = event_data.get("operator", {}).get("open_id")

    action_data = event_data.get("action", {})
    action_value = action_data.get("value", {})  # 按钮本身绑定的值
    form_value = action_data.get("form_value", {})  # 卡片上所有输入框的值

    current_thread_id = action_value.get("thread_id")

    user_input_text = form_value.get("user_input_text", "")

    if action_value.get("type") in ["response", "edit"]:
        action_value["args"] = user_input_text

    if open_id and action_value and current_thread_id:
        background_tasks.add_task(
            run_agent_worker,
            thread_id=current_thread_id,
            resume_command=Command(resume=action_value),
            user_id=open_id
        )
    else:
        print(f"无法提取必要参数。action_value: {action_value}")

    return {"toast": {"type": "info", "content": "Agent 已收到反馈，继续执行..."}}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
