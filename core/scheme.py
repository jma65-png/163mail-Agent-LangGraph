from typing import TypedDict, Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import NotRequired


class RouterScheme(BaseModel):
    """
    析未读邮件并根据内容进行分拣。
    """
    reasoning: str = Field(description="分类背后的思考逻辑")
    classification: Literal["respond", "notify", "ignore"] = Field(
        description="""邮件的分类结果：
                - respond: 需要人工或 AI 撰写回复的邮件。
                - notify: 包含重要信息但无需回复，仅需通知用户的邮件。
                - ignore: 垃圾邮件、广告或无需任何处理的邮件。"""
    )


class Userpreference(BaseModel):
    """
    基于用户的反馈更新用户偏好设置
    """
    reasoning: str = Field(description="关于是否需要添加或更新用户偏好的推理逻辑")
    preferences: str = Field(description="更新后的用户偏好描述文字")


class EmailDetail(TypedDict):
    """
    邮件格式定义
    """
    author: str
    to: str
    subject: NotRequired[str]
    email_thread: str
    thread_id: str  # 邮件的专属 UUID
    user_id: str  # 飞书 Open ID (收件人)


class State(MessagesState):
    """
    在整个工作流节点之间传递的‘共享内存’,现在已经引入长期内存。
    """
    email_input: EmailDetail
    classification: Literal["respond", "notify", "ignore"]
    preferences: str


class StateInput(TypedDict):
    """
    初始输入状态：启动程序时传入的内容
    """
    email_input: EmailDetail
