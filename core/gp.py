from typing import Literal

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.types import interrupt, Command

from agents.agent_prompt import (
    triage_system_prompt,
    triage_user_prompt,
    agent_system_prompt,
    default_background,
    default_triage_instructions,
    default_response_preferences,
    default_cal_preferences

)
from agents.tool_prompt import tools_prompt
from agents.tools import write_email, Question, Done
from core.models import get_llm
from core.scheme import StateInput
from core.scheme import RouterScheme, State
from utils.helpers import format_for_display
from utils.helpers import parse_email, format_email_markdown
from core.memory import get_memory, update_memory, load_from_disk

tools = [
    write_email,
    Question,
    Done,
]
tools_by_name = {}
for tool in tools:
    name = tool.name
    tools_by_name[name] = tool

load_dotenv()
llm = get_llm()

llm_router = llm.with_structured_output(RouterScheme)
llm_tools = llm.bind_tools(tools, tool_choice="required")


def triage_router(state: State, store: BaseStore) -> Command[
    Literal["triage_interrupt_handler", "response_agent", "__end__"]]:
    # author, to, subject, email_thread = parse_email(state["email_input"])
    email_input = state.get("email_input")
    if not email_input:
        # 如果状态里没有 email_input，说明可能是从中断直接恢复的，或者流程已经结束
        # 这种情况下，如果分类已经是 ignore/accept，我们直接结束
        if state.get("classification") in ["ignore", "accept"]:
            return Command(goto="__end__", update={})
        # 否则抛出一个更有意义的错误
        raise ValueError("无法从 State 中获取 email_input 数据")

    author, to, subject, email_thread = parse_email(email_input)
    email_markdown = format_email_markdown(subject, author, to, email_thread)
    current_triage_prefs = get_memory(
        store,
        ("email_assistant", "triage_preferences"),
        default_triage_instructions
    )

    user_prompt = triage_user_prompt.format(
        author=author,
        to=to,
        subject=subject,
        email_thread=email_thread
    )
    system_prompt = triage_system_prompt.format(
        background=default_background,
        triage_instructions=current_triage_prefs
    )

    result = llm_router.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )
    classification = result.classification
    if classification == "respond":
        print(f"分类结果：回复 - 这封邮件需要撰写回信")
        goto = "response_agent"
        update = {
            "classification": classification,
            "messages": [{"role": "user",
                          "content": f"请回复下面这封邮件。\n注意：调用写信工具时，'to'(收件人) 参数是原邮件的发件人({author})，绝对不能发给原来的【收件人】！\n\n{email_markdown}"
                          }],
        }

    elif classification == "ignore":
        print(f"分类结果：忽略 - 这是一封无需处理的邮件")
        goto = END
        update = {
            "classification": classification,
        }

    elif classification == "notify":
        print(f"分类结果：通知 - 这封邮件包含重要信息，需告知用户")
        goto = "triage_interrupt_handler"
        update = {
            "classification": classification,
        }
    else:
        raise ValueError(f"无效的分类结果: {classification}")
    return Command(goto=goto, update=update)


def triage_interrupt_handler(state: State, store: BaseStore) -> Command[Literal["response_agent", "__end__"]]:
    email_input = state["email_input"]
    author, to, subject, email_thread = parse_email(email_input)
    email_markdown = format_email_markdown(subject, author, to, email_thread)
    curr_thread_id = email_input.get("thread_id")
    curr_user_id = email_input.get("user_id")

    messages = [{
        "role": "user",
        "content": f"需要提醒用户关注的邮件内容如下：\n{email_markdown}"
    }]

    request = {
        "action_request": {
            "action": f"邮件助手提醒：分类决策为 [{state['classification']}]",
            "args": {"thread_id": curr_thread_id}
        },
        "config": {
            "allow_ignore": True,  # 允许用户点击“忽略”
            "allow_respond": True,  # 允许用户点击“回复”并输入反馈
            "allow_edit": False,  # 不允许直接编辑原文
            "allow_accept": False,  # 不需要直接“接受”
        },

        "description": email_markdown,
        "user_id": curr_user_id
    }

    # response = interrupt([request])[0]
    res = interrupt([request])
    response = res[0] if isinstance(res, list) else res

    if response["type"] == "response":
        user_input = response["args"]

        messages.append({
            "role": "user",
            "content": f"用户希望回复此邮件。请根据以下用户反馈来撰写回信：{user_input}"
        })

        learning_message = [{
            "role": "user",
            "content": f"原邮件主题：{subject}\n系统原分类：{state['classification']}\n用户的纠正或指导意见：{user_input}\n请根据此意见，提取并更新邮件的处理或回复偏好。"
        }]
        update_memory(store, ("email_assistant", "triage_preferences"), learning_message)

        goto = "response_agent"

    elif response["type"] == "ignore":
        learning_message = [{
            "role": "user",
            "content": "用户忽略了这封邮件。请更新分拣偏好，确保以后类似邮件直接被归类为'ignore'，不要再打扰用户。"
        }]
        update_memory(store, ("email_assistant", "triage_preferences"), messages + learning_message)

        # 流程直接结束
        goto = END

    elif response["type"] == "accept":
        print("通知已阅，流程结束。")
        goto = END

    else:
        raise ValueError(f"无法识别的响应类型: {response['type']}")

    update = {
        "messages": messages,
    }

    return Command(goto=goto, update=update)


