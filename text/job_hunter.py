from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field
from core.apimodels import get_model_gpt
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
import os
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from agents.prompts import JD_ANALYZER_PROMPT,COVER_LETTER_PROMPT
load_dotenv()
llm = get_model_gpt()

current_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(current_dir, "..", "Ingestion", "chroma_db")
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(
    persist_directory=db_path,
    embedding_function=embeddings,
    collection_name="resume_info"
)


class JobHunterState(TypedDict):
    raw_jd_input: str       # 你粘贴进来的原始 JD（
    analyzed_jd: str        # 节点 1 提取出的【核心岗位要求】
    resume_context: str     # 节点 2 从数据库里捞出来的【匹配经历】
    cover_letter: str       # 最终生成的【自我介绍/求职信】

class jobread(BaseModel):
    """
    分析岗位需求并给出岗位画像
    """
    reasoning: str = Field(description="提取画像背后的详细逻辑和思考过程。")
    jobneed: str = Field(description="总结岗位的核心画像（职责、硬技能、软技能、潜台词）。")

llm_with_structure = llm.with_structured_output(jobread)

# --- 节点 1：解析工作要求 ---
def extract_requirements_node(state: JobHunterState):
    print("正在拆解 JD，提取核心考察点...")

    result = llm_with_structure.invoke(
        [
            {"role": "system", "content": JD_ANALYZER_PROMPT},
            {"role": "user", "content": state["raw_jd_input"]},
        ]
    )
    response = result.jobneed

    print(f"✅提取完毕！岗位画像：\n{response}\n")
    return {"analyzed_jd": response}


# --- 节点 2：检索简历并生成自我介绍 ---
def generate_intro_node(state: JobHunterState):
    print("正在根据岗位画像，定向抓取你的简历经历...")
    #天才
    docs = vectorstore.similarity_search(state["analyzed_jd"], k=4)
    resume_context = "\n\n".join([doc.page_content for doc in docs]) if docs else "未找到直接相关的项目经历。"
    print("✅简历素材准备完毕。")
    print("正在融合信息，撰写高转化率自我介绍...")
    final_prompt = COVER_LETTER_PROMPT.format(
        analyzed_jd=state["analyzed_jd"],
        resume_context=resume_context
    )
    response = llm.invoke([SystemMessage(content=final_prompt)])
    return {"resume_context": resume_context, "cover_letter": response.content}

builder = StateGraph(JobHunterState)
builder.add_node("analyze_jd", extract_requirements_node)
builder.add_node("generate_intro", generate_intro_node)

builder.add_edge(START, "analyze_jd")
builder.add_edge("analyze_jd", "generate_intro")
builder.add_edge("generate_intro", END)

job_assistant = builder.compile()

if __name__ == "__main__":
    # 网页复制的一段 JD
    test_jd_text = """ 1、设计和开发复杂的多智能体(Multi-Agent)boss系统架构 2、深入研究和实现Agent交boss互、协作和通信机制 3、构建高效的Agent编排和协调策略 4、使用Python开发Agent原型和生产系统 5、优化Agent之间的信息交换和决策流程 6、设计创新的提⽰⼯程(PromptEngineering)策略持续优化Agent系统的性能和可扩展性 岗位要求 1、强⼤的Python编程能力 2、对Agent交互和协作机制有深入理解 3、能独⽴设计和实现复杂Agent系统 4、有AI视频生成经验者优先 技术要求 精通Python，熟悉MCP、openApi等模型通信协议优先了解LangChain、CrewAl、metaGPT等Agent开发框架熟悉GPT、Claude等大语言模型"""
    final_state = job_assistant.invoke({"raw_jd_input": test_jd_text})
    print("最终生成的求职信草稿：")
    print(final_state["cover_letter"])