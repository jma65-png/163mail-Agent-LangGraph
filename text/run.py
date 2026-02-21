import uuid
from langgraph.types import Command
from core.graph import overall_workflow
from services.email_163 import fetch_latest_163_email

def run_real_email_agent():
    print("==================================================")
    print("[系统启动] 正在连接 163 邮箱获取最新邮件...")
    print("==================================================")

    # 1. 获取真实邮件数据
    real_email_data = fetch_latest_163_email()

    if isinstance(real_email_data, str):
        print(f"❌ 邮件抓取失败，流程终止。\n原因: {real_email_data}")
        return

    print("\n✅ 成功获取最新邮件！")
    print(f"📧 标题: {real_email_data.get('subject')}")
    print(f"👤 发件人: {real_email_data.get('author')}")
    print("\n正在将邮件移交至 AI 分拣中心...")
    print("-" * 50)

    # 2. 初始化工作流配置
    graph = overall_workflow
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # 初始输入状态：把真实邮件喂进去
    current_input = {"email_input": real_email_data}

    # 3. 启动人机回环 (HITL) 持续监听
    while True:
        interrupted = False

        # 运行图（可能是初始运行，也可能是带指令恢复运行）
        for event in graph.stream(current_input, config=config):
            for node_name in event:
                print(f"[节点流转] -> {node_name}")

            # 捕获 Interrupt (发现需要人工审核)
            if "__interrupt__" in event:
                interrupted = True
                interrupt_data = event["__interrupt__"][0].value[0]
                action = interrupt_data.get('action_request', {}).get('action', '未知操作')
                description = interrupt_data.get('description', '')

                print("\n" + "✅" * 25)
                print(f"🛑 [系统暂停] 触发人工审核闸口！")
                print(f"🔹 AI 申请执行工具: {action}")
                print(f"🔹 操作详情预览:\n{description}")
                print("✅  " * 25)

                print("\n请下达指挥官指令：")
                print(" [y] -> 批准操作 (让 AI 继续执行)")
                print(" [n] -> 驳回操作 (直接忽略并结束)")
                print(" [其他文字] -> 打回重做 (输入修改意见，AI 将重新拟稿)")

                user_choice = input("\n👉 指令: ").strip()

                if user_choice.lower() == 'y':
                    resume_action = [{"type": "accept", "args": {}}]
                elif user_choice.lower() == 'n':
                    resume_action = [{"type": "ignore", "args": {}}]
                else:
                    resume_action = [{"type": "response", "args": user_choice}]

                # 打包你的指令，准备下一轮循环唤醒 AI
                print(f"\n🔄 收到指令，正在唤醒 AI 恢复运行...")
                current_input = Command(resume=resume_action)
                break  # 跳出当前流，进入下一轮 while 循环


        if not interrupted:
            break

    print("\n[任务结束] 当前邮件的全流程处理已完毕！")


if __name__ == "__main__":
    run_real_email_agent()