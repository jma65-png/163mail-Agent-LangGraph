from typing import List, Any
import json
import html2text


def format_email_markdown(subject, author, to, email_thread, email_id=None):
    """将邮件详情格式化为漂亮的 Markdown 字符串以便显示。

    参数:
        subject: 邮件主题
        author: 发件人
        to: 收件人
        email_thread: 邮件内容
        email_id: 可选的邮件 ID（用于 Gmail API）
    """
    id_section = f"\n**ID**: {email_id}" if email_id else ""

    return f"""
**主题**: {subject}
**发件人**: {author}
**收件人**: {to}{id_section}

{email_thread}

---
"""


def format_gmail_markdown(subject, author, to, email_thread, email_id=None):
    """将 Gmail 邮件详情格式化为 Markdown，并处理 HTML 转换。

    参数:
        subject: 邮件主题
        author: 发件人
        to: 收件人
        email_thread: 邮件内容（可能是 HTML 格式）
        email_id: 可选的邮件 ID
    """
    id_section = f"\n**ID**: {email_id}" if email_id else ""

    # 检查内容是否为 HTML 并转换为纯文本 Markdown
    if email_thread and (email_thread.strip().startswith("<!DOCTYPE") or
                         email_thread.strip().startswith("<html") or
                         "<body" in email_thread):
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # 不换行
        email_thread = h.handle(email_thread)

    return f"""
**主题**: {subject}
**发件人**: {author}
**收件人**: {to}{id_section}

{email_thread}

---
"""


def format_for_display(tool_call):
    """为 Agent 收件箱格式化展示内容。

    参数:
        tool_call: 需要格式化的工具调用信息
    """
    display = ""

    # 根据不同的工具名称添加不同的标题和格式
    if tool_call["name"] == "write_email":
        display += f"""# 邮件草稿

**收件人**: {tool_call["args"].get("to")}
**主题**: {tool_call["args"].get("subject")}

{tool_call["args"].get("content")}
"""
    elif tool_call["name"] == "schedule_meeting":
        display += f"""# 会议邀请预览

**会议主题**: {tool_call["args"].get("subject")}
**参会者**: {', '.join(tool_call["args"].get("attendees"))}
**时长**: {tool_call["args"].get("duration_minutes")} 分钟
**日期**: {tool_call["args"].get("preferred_day")}
"""
    elif tool_call["name"] == "Question":
        display += f"""# 待办：向用户提问

{tool_call["args"].get("content")}
"""
    else:
        display += f"""# 工具调用: {tool_call["name"]}

参数:"""
        if isinstance(tool_call["args"], dict):
            display += f"\n{json.dumps(tool_call['args'], indent=2, ensure_ascii=False)}\n"
        else:
            display += f"\n{tool_call['args']}\n"
    return display


def parse_email(email_input: dict) -> tuple:
    """解析标准邮件输入字典。
    将字典拆分成为元组tuple
    """
    return (
        email_input["author"],
        email_input["to"],
        email_input["subject"],
        email_input["email_thread"],
    )


def parse_gmail(email_input: dict) -> tuple:
    """解析来自 Gmail 的邮件输入，包含 ID。"""
    print("!收到 Gmail 原始输入!")
    return (
        email_input["from"],
        email_input["to"],
        email_input["subject"],
        email_input["body"],
        email_input.get("id"),
    )


def extract_message_content(message) -> str:
    """从不同类型的消息对象中提取纯文本内容。"""
    content = message.content

    # 防止无限递归导致的死循环
    if isinstance(content, str) and '<Recursion on AIMessage' in content:
        return "[递归内容，已忽略]"

    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and 'text' in item:
                text_parts.append(item['text'])
        return "\n".join(text_parts)

    return str(content)


def format_few_shot_examples(examples):
    """将向量数据库中的历史案例格式化为可读字符串。"""
    formatted = []
    for example in examples:
        # 拆分并提取历史分类案例
        email_part = example.value.split('Original routing:')[0].strip()
        original_routing = example.value.split('Original routing:')[1].split('Correct routing:')[0].strip()
        correct_routing = example.value.split('Correct routing:')[1].strip()

        formatted_example = f"""案例:
邮件内容: {email_part}
原始分类: {original_routing}
修正后分类: {correct_routing}
---"""
        formatted.append(formatted_example)

    return "\n".join(formatted)


def extract_tool_calls(messages: List[Any]) -> List[str]:
    """安全地从消息记录中提取被调用的工具名称。"""
    tool_call_names = []
    for message in messages:
        if isinstance(message, dict) and message.get("tool_calls"):
            tool_call_names.extend([call["name"].lower() for call in message["tool_calls"]])
        elif hasattr(message, "tool_calls") and message.tool_calls:
            tool_call_names.extend([call["name"].lower() for call in message.tool_calls])
    return tool_call_names


def show_graph(graph, xray=False):
    """显示 LangGraph 的架构流程图（支持多种渲染方式）。"""
    from IPython.display import Image
    try:
        return Image(graph.get_graph(xray=xray).draw_mermaid_png())
    except Exception as e:
        import nest_asyncio
        nest_asyncio.apply()
        from langchain_core.runnables.graph import MermaidDrawMethod
        return Image(graph.get_graph().draw_mermaid_png(draw_method=MermaidDrawMethod.PYPPETEER))