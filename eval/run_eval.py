import os
from dotenv import load_dotenv
from langsmith import Client
from langgraph.store.memory import InMemoryStore
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.graph import triage_router
from core.apimodels import get_model_gpt

load_dotenv()
client = Client()

examples_triage = [

    {"inputs": {"email_input": {"author": "boss@company.com", "to": "zhangxu@163.com", "subject": "产品报价单", "email_thread": "您好，关注贵司很久了，请发一份 Agent 开发服务的报价单。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "aliyun-hr@alibaba-inc.com", "to": "zhangxu@163.com", "subject": "面试邀请", "email_thread": "张旭您好，我是阿里云 HR，想约您下周二聊聊简历。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "partner@test.com", "to": "zhangxu@163.com", "subject": "合同流程", "email_thread": "小张，上次发的合同还没盖章回传，请确认。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "dev-support@cloud.com", "to": "zhangxu@163.com", "subject": "API 报错", "email_thread": "调用你们的接口一直返回 500 错误，急需解决。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "biz@startup.com", "to": "zhangxu@163.com", "subject": "资源交换", "email_thread": "我有 10 万活跃用户，希望能和你们的邮件助手做联运。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "manager@dept.com", "to": "zhangxu@163.com", "subject": "改期", "email_thread": "不好意思，明天下午的同步会我有事，能改到后天吗？"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "user123@gmail.com", "to": "zhangxu@163.com", "subject": "用户反馈", "email_thread": "你们的产品很好用，但我希望增加一个导出功能。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "finance@client.com", "to": "zhangxu@163.com", "subject": "打款凭证", "email_thread": "财务已汇款，请查收附件中的水单并安排开票。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "ex-colleague@oldfirm.com", "to": "zhangxu@163.com", "subject": "离职证明", "email_thread": "张旭，我需要你协助提供一下去年的工作证明。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "tech-lead@team.com", "to": "zhangxu@163.com", "subject": "交付物确认", "email_thread": "代码已经推送到仓库，请检查是否符合部署要求。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "admin@company.com", "to": "all@company.com", "subject": "国庆安排", "email_thread": "全公司国庆放假 7 天，10 月 8 日正常上班。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "office@company.com", "to": "dev-team@company.com", "subject": "座位搬迁", "email_thread": "本周五晚上，研发部全体搬迁到 5 楼 A 区。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "finance@company.com", "to": "all@company.com", "subject": "报销截止日期", "email_thread": "本月报销将于 25 号关闭，请各位尽快提交。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "it-support@company.com", "to": "all@company.com", "subject": "停机维护", "email_thread": "内网服务器将在今晚 2 点进行升级，期间无法访问。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "hr@company.com", "to": "all@company.com", "subject": "社保基数更新", "email_thread": "本月起，各位的社保缴纳基数将根据去年工资调整。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "hr@company.com", "to": "all@company.com", "subject": "新员工入职", "email_thread": "欢迎王大锤加入我们，担任后端工程师。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "payroll@company.com", "to": "zhangxu@163.com", "subject": "10月工资条", "email_thread": "本月实发工资已入账，点击附件查看明细。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "event@company.com", "to": "all@company.com", "subject": "年会地点", "email_thread": "今年年会在丽思卡尔顿举办，请记得携带工牌。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "general-affairs@company.com", "to": "all@company.com", "subject": "食堂满意度", "email_thread": "行政部发起的食堂调研，请在下班前填写。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "health@company.com", "to": "all@company.com", "subject": "防疫提醒", "email_thread": "最近流感频发，请大家在工位也要注意通风。"}}, "outputs": {"classification": "notify"}},

    # --- 3. 低价值/垃圾邮件类 (Ignore) ---
    {"inputs": {"email_input": {"author": "ads@marketing.com", "to": "zhangxu@163.com", "subject": "副业培训", "email_thread": "每天半小时，教你用 AI 赚钱，年入百万。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "loan@bank-service.com", "to": "zhangxu@163.com", "subject": "贷款利息优惠", "email_thread": "您有一笔 30 万额度待领取，低至 3.2%。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "gym@fitness.com", "to": "zhangxu@163.com", "subject": "游泳健身", "email_thread": "楼下健身房开业，办卡买一送一。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "noreply@job-site.com", "to": "zhangxu@163.com", "subject": "本周职位推荐", "email_thread": "智联招聘为您推荐了 20 个相关职位。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "newsletter@daily.com", "to": "zhangxu@163.com", "subject": "已成功退订", "email_thread": "您已成功退订我们的每日新闻简报。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "prize@scam.com", "to": "zhangxu@163.com", "subject": "中奖通知", "email_thread": "恭喜您获得 iPhone 15 一部，请点击链接领奖。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "system@auth.com", "to": "zhangxu@163.com", "subject": "验证码", "email_thread": "您的注册验证码是 123456，请勿告诉他人。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "test@test.com", "to": "zhangxu@163.com", "subject": "测试邮件", "email_thread": "123 456 test test test"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "bot@greet.com", "to": "zhangxu@163.com", "subject": "早安", "email_thread": "祝大家今天有个好心情。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "unknown@unknown.com", "to": "zhangxu@163.com", "subject": "无主题", "email_thread": "..."}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "sales@old-promo.com", "to": "zhangxu@163.com", "subject": "618大促", "email_thread": "快来抢购，活动仅剩最后 1 小时（已过期）。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "insure@protection.com", "to": "zhangxu@163.com", "subject": "意外险领取", "email_thread": "免费送您一份 100 万保额的交通意外险。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "hacker@phishing.com", "to": "zhangxu@163.com", "subject": "紧急更新", "email_thread": "您的账号异常，请点击 http://fake-link.com 修改密码。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "growth@blog.com", "to": "zhangxu@163.com", "subject": "行业干货", "email_thread": "深度解析：为什么你还在加班？文末有惊喜礼包。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "auto-reply@client.com", "to": "zhangxu@163.com", "subject": "Out of office", "email_thread": "我正在休假，无法及时回复您的邮件。"}}, "outputs": {"classification": "ignore"}},

    # --- 4. 边界/混合情况类 (Hard) ---
    {"inputs": {"email_input": {"author": "angry-user@test.com", "to": "zhangxu@163.com", "subject": "吐槽一下", "email_thread": "你们的系统太难用了，我折腾了一下午。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "friend@daily.com", "to": "zhangxu@163.com", "subject": "感谢信", "email_thread": "谢谢张经理上次的招待，希望以后常联系。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "staff@team.com", "to": "zhangxu@163.com", "subject": "资料", "email_thread": "见附件。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "pm@company.com", "to": "zhangxu@163.com", "subject": "纪要", "email_thread": "附件是今天的会议结论，请知悉并按此执行。"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "boss@client.com", "to": "zhangxu@163.com", "subject": "还没好吗？", "email_thread": "项目延期三天了，今天必须给我个说法。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "student@university.com", "to": "zhangxu@163.com", "subject": "求职", "email_thread": "你好，我想去你们公司写代码，这是简历。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "old-pal@school.com", "to": "zhangxu@163.com", "subject": "老同学聚会", "email_thread": "小张，这周六咱们班同学在老地方聚聚。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "colleague@office.com", "to": "zhangxu@163.com", "subject": "转发：产品 Bug", "email_thread": "张旭，这个 Bug 你跟进处理一下。"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "stranger@web.com", "to": "zhangxu@163.com", "subject": "好文章", "email_thread": "https://blog.com/test 这篇文章不错。"}}, "outputs": {"classification": "ignore"}},
    {"inputs": {"email_input": {"author": "support@aliyun.com", "to": "zhangxu@163.com", "subject": "服务器到期", "email_thread": "您的阿里云服务器还有 3 天到期，请及时续费。"}}, "outputs": {"classification": "respond"}},

    # --- 5. 格式干扰类 (Structure) ---
    {"inputs": {"email_input": {"author": "vip@client.com", "to": "zhangxu@163.com", "subject": "【急】确认", "email_thread": "<html><body><b>请回复！</b></body></html>"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "global-biz@overseas.com", "to": "zhangxu@163.com", "subject": "Collaboration", "email_thread": "I'm interested in your project, let's talk."}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "notice@urgent.com", "to": "zhangxu@163.com", "subject": "@@@重要通知@@@", "email_thread": "!!!一定要看!!!"}}, "outputs": {"classification": "notify"}},
    {"inputs": {"email_input": {"author": "intern@team.com", "to": "zhangxu@163.com", "subject": "日报", "email_thread": "（超长报表内容...）最后一行：请张旭回复确认"}}, "outputs": {"classification": "respond"}},
    {"inputs": {"email_input": {"author": "mate@team.com", "to": "zhangxu@163.com", "subject": "🎉🎉🎉", "email_thread": "我们得奖啦！大家来会议室分蛋糕。"}}, "outputs": {"classification": "notify"}}
]

dataset_name = "163Email-Triage-Evaluation-V3"

if not client.has_dataset(dataset_name=dataset_name):
    dataset = client.create_dataset(dataset_name=dataset_name, description="测试163邮箱Agent的分拣准确率")
    client.create_examples(dataset_id=dataset.id, examples=examples_triage)
    print(f"✅ 数据集 {dataset_name} 创建成功！")


def target_email_assistant(inputs: dict) -> dict:
    """
    目标函数：直接调用原生分拣函数（脱离 Graph 框架测试核心逻辑）
    """

    test_store = InMemoryStore()
    initial_state = {"email_input": inputs["email_input"], "messages": []}

    # 直接把它当成普通函数调用，不用 .invoke()，也不用 config
    command_response = triage_router(initial_state, test_store)

    # command_response 返回的是一个 Command 对象，里面有 update 属性
    return {"classification_decision": command_response.update['classification_decision']}
    # 5. 返回结果给 LangSmith
    return {"classification_decision": response.update['classification_decision']}

def classification_evaluator(outputs: dict, reference_outputs: dict) -> bool:
    return outputs["classification_decision"].lower() == reference_outputs["classification"].lower()

if __name__ == "__main__":
    print("🚀 正在启动分拣准确率批量测试...")
    experiment_results = client.evaluate(
        target_email_assistant,
        data=dataset_name,
        evaluators=[classification_evaluator],
        experiment_prefix="Triage-Accuracy-Test",
        max_concurrency=2, # 并发数
    )
    print("🎉 测试完成！请登录 LangSmith 网页端查看评估报告！")