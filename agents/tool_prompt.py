tools_prompt = """
你可以使用以下工具来处理任务：
1. write_email(to, subject, content): 向指定收件人发送邮件。
2. schedule_meeting(attendees, subject, duration_minutes, preferred_day, start_time): 
   预约日历会议。注意：preferred_day 必须是一个 datetime 对象。
3. check_calendar_availability(day): 查询指定日期的空闲时间段。
4. Question(content): 如果信息不足或需要确认，向用户询问后续问题。
5. Done: 当邮件已发送或任务彻底完成时调用此工具结束流程。

注意：在执行敏感操作（如发邮件和定会议）前，你的草稿会被送去人工审核。
"""
