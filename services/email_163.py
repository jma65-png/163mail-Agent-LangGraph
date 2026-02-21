import os
import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
from typing import Dict, Union
from dotenv import load_dotenv


load_dotenv()

def smart_decode(header_text):
    """助手函数：安全地解码邮件头信息（处理 =?utf-8?B?...= 乱码）"""
    if not header_text:
        return "无"
    try:
        decoded_list = decode_header(header_text)
        result_parts = []
        for content, encoding in decoded_list:
            if isinstance(content, bytes):
                result_parts.append(content.decode(encoding or "utf-8", errors="ignore"))
            else:
                result_parts.append(str(content))
        return "".join(result_parts)
    except Exception:
        return str(header_text)

def fetch_latest_163_email() -> Union[Dict, str]:
    """
    连接到 163 邮箱，抓取并清洗最新的一封邮件。
    返回包含解码后的主题、发件人和纯文本正文的字典。
    """
    imap_server = "imap.163.com"
    email_user = os.getenv("MAIL_USER")
    password = os.getenv("MAIL_PASS")

    try:
        # 1. 连接与登录
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        if 'ID' not in imaplib.Commands:
            imaplib.Commands['ID'] = ('AUTH')
        mail.login(email_user, password)

        # 2. 身份识别 (避开网易安全拦截)
        id_info = '("name" "python-imap" "version" "1.0.0" "vendor" "myclient")'
        mail._simple_command('ID', id_info)
        mail.select("INBOX")

        mail.check()

        # 3. 搜索并获取最新邮件内容
        status, messages = mail.search(None, 'ALL')
        if status != 'OK' or not messages[0]:
            return "收件箱中没有找到任何邮件。"

        latest_email_id = messages[0].split()[-1]
        res, msg_data = mail.fetch(latest_email_id, "(RFC822)")

        if res != 'OK':
            return "邮件抓取失败。"

        # 4. 解析邮件对象
        raw_email_bytes = msg_data[0][1]
        msg = email.message_from_bytes(raw_email_bytes)

        # --- 数据清洗 A: 解码 Header ---
        subject = smart_decode(msg.get("Subject", ""))
        author = smart_decode(msg.get("From", ""))

        # --- 数据清洗 B: 提取并过滤 Body ---
        raw_body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                # 优先寻找纯文本，如果没有则取 HTML
                if content_type in ["text/plain", "text/html"]:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    raw_body += payload.decode(charset, errors="ignore")
        else:
            raw_body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")

        # 使用 BeautifulSoup 剥离 HTML 标签
        soup = BeautifulSoup(raw_body, "html.parser")
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()

        # 压缩多余空白符，保留核心文本
        clean_text = soup.get_text(separator="\n")
        final_body = "\n".join([line.strip() for line in clean_text.splitlines() if line.strip()])

        raw_to = msg.get("To", "")
        to_address = smart_decode(raw_to) if raw_to else "Me"

        mail.logout()

        # 5. 返回字典格式
        return {
            "author": author,  # 发件人
            "to": to_address,  # 收件人
            "subject": subject,  # 主题
            "email_thread": final_body.strip()  # 清洗后的正文
        }

    except Exception as e:
        return f"读取邮件时发生错误: {str(e)}"

if __name__ == "__main__":
    print("开始连接 163 邮箱...")

    # 执行抓取
    result = fetch_latest_163_email()

    # 打印结果
    if isinstance(result, str):
        # 如果返回的是字符串，说明报错了
        print("\n❌ 抓取失败，原因如下：")
        print(result)
    else:
        # 如果返回的是字典，说明抓取并清洗成功！
        print("\n✅ 抓取成功！以下是清洗后准备喂给 AI 的数据：")
        print("-" * 20)
        print(f"👤 发件人: {result.get('author')}")
        print(f"🎯 收件人: {result.get('to')}")
        print(f"📝 主 题: {result.get('subject')}")
        print("-" * 20)
        print("正文预览 (前 200 字):")

        # 截取正文前 200 个字符预览
        body = result.get('email_thread', '')
        print(body[:200] + ("..." if len(body) > 200 else ""))
        print("-" * 50)