def response_agent(state: State, store: BaseStore):
    current_response_prefs = get_memory(
        store,
        ("email_assistant", "response_preferences"),
        default_response_preferences
    )
    current_cal_prefs = get_memory(
        store,
        ("email_assistant", "cal_preferences"),
        default_cal_preferences
    )
    prompt_content = agent_system_prompt.format(
        tools_prompt=tools_prompt,
        background=default_background,
        response_preferences=current_response_prefs,  # 注入专属写信偏好
        cal_preferences=current_cal_prefs  # 注入专属日程偏好
    )
    system_message = {"role": "system", "content": prompt_content}
    full_messages = [system_message] + state["messages"]
    ai_message = llm_tools.invoke(full_messages)
    return {"messages": [ai_message]}


def interrupt_handler(state: State, store: BaseStore) -> Command[Literal["response_agent", "__end__"]]:
    result = []
    response = None
    goto = "response_agent"

    for tool_call in state["messages"][-1].tool_calls:
        hitl_tools = ["write_email"]
        if tool_call["name"] not in hitl_tools:
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append({
                "role": "tool",
                "content": observation,
                "tool_call_id": tool_call["id"]
            })
            continue

        email_input = state["email_input"]
        author, to, subject, email_thread = parse_email(email_input)
        original_email_markdown = format_email_markdown(subject, author, to, email_thread)
        curr_thread_id = email_input.get("thread_id")
        curr_user_id = email_input.get("user_id")
        tool_display = format_for_display(tool_call)
        description = original_email_markdown + tool_display

        config = {
            "allow_ignore": True,
            "allow_respond": True,
            "allow_edit": True,
            "allow_accept": True,
        }

        request = {
            "action_request": {
                "action": tool_call["name"],
                "args": tool_call["args"]
            },
            "config": config,
            "description": description,
            "user_id": curr_user_id,  # 新增：收件人
            "thread_id": curr_thread_id  # 新增：thread_id
        }

        res = interrupt([request])
        # 如果恢复时传回的是 dict (飞书)，直接用；如果是 list (本地模拟)，取第一个
        response = res[0] if isinstance(res, list) else res

        if response["type"] == "response":
            user_feedback = response["args"]
            print(f"检测到针对邮件草稿的反馈: {user_feedback}")

            learning_message = [{
                "role": "user",
                "content": f"用户对你生成的邮件草稿提出了修改意见：'{user_feedback}'。请将此偏好加入‘回复偏好’档案，以便下次生成的草稿更符合用户要求。"
            }]

            update_memory(store, ("email_assistant", "response_preferences"), learning_message)

            result.append({
                "role": "user",
                "content": f"这是我对草稿的反馈意见，请参考并重新写一版：{user_feedback}"
            })
            goto = "response_agent"

        elif response["type"] == "edit":
            # 这里的 new_args 现在是用户在飞书输入框里写的纯文本（即用户手动重写的邮件正文）
            user_manual_content = response["args"]
            print("检测到用户手动修改了邮件，正在分析修改习惯...")

            # 提取 AI 原本打算发送的参数
            original_args = tool_call["args"]

            # 组装新的合法参数字典，保留原收件人和主题，替换正文
            new_args = {
                "to": original_args.get("to"),
                "subject": original_args.get("subject"),
                "content": user_manual_content  # 注入用户手动写的正文
            }

            learning_message = [{
                "role": "user",
                "content": f"原始生成的参数：{original_args}\n用户手动修改后的参数：{new_args}\n请分析用户的修改点（如语气、落款、格式），并更新‘回复偏好’档案。"
            }]
            update_memory(store, ("email_assistant", "response_preferences"), learning_message)

            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(new_args)
            result.append({"role": "tool", "content": observation, "tool_call_id": tool_call["id"]})
            goto = "__end__"

        elif response["type"] == "accept":
            print("用户点击确认，直接发送原草稿...")
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append({"role": "tool", "content": observation, "tool_call_id": tool_call["id"]})
            goto = "__end__"

        # 【新增】：用户点击忽略，取消发送
        elif response["type"] == "ignore":
            print("用户忽略了此邮件，已取消发送...")
            # LangGraph 要求必须返回一个 ToolMessage 来闭环，所以我们模拟一个空结果
            result.append({"role": "tool", "content": "用户已取消操作，未发送邮件。", "tool_call_id": tool_call["id"]})
            goto = "__end__"

    update_data = {"messages": result}
    return Command(goto=goto, update=update_data)


