import os
import sys
from pydantic import BaseModel, Field
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.apimodels import get_model_gpt
from services.email_163 import fetch_latest_163_email

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))



class CriteriaGrade(BaseModel):

    justification: str = Field(description="打分的详细理由，必须引用这封测试邮件中的具体句子")
    grade: bool = Field(description="是否满足了所有标准？True为合格，False为不合格")

judge_llm = get_model_gpt().with_structured_output(CriteriaGrade)

RESPONSE_CRITERIA_SYSTEM_PROMPT = """你是一个严苛的邮件质量审查专家。
下面是一封由AI助理自动撰写并发送的真实邮件。
你还将看到一系列必须满足的【成功标准】（以 • 开头）。
你的任务是评估该邮件是否满足了所有的标准。
如果满足所有标准，给出 True；只要有一条没满足，给出 False，并详细说明理由。
"""

def evaluate_real_email(email_data: dict, success_criteria: str):
    """调用裁判大模型对真实的 163 邮件进行打分"""
    print(f"裁判模型正在审阅主题为: 【{email_data.get('subject')}】 的邮件...")
    email_content = f"发件人: {email_data.get('author')}\n收件人: {email_data.get('to')}\n主题: {email_data.get('subject')}\n正文:\n{email_data.get('email_thread')}"

    eval_result = judge_llm.invoke([
        {"role": "system", "content": RESPONSE_CRITERIA_SYSTEM_PROMPT},
        {"role": "user",
         "content": f"【成功标准】:\n{success_criteria}\n\n【被评估的真实邮件】:\n{email_content}\n\n请评估是否达标并给出理由。"}
    ])

    return eval_result

if __name__ == "__main__":
    # 第一步：去 163 邮箱抓取最新的一封邮件
    result = fetch_latest_163_email()

    if isinstance(result, str):
        print(f"邮件抓取失败: {result}")
    else:
        print("✅ 邮件抓取成功！正在转交裁判模型评估...\n")

        criteria = """
        • 必须有礼貌的称呼（如：您好、尊敬的）
        • 必须正面回答或处理了对方的诉求，不能答非所问
        • 必须有专业的落款（例如包含张旭或AI助理字样）
        • 语气必须自然，不能有生硬的机器人味（如“作为AI大模型...”）
        """

        grade_report = evaluate_real_email(result, criteria)

        print("=" * 40)
        print("线上邮件质检报告")
        print("=" * 40)
        print(f"✅ 合格状态: {'【通过】' if grade_report.grade else '【不合格】'}")
        print(f"判决理由:\n{grade_report.justification}")
        print("=" * 40)