from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage
from core.apimodels import get_model_gpt
from dotenv import load_dotenv
load_dotenv()
class CriteriaGrade(BaseModel):
    """根据特定标准对回复进行打分"""
    justification: str = Field(description="打分的理由，必须引用被测试邮件中的具体句子")
    grade: bool = Field(description="是否满足了所有标准？True为及格，False为不及格")
judge_llm = get_model_gpt().with_structured_output(CriteriaGrade)

RESPONSE_CRITERIA_SYSTEM_PROMPT = """你是一个严苛的邮件质量审查员。
你将看到AI助理代表用户写的一封邮件草稿。
你还将看到一系列必须满足的【成功标准】（以 • 开头）。
你的任务是评估该邮件草稿是否满足了所有的标准。
如果满足所有标准，给出 True；只要有一条没满足，给出 False，并详细说明理由。
"""


def evaluate_response_quality(ai_generated_email: str, success_criteria: str):
    """调用裁判大模型进行打分"""
    print("裁判模型正在审阅草稿...")
    eval_result = judge_llm.invoke([
        {"role": "system", "content": RESPONSE_CRITERIA_SYSTEM_PROMPT},
        {"role": "user",
         "content": f"【成功标准】:\n{success_criteria}\n\n【AI生成的草稿】:\n{ai_generated_email}\n\n请评估是否达标并给出理由。"}
    ])

    print("\n裁判打分结果:")
    print(f"及格状态 (Grade): {'✅ 及格 (True)' if eval_result.grade else '不及格 (False)'}")
    print(f"判决理由 (Justification):\n{eval_result.justification}")
    return eval_result

if __name__ == "__main__":
    mock_ai_email = "王总您好，收到您的报价请求。附件是我们最新的产品手册，请查阅。祝好，张煦"
    criteria = "• 必须礼貌称呼对方\n• 必须提及附件\n• 必须包含发件人签名'张煦'"
    evaluate_response_quality(mock_ai_email, criteria)