from dotenv import load_dotenv
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from langgraph.store.base import BaseStore
from langchain_core.messages import SystemMessage
from langgraph.store.memory import InMemoryStore
from datetime import datetime
from core.memory import get_memory, update_memory
from agents.tools import write_email, schedule_meeting, check_calendar_availability, Question, Done
from core.apimodels import get_model_gpt
from core.state import State, RouterSchema, StateInput,UserPreferences
from agents.tool_prompt import HITL_TOOLS_PROMPT
from utils.helpers import (
    format_email_markdown,
    parse_email,
    format_for_display
)
from agents.prompts import (
    triage_system_prompt,
    triage_user_prompt,
    agent_system_prompt_hitl,
    default_background,
    default_triage_instructions,
    default_response_preferences,
    default_cal_preferences
)
load_dotenv()
llm = get_model_gpt()

tools = [
    write_email,
    schedule_meeting,
    check_calendar_availability,
    Question,
    Done,
]

tools_by_name ={}
for tool in tools:
     name_str =tool.name
     tools_by_name[name_str]=tool

llm_router = llm.with_structured_output(RouterSchema)
llm_with_tools = llm.bind_tools(tools, tool_choice="required")

# def load_memory(state: State,store: BaseStore):
#     """
#     在处理邮件前，从长期记忆库（Store）中读取用户的偏好
#     """
#     print("正在读取用户长期偏好...")
#     namespace=("user_profile","zhangxu")
#
#     memory_item=store.get(namespace,"preferences")
#     if memory_item:
#         prefs=memory_item.value.get("preferences","")
#         print("发现历史偏好已加载")
#     else:
#         prefs="暂无历史偏好"
#         print("无历史偏好")
#
#     return {"user_preferences":prefs}

# def update_memory(state: State,store: BaseStore):
#     """
#     记忆更新结点，从历史对话中提取用户的长期偏好
#     :param state:
#     :param store:
#     :return:{"user_preferences":new_prefs}
#     """
#     print("准备跟新用户长期历史偏好")
#     namespace=("user_profile","zhangxu")
#     memory_item=store.get(namespace,"preferences")
#     if memory_item:
#         current_prefs=memory_item.value.get("preferences","")
#     else:
#         current_prefs=""
#     memory_instructions = f"""你是一个专门负责管理用户偏好的高级档案管理员。
# 以下是用户当前的偏好档案：
# <current_preferences>
# {current_prefs}
# </current_preferences>
#
# 请分析接下来的对话记录（特别是用户对 AI 草稿提出的修改意见和反馈）。
# 如果用户在对话中暗示或明示了新的偏好（例如写作风格、称呼习惯、处理特定邮件的规则等），请更新档案。
#
# 要求：
# 1. 保留原有的有效偏好，将新的偏好补充进去。
# 2. 如果用户的最新反馈与旧偏好冲突，请以最新的反馈为准。
# 3. 尽量用简洁、清晰的规则条目来描述偏好。
# """
#     content=memory_instructions
#     messages=[SystemMessage(content=content)]+state["messages"]
#     structured_llm=llm.with_structured_output(UserPreferences)
#     result=structured_llm.invoke(messages)
#
#     new_prefs=result.user_preferences
#
#     store.put(namespace,
#               "preferences",{"preferences":new_prefs})
#
#     print(f"已经更新AI的思考过程：{result.chain_of_thought}")
#     print(f"更新的内容：{new_prefs}")
#
#     return {"user_preferences":new_prefs}

def triage_router(state: State, store: BaseStore) -> Command[Literal["triage_interrupt_handler", "response_agent", "__end__"]]:
    """邮件分拣器：分析邮件内容，决定是回复、通知还是忽略。"""

    author, to, subject, email_thread = parse_email(state["email_input"])
    user_prompt = triage_user_prompt.format(author=author, to=to, subject=subject, email_thread=email_thread)
    email_markdown = format_email_markdown(subject, author, to, email_thread)

    triage_instructions = get_memory(store, ("email_assistant", "triage_preferences"), default_triage_instructions)

    system_prompt = triage_system_prompt.format(
        background=default_background,
        triage_instructions=triage_instructions
    )

    result = llm_router.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )

    classification = result.classification

    if classification == "respond":
        print(f"📧 分类结果：回复 - 这封邮件需要撰写回信")
        # 下一个节点：跳转到回复助理
        goto = "response_agent"
        # 更新状态：记录决策并初始化对话消息
        update = {
            "classification_decision": classification,
            "messages": [{"role": "user",
                          # bug修改在这里给 AI 明确划重点，告诉它“收件人”应该是原邮件的“发件人”
                          "content": f"请回复下面这封邮件。\n注意：调用写信工具时，'to'(收件人) 参数是原邮件的发件人({author})，绝对不能发给原来的【收件人】！\n\n{email_markdown}"
                          }],
        }

    elif classification == "ignore":
        print(f"分类结果：忽略 - 这是一封无需处理的邮件")
        # 直接结束流程
        goto = END
        update = {
            "classification_decision": classification,
        }

    elif classification == "notify":
        print(f"分类结果：通知 - 这封邮件包含重要信息，需告知用户")
        # 下一个节点：跳转到分拣中断处理器（等待人工确认）
        goto = "triage_interrupt_handler"
        update = {
            "classification_decision": classification,
        }

    else:
        raise ValueError(f"无效的分类结果: {classification}")
    return Command(goto=goto, update=update)