def should_continue(state: State) -> Literal["interrupt_handler", "__end__"]:
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return END
    tool_names = [tc["name"] for tc in last_message.tool_calls]
    if "write_email" in tool_names:
        return "interrupt_handler"
    if "Done" in tool_names:
        return END
    return "interrupt_handler"


workflow = StateGraph(State, input_schema=StateInput)
workflow.add_node("triage_router", triage_router)
workflow.add_node("response_agent", response_agent)
workflow.add_node("triage_interrupt_handler", triage_interrupt_handler)
workflow.add_node("interrupt_handler", interrupt_handler)
workflow.add_edge(START, "triage_router")
workflow.add_conditional_edges(
    "response_agent",
    should_continue,
    {
        "interrupt_handler": "interrupt_handler",
        "__end__": END
    }
)

if __name__ == '__main__':
    import uuid
    from langgraph.checkpoint.memory import MemorySaver
    from core.memory import load_from_disk

    mock_store = InMemoryStore()
    memory_saver = MemorySaver()
    load_from_disk(mock_store)

    app = workflow.compile(store=mock_store, checkpointer=memory_saver)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    print(f"当前任务线程 ID: {thread_id}")

    test_email = {
        "email_input": {
            "author": "招聘集团<260@qq.com>",
            "to": "maj04@163.com",
            "subject": "【面试邀约】蚂蚁集团-支付事业部-Python 开发工程师（杭州）",
            "email_thread": """张同学你好：

                    我是蚂蚁集团支付事业部的 HR。很高兴收到你投递的简历，你的 AI Agent 项目经历（163邮件助手）与我们部门目前的业务需求非常契合。

                    我们想邀请你参加下午 14:00 的技术初面，形式为远程面试。

                    请确认该时间是否方便？如果时间冲突，请提供两个你方便的候选时段（建议在工作日 10:00 - 18:00 之间）。

                    收到请回复，祝好！""",
            "thread_id": thread_id,
            "user_id": "ou_6a1177c174880b64fc4044f842edaff2"
        }
    }

    for event in app.stream(test_email, config=config):
        for node_name, state_update in event.items():
            print(f"执行节点: {node_name}")
            print(f"状态更新: {state_update}\n")
            print("-" * 40)

    print("\n" + "=" * 50)
    print("模拟用户在飞书(Accept)")
    print("=" * 50)

    mock_feishu_accept_action = {
        "type": "accept",
        "action": "write_email",
        "thread_id": thread_id,
        "args": {}
    }
    mock_operator_open_id = "ou_6a117f842edaff2"
    from langgraph.types import Command

    for event in app.stream(Command(resume=mock_feishu_accept_action), config=config):
        for node_name, state_update in event.items():
            print(f"执行节点: {node_name}")
            print(f"状态更新: {state_update}\n")
            print("-" * 40)

    print(" Accept 流程测试结束！")
