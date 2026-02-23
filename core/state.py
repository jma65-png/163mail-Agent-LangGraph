from pydantic import BaseModel, Field
from typing_extensions import TypedDict, Literal
from langgraph.graph import MessagesState


# --- 第一部分：给 AI 定的“输出格式” (BaseModel) ---

class RouterSchema(BaseModel):
    """
    分析未读邮件并根据内容进行分拣。
    这个类就是给 LLM 定的‘回话格式。
    继承了 BaseModel 之后，LLM 才知道要按这个结构填空。
    """

    reasoning: str = Field(
        description="分类背后的详细逻辑和思考过程。"
    )
    classification: Literal["respond", "notify", "ignore"] = Field(
        description="""邮件的分类结果：
            - respond: 需要人工或 AI 撰写回复的邮件。
            - notify: 包含重要信息但无需回复，仅需通知用户的邮件。
            - ignore: 垃圾邮件、广告或无需任何处理的邮件。"""
    )

class UserPreferences(BaseModel):
    """基于用户反馈更新的用户偏好设置。"""

    chain_of_thought: str = Field(
        description="关于是否需要添加或更新用户偏好的推理逻辑。"
    )
    user_preferences: str = Field(
        description="更新后的用户偏好描述文字。"
    )


# --- 第二部分：程序的“内存结构” (State) ---

class StateInput(TypedDict):
    """初始输入状态：启动程序时传入的内容。"""
    # 存储邮件原始内容
    email_input: dict


class State(MessagesState):
    """全局状态：在整个工作流节点之间传递的‘共享内存’,现在已经引入长期内存。"""
    # MessagesState 已经内置了 messages 列表，用于记录对话历史

    # 存储邮件内容
    email_input: dict

    # 存储路由器的分类决策结果
    classification_decision: Literal["ignore", "respond", "notify"]
    #用来装载从store里读出来的长期偏好
    user_preferences: str

# --- 第三部分：基础数据结构 ---

class EmailData(TypedDict):
    """单封邮件的详细数据结构。"""
    id: str  # 邮件 ID
    thread_id: str  # 会话线程 ID
    from_email: str  # 发件人
    subject: str  # 主题
    page_content: str  # 邮件正文
    send_time: str  # 发送时间
    to_email: str  # 收件人