def triage_interrupt_handler(state: State) -> Command[Literal["response_agent", "__end__"]]:
    """
    处理来自分拣节点的“中断”请求。
    当邮件被归类为 'notify'（通知）时，此函数会暂停工作流，等待人工干预。
    """

    # 1. 解析邮件输入
    # 从状态中提取发件人、收件人、主题和正文
    author, to, subject, email_thread = parse_email(state["email_input"])

    # 2. 生成用于“智能收件箱”展示的 Markdown 预览
    email_markdown = format_email_markdown(subject, author, to, email_thread)

    # 3. 构建待处理的消息记录
    messages = [{
        "role": "user",
        "content": f"需要提醒用户关注的邮件内容如下：\n{email_markdown}"
    }]

    # 4. 创建中断请求
    request = {
        "action_request": {
            "action": f"邮件助手提醒：分类决策为 [{state['classification_decision']}]",
            "args": {}
        },
        "config": {
            "allow_ignore": True,  # 允许用户点击“忽略”
            "allow_respond": True,  # 允许用户点击“回复”并输入反馈
            "allow_edit": False,  # 不允许直接编辑原文
            "allow_accept": False,  # 不需要直接“接受”
        },
        # 在 Agent Inbox 中显示的邮件正文预览
        "description": email_markdown,
    }

    # 5. 【核心步骤】触发中断
    # 程序运行到这里会物理暂停，直到用户在界面上做出操作。
    # interrupt 函数会返回用户的输入数据。
    response = interrupt([request])[0]

    # 6. 根据用户的反馈决定下一步去向



    # 情况 A：用户选择了“回复”并提供了反馈建议
    if response["type"] == "response":
        user_input = response["args"]

        messages.append({
            "role": "user",
            "content": f"用户希望回复此邮件。请根据以下用户反馈来撰写回信：{user_input}"
        })
        update_memory(store, ("email_assistant", "triage_preferences"), messages + [{
            "role": "user",
            "content": "用户决定回复这封被标记为通知的邮件。请更新分拣偏好，确保以后这类邮件直接被归类为'respond'。"
        }])

        # 跳转到回复助手节点 (response_agent)
        goto = "response_agent"

    # 情况 B：用户选择了“忽略”邮件
    elif response["type"] == "ignore":
        update_memory(store, ("email_assistant", "triage_preferences"), messages + [{
            "role": "user",
            "content": "用户忽略了这封邮件。请更新分拣偏好，确保以后类似邮件直接被归类为'ignore'，不要再打扰用户。"
        }])
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

def llm_call(state: State, store: BaseStore):
    cal_prefs = get_memory(store, ("email_assistant", "cal_preferences"), default_cal_preferences)
    response_prefs = get_memory(store, ("email_assistant", "response_preferences"), default_response_preferences)
    today_date = datetime.now().strftime("%Y-%m-%d, %A")
    dynamic_background = default_background + f"\n[重要时间提示：今天是 {today_date}，请以此为基准。]"
    prompt_content = agent_system_prompt_hitl.format(
        tools_prompt=HITL_TOOLS_PROMPT,
        background=dynamic_background,
        response_preferences=response_prefs, # 注入专属写信偏好
        cal_preferences=cal_prefs            # 注入专属日程偏好
    )
    system_message = {"role": "system", "content": prompt_content}

    full_messages = [system_message] + state["messages"]

    ai_message = llm_with_tools.invoke(full_messages)
    return {"messages": [ai_message]}

