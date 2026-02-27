import os
import smtplib
from email.header import Header
from email.mime.text import MIMEText

from dotenv import load_dotenv
from langchain.tools import tool
from pydantic import BaseModel

load_dotenv()


@tool
def write_email(to: str, subject: str, content: str) -> str:
    """
    编写并发送电子邮件。

    Args:
        to:收件人地址
        subject:主题
        content:正文

    Returns:

    """
    smtp_server = "smtp.163.com"
    smtp_port = 465
    sender_email = os.getenv("MAIL_USER")
    sender_password = os.getenv("MAIL_PASS")

    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = sender_email
    message['To'] = to
    message['Subject'] = Header(subject, 'utf-8')

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, [to], message.as_string())
            # server.quit()
            return f"发送成功"
    except Exception as e:
        return f"发送失败，错误消息:{str(e)}"


@tool
class Question(BaseModel):
    """
    当信息不足或需要向用户确认细节时，调用此工具提问。
    """
    content: str


@tool
class Done(BaseModel):
    """
    当所有任务（如发送邮件、预约会议）已全部完成且无需进一步操作时调用。
    """
    done: bool = True
