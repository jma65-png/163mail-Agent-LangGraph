import smtplib
import os
from email.mime.text import MIMEText
from email.header import Header

from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel

from langchain.tools import tool

load_dotenv()


# @tool
# def write_email(to: str, subject: str, content: str) -> str:
#     """Write and send an email."""
#     # Placeholder response - in real app would send email
#     return f"Email sent to {to} with subject '{subject}' and content: {content}"

@tool
def write_email(to: str, subject: str, content: str) -> str:
    """编写并发送电子邮件。参数 to 是收件人地址，subject 是主题，content 是正文。"""

    # 1. 配置发送方信息
    smtp_server = "smtp.163.com"
    smtp_port = 465
    sender_email = os.getenv("MAIL_USER")
    sender_password = os.getenv("MAIL_PASS")

    # 2. 构建邮件内容

    # my_name = os.getenv("MY_NAME")
    # signature = f"\n\n最诚挚的问候，\n{my_name}"
    # final_content = content + signature
    # message = MIMEText(final_content, 'plain', 'utf-8')
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = sender_email
    message['To'] = to
    message['Subject'] = Header(subject, 'utf-8')


    try:

        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [to], message.as_string())

        return f"✅ 成功：关于「{subject}」的邮件已成功发送给 {to}"

    except Exception as e:
        return f"失败：邮件发送过程中出错，错误信息：{str(e)}"

@tool
def schedule_meeting(
        attendees: list[str], subject: str, duration_minutes: int, preferred_day: datetime, start_time: int
) -> str:
    """预约会议工具。"""

    # 如果想让星期也变中文，可以用索引映射
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_str = weekdays[preferred_day.weekday()]

    date_str = f"{preferred_day.year}年{preferred_day.month:02d}月{preferred_day.day:02d}日 ({weekday_str})"

    # 2. 返回中文结果
    return (
        f"会议「{subject}」已成功预约！\n"
        f"日期：{date_str}\n"
        f"时间：{start_time}点\n"
        f"时长：{duration_minutes}分钟\n"
        f"与会人数：{len(attendees)}人"
    )




# @tool
# def check_calendar_availability(day: str) -> str:
#     """Check calendar availability for a given day."""
#     # Placeholder response - in real app would check actual calendar
#     return f"Available times on {day}: 9:00 AM, 2:00 PM, 4:00 PM"

@tool
def check_calendar_availability(day: str) -> str:
    """查询指定日期的日历空闲时间。"""

    # 占位符响应 - 在实际应用中，这里会对接真实的日历 API（如 Google Calendar）
    # 假设查询结果如下
    available_times = "上午 9:00, 下午 2:00, 下午 4:00"

    return f"{day} 的可用时间段为：{available_times}"

@tool
class Question(BaseModel):
    """当信息不足或需要向用户确认细节时，调用此工具提问。"""
    content: str # 提问的具体内容

@tool
class Done(BaseModel):
    """当所有任务（如发送邮件、预约会议）已全部完成且无需进一步操作时调用。"""
    done: bool = True