def interrupt_handler(state: State) -> Command[Literal["llm_call", "__end__"]]:
    """为人工审核 AI 的工具调用创建中断逻辑（安全闸口）"""

    # 存储需要更新的消息结果
    result = []
    response = None

    # 默认下一步跳转到 AI 思考节点 (llm_call)
    goto = "llm_call"

    # 遍历 AI 在上一条消息中提出的所有“工具调用”请求
    for tool_call in state["messages"][-1].tool_calls:

        # 定义需要人工安检的敏感工具名单
        hitl_tools = ["write_email", "schedule_meeting", "Question"]

        # 如果调用的工具不在敏感名单中（例如“查询日历”），则直接执行，无需打断用户
        if tool_call["name"] not in hitl_tools:
            # 意思是“直接运行这个 Python 功能”
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            # 将执行结果存入结果列表
            result.append({
                "role": "tool",
                "content": observation,
                "tool_call_id": tool_call["id"]
            })
            continue

        # --- 如果是敏感工具，开始准备人工审核界面 ---

        # 从状态中获取原始邮件信息并格式化
        email_input = state["email_input"]
        author, to, subject, email_thread = parse_email(email_input)
        original_email_markdown = format_email_markdown(subject, author, to, email_thread)

        # 格式化 AI 建议的操作预览，并拼接到原始邮件下方
        tool_display = format_for_display(tool_call)
        description = original_email_markdown + tool_display

        # 根据不同的工具类型，配置“智能收件箱”中允许的操作按钮
        if tool_call["name"] == "write_email":
            config = {
                "allow_ignore": True,  # 允许忽略
                "allow_respond": True,  # 允许提供反馈意见
                "allow_edit": True,  # 允许直接修改邮件内容
                "allow_accept": True,  # 允许直接发送
            }
        elif tool_call["name"] == "schedule_meeting":
            config = {
                "allow_ignore": True,
                "allow_respond": True,
                "allow_edit": True,
                "allow_accept": True,
            }
        elif tool_call["name"] == "Question":
            config = {
                "allow_ignore": True,
                "allow_respond": True,
                "allow_edit": False,  # 提问工具通常只需回答，无需修改参数
                "allow_accept": False,
            }
        else:
            raise ValueError(f"无效的工具调用: {tool_call['name']}")

        # 创建中断请求对象
        request = {
            "action_request": {
                "action": tool_call["name"],
                "args": tool_call["args"]
            },
            "config": config,
            "description": description,
        }

        # 【核心点】程序在此暂停，发送请求到收件箱并等待用户操作
        # response 字典里存的就是你在界面上到底点了哪个按钮，以及你改了什么东西。
        response = interrupt([request])[0]

        # --- 根据用户的点击结果处理响应 ---

        if response["type"] == "accept":
            # 1. 用户点击“接受”：按 AI 原计划执行工具
            tool = tools_by_name[tool_call["name"]]
            observation = tool.invoke(tool_call["args"])
            result.append({"role": "tool", "content": observation, "tool_call_id": tool_call["id"]})

        elif response["type"] == "edit":
            # 2. 用户点击“编辑”：使用用户修改后的参数 (edited_args)
            tool = tools_by_name[tool_call["name"]]
            edited_args = response["args"]["args"]  # 从界面获取修改后的数据

            # 为了保持逻辑一致性，我们需要制造一个“平行时空”
            # 把 AI 原始的消息复制一份，但把里面的工具参数替换成用户修改后的
            ai_message = state["messages"][-1]
            current_id = tool_call["id"]

            updated_tool_calls = [tc for tc in ai_message.tool_calls if tc["id"] != current_id] + [
                {"type": "tool_call", "name": tool_call["name"], "args": edited_args, "id": current_id}
            ]

            # 替换掉那条 AI 消息，让它看起来好像原本就想写成用户修改后的样子
            result.append(ai_message.model_copy(update={"tool_calls": updated_tool_calls}))

            # 执行修改后的工具逻辑
            observation = tool.invoke(edited_args)
            result.append({"role": "tool", "content": observation, "tool_call_id": current_id})
            initial_tool_call = tool_call["args"]
            if tool_call["name"] == "write_email":

                update_memory(store, ("email_assistant", "response_preferences"), state["messages"][:-1] + result + [{
                    "role": "user",
                    "content": f"用户修改了邮件草稿。AI 原稿：{initial_tool_call}。用户修改后：{edited_args}。请总结用户的写作习惯并更新偏好档案。"
                }])
            elif tool_call["name"] == "schedule_meeting":

                update_memory(store, ("email_assistant", "cal_preferences"), state["messages"][:-1] + result + [{
                    "role": "user",
                    "content": f"用户修改了会议邀请。AI 原稿：{initial_tool_call}。用户修改后：{edited_args}。请总结用户对会议时长、时间的偏好并更新档案。"
                }])
        elif response["type"] == "ignore":
            # 3. 用户点击“忽略”：不执行工具，并强行结束整个工作流
            result.append({
                "role": "tool",
                "content": f"用户忽略了该操作 ({tool_call['name']})。流程结束。",
                "tool_call_id": tool_call["id"]
            })
            update_memory(store, ("email_assistant", "triage_preferences"), state["messages"] + result + [{
                "role": "user",
                "content": f"用户在看到 AI 准备执行 {tool_call['name']} 时，直接选择了忽略草稿并终止流程。这意味着用户根本不想处理这封邮件。请更新分拣偏好，确保以后此类邮件在第一关直接被归类为 'ignore'。"
            }])
            goto = END

        elif response["type"] == "response":
            # 4. 用户提供了反馈意见：不执行工具，把意见传回给 AI 重新思考
            user_feedback = response["args"]
            result.append({
                "role": "tool",
                "content": f"用户提供了反馈，请根据此反馈调整操作。反馈内容: {user_feedback}",
                "tool_call_id": tool_call["id"]
            })
            if tool_call["name"] in ["write_email", "Question"]:

                update_memory(store, ("email_assistant", "response_preferences"), state["messages"] + result + [{
                    "role": "user",
                    "content": f"关于这封邮件，用户给出了反馈：{user_feedback}。请据此更新写信偏好档案。"
                }])

            elif tool_call["name"] == "schedule_meeting":

                update_memory(store, ("email_assistant", "cal_preferences"), state["messages"] + result + [{
                    "role": "user",
                    "content": f"关于这个会议，用户给出了反馈：{user_feedback}。请据此更新日程偏好档案。"
                }])

        else:
            raise ValueError(f"无效的响应类型: {response['type']}")
    update_data = {"messages": result}

    if response is None or response["type"] in ["response", "edit"]:
        update_data["human_choice"] = "revise"  # 告诉路由：需要重写
    else:
        update_data["human_choice"] = "accept"  # 告诉路由：可以结束了

    return Command(goto=goto, update=update_data)


