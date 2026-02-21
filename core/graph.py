from dotenv import load_dotenv
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

from agents.tools import write_email, schedule_meeting, check_calendar_availability, Question, Done
from core.models import get_model_gpt
from core.state import State, RouterSchema, StateInput
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

def triage_router(state: State) -> Command[Literal["triage_interrupt_handler", "response_agent", "__end__"]]:
    """
    邮件分拣器：分析邮件内容，决定是回复、通知还是忽略。
    """

    # 1. 解析原始邮件输入
    author, to, subject, email_thread = parse_email(state["email_input"])

    # 2. 构建发送给 LLM 的用户提示词
    user_prompt = triage_user_prompt.format(
        author=author, to=to, subject=subject, email_thread=email_thread
    )

    # 3. 创建用于展示的 Markdown 格式邮件内容（用于人工审核环节）
    email_markdown = format_email_markdown(subject, author, to, email_thread)

    # 4. 结合背景信息和分拣指令，构建系统提示词
    system_prompt = triage_system_prompt.format(
        background=default_background,
        triage_instructions=default_triage_instructions
    )

    # 5. 调用分拣 LLM (带有结构化输出)
    result = llm_router.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )

    # 6. 获取分类决策结果
    classification = result.classification


    # 7. 根据分类决策处理后续流程
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
        print(f"🚫 分类结果：忽略 - 这是一封无需处理的邮件")
        # 直接结束流程
        goto = END
        update = {
            "classification_decision": classification,
        }

    elif classification == "notify":
        print(f"🔔 分类结果：通知 - 这封邮件包含重要信息，需告知用户")
        # 下一个节点：跳转到分拣中断处理器（等待人工确认）
        goto = "triage_interrupt_handler"
        update = {
            "classification_decision": classification,
        }

    else:
        # 防错机制：处理意外的分类情况
        raise ValueError(f"无效的分类结果: {classification}")

    # 返回控制指令：决定下一步去向并更新内存状态
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

    # 4. 创建中断请求（这个字典定义了你在 UI 界面上看到的按钮和说明）
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
        user_input = response["args"]  # 这里的 args 包含用户输入的指令

        # 将用户的反馈加入消息序列，以便下一个节点（回复助手）参考
        messages.append({
            "role": "user",
            "content": f"用户希望回复此邮件。请根据以下用户反馈来撰写回信：{user_input}"
        })

        # 跳转到回复助手节点 (response_agent)
        goto = "response_agent"

    # 情况 B：用户选择了“忽略”邮件
    elif response["type"] == "ignore":
        # 流程直接结束
        goto = END

    elif response["type"] == "accept":
        print("📥 通知已阅，流程结束。")
        goto = END

    # 情况 C：未知的响应类型，抛出异常以防逻辑错误
    else:
        raise ValueError(f"无法识别的响应类型: {response['type']}")

    # 7. 更新全局状态（State）并根据 goto 指向进行跳转
    update = {
        "messages": messages,
    }

    return Command(goto=goto, update=update)


def llm_call(state: State):
    # 1. 准备“剧本” (System Message)
    prompt_content = agent_system_prompt_hitl.format(
        tools_prompt=HITL_TOOLS_PROMPT,
        background=default_background,
        response_preferences=default_response_preferences,
        cal_preferences=default_cal_preferences
    )
    system_message = {"role": "system", "content": prompt_content}

    # 2. 准备“对话上下文” (Full Messages)
    # 将系统指令放在最前面，拼接历史消息
    full_messages = [system_message] + state["messages"]

    # 3. 询问 AI 并直接返回结果
    # invoke 的结果直接包进 messages 列表里返回
    ai_message = llm_with_tools.invoke(full_messages)

    return {"messages": [ai_message]}

def interrupt_handler(state: State) -> Command[Literal["llm_call", "__end__"]]:
    """为人工审核 AI 的工具调用创建中断逻辑（安全闸口）"""

    # 存储需要更新的消息结果
    result = []

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

        elif response["type"] == "ignore":
            # 3. 用户点击“忽略”：不执行工具，并强行结束整个工作流
            result.append({
                "role": "tool",
                "content": f"用户忽略了该操作 ({tool_call['name']})。流程结束。",
                "tool_call_id": tool_call["id"]
            })
            goto = END

        elif response["type"] == "response":
            # 4. 用户提供了反馈意见：不执行工具，把意见传回给 AI 重新思考
            user_feedback = response["args"]
            result.append({
                "role": "tool",
                "content": f"用户提供了反馈，请根据此反馈调整操作。反馈内容: {user_feedback}",
                "tool_call_id": tool_call["id"]
            })

        else:
            raise ValueError(f"无效的响应类型: {response['type']}")

    # 更新全局状态并跳转
    return Command(goto=goto, update={"messages": result})


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
# --- 1. 子图优化：回复助理 (Response Agent) ---
# 重点：增加了从 interrupt_handler 回到 llm_call 的“反馈循环”
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
    # 假设你在 interrupt_handler 里把用户的选择存入了 state["human_choice"]
    choice = state.get("human_choice")
    if choice == "revise": # 用户要求修改
        return "llm_call"
    return END # 用户批准发送，退出子图

agent_builder.add_conditional_edges(
    "interrupt_handler",
    after_review_condition
)

response_agent = agent_builder.compile()

# --- 2. 总工作流优化 (Overall Workflow) ---
# 补全了 triage_router 后的分发逻辑
overall_workflow_builder = StateGraph(State, input_schema=StateInput)


overall_workflow_builder.add_node("triage_router", triage_router)
overall_workflow_builder.add_node("triage_interrupt_handler", triage_interrupt_handler)
overall_workflow_builder.add_node("response_agent", response_agent)

overall_workflow_builder.add_edge(START, "triage_router")

# 决策点 C：父图的分流逻辑
def triage_routing(state: State) -> Literal["triage_interrupt_handler", "response_agent", "__end__"]:
    decision = state.get("classification")
    if decision == "notify":
        return "triage_interrupt_handler"
    elif decision == "respond":
        return "response_agent"
    return END

overall_workflow_builder.add_conditional_edges(
    "triage_router",
    triage_routing
)


# overall_workflow_builder.add_edge("triage_interrupt_handler", "response_agent")
# overall_workflow_builder.add_edge("response_agent", END)

overall_workflow = overall_workflow_builder.compile(checkpointer=memory)

if __name__ == "__main__":
    print("正在进行函数测试...")



