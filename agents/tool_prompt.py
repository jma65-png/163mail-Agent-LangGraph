"""邮件助理的工具提示词模板。"""

# 标准工具描述，用于插入提示词中
STANDARD_TOOLS_PROMPT = """
1. triage_email(ignore, notify, respond) - 将邮件分拣为三类：忽略、通知或回复
2. write_email(to, subject, content) - 向指定的收件人发送邮件
3. schedule_meeting(attendees, subject, duration_minutes, preferred_day, start_time) - 安排日历会议，其中 preferred_day 是一个 datetime 对象
4. check_calendar_availability(day) - 检查指定日期的空闲时段
5. Done - 邮件已发送，任务完成
"""

# 用于人机回环（HITL）工作流的工具描述
HITL_TOOLS_PROMPT = """
你可以使用以下工具来处理任务：

1. write_email(to, subject, content): 向指定收件人发送邮件。
2. schedule_meeting(attendees, subject, duration_minutes, preferred_day, start_time): 
   预约日历会议。注意：preferred_day 必须是一个 datetime 对象。
3. check_calendar_availability(day): 查询指定日期的空闲时间段。
4. Question(content): 如果信息不足或需要确认，向用户询问后续问题。
5. Done: 当邮件已发送或任务彻底完成时调用此工具结束流程。

注意：在执行敏感操作（如发邮件和定会议）前，你的草稿会被送去人工审核。
"""

# 用于带记忆的人机回环（HITL with Memory）工作流的工具描述
# 注意：这里可以根据需要添加额外的记忆相关工具
HITL_MEMORY_TOOLS_PROMPT = """
1. write_email(to, subject, content) - 向指定的收件人发送邮件
2. schedule_meeting(attendees, subject, duration_minutes, preferred_day, start_time) - 安排日历会议，其中 preferred_day 是一个 datetime 对象
3. check_calendar_availability(day) - 检查指定日期的空闲时段
4. Question(content) - 向用户询问任何后续问题或补充信息
5. Done - 邮件已发送，任务完成
"""

# 用于不包含分拣环节的代理工作流工具描述
AGENT_TOOLS_PROMPT = """
1. write_email(to, subject, content) - 向指定的收件人发送邮件
2. schedule_meeting(attendees, subject, duration_minutes, preferred_day, start_time) - 安排日历会议，其中 preferred_day 是一个 datetime 对象
3. check_calendar_availability(day) - 检查指定日期的空闲时段
4. Done - 邮件已发送，任务完成
"""