# --- 1. 条件判断：决定是继续执行还是收工 ---
def should_continue(state: State) -> Literal["interrupt_handler", "__end__"]:
    """
    判断逻辑：如果 AI 调用了 'Done' 工具，则结束流程；
    否则，将工具调用交给人工审核处理器。
    """
    messages = state["messages"]
    last_message = messages[-1]

    # 检查是否有工具调用请求
    if last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            # 如果 AI 说“搞定了”，就收工
            if tool_call["name"] == "Done":
                return END
            # 否则，去人工审核环节排队
            else:
                return "interrupt_handler"

    # 如果没调工具，默认也结束（防止死循环）
    return END

# 1. 初始化内存存储
memory = MemorySaver()
agent_builder = StateGraph(State)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("interrupt_handler", interrupt_handler)
agent_builder.add_edge(START, "llm_call")

# 决策点 A：AI 生成草稿后，决定是去人工审核还是直接结束
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue # 这个函数判断是否有 tool_calls
)

# 决策点 B：人工审核后的去向
def after_review_condition(state: State) -> Literal["llm_call", "__end__"]:

    choice = state.get("human_choice")
    if choice == "revise": # 用户要求修改
        return "llm_call"
    return END # 用户批准发送，退出子图

agent_builder.add_conditional_edges(
    "interrupt_handler",
    after_review_condition
)

response_agent = agent_builder.compile()

overall_workflow_builder = StateGraph(State, input_schema=StateInput)

overall_workflow_builder.add_node("triage_router", triage_router)
overall_workflow_builder.add_node("triage_interrupt_handler", triage_interrupt_handler)
overall_workflow_builder.add_node("response_agent", response_agent)

overall_workflow_builder.add_edge(START, "triage_router")
overall_workflow_builder.add_edge("triage_interrupt_handler", "response_agent")
overall_workflow_builder.add_edge("response_agent", END)

#必须把 store 传给子图和父图
store = InMemoryStore()
from core.memory import load_from_disk
load_from_disk(store)
overall_workflow = overall_workflow_builder.compile(
    checkpointer=memory,
    store=store
)

if __name__ == "__main__":
    import uuid

    print("正在启动测试...")

    # 模拟一封新邮件
    test_email = {
        "email_input": {
            "author": "财务部-王经理 <finance-admin@scam-mail.com>",
            "to": "zhangxu@163.com",
            "subject": "【紧急通知】2026年第一季度报销款项核对清单",
            "email_thread": "张旭您好，附件是您第一季度的报销清单。请您务必在今天下午5点前回复本邮件确认金额，否则本月报销将延期打款。收到请回复“确认收到”。"
        }
    }

    # 创建一个线程 ID（代表一次对话）
    thread_config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    for event in overall_workflow.stream(test_email, config=thread_config):
        if "__interrupt__" in event:
            print("\n[系统暂停] 等待人工审核...")
            interrupt_data = event["__interrupt__"][0]
            print(f"AI 提议的操作: {interrupt_data.value[0]['action_request']['action']}")
            print("模拟反馈：'委婉拒绝，说自己不喜欢吃鱼'")
            resume_command = Command(resume=[{
                "type": "response",
                "args": "委婉拒绝，说自己不喜欢吃鱼"
            }])

            for resume_event in overall_workflow.stream(resume_command, config=thread_config):
                pass

    print("\n测试流程结束！")



