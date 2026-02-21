import uuid
from langgraph.types import Command
from core.graph import overall_workflow


def test_workflow_with_mock_data():
    mock_email_input = {
        "author": "老板 <boss@company.com>",
        "to": "我 <me@company.com>",
        "subject": "关于明天会议的紧急确认",
        "email_thread": "明天的项目汇报会议，你准备好 PPT 了吗？请务必今天下班前回复我。"
    }

    graph = overall_workflow
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("[测试开始] 注入 Mock 邮件数据...")

    # 初始的输入状态
    current_input = {"email_input": mock_email_input}

    # 使用 while 循环，支持无限次的“打回重写”
    while True:
        interrupted = False

        # 运行图（可能是初始运行，也可能是带指令恢复运行）
        for event in graph.stream(current_input, config=config):
            for node_name in event:
                print(f"✅ 节点流转: {node_name}")

            # 捕获 Interrupt (发现需要人工审核)
            if "__interrupt__" in event:
                interrupted = True
                interrupt_data = event["__interrupt__"][0].value[0]
                action = interrupt_data.get('action_request', {}).get('action', '未知操作')
                description = interrupt_data.get('description', '')

                print("\n" + "✅ " * 20)
                print(f"🛑 触发人工审核 (等待你的决定)")
                print(f"🔹 拟调用工具: {action}")
                print(f"🔹 邮件草稿预览:\n{description}")
                print("✅ " * 20)

                print("\n你的选择：")
                print(" [y] -> 没问题，批准发送！")
                print(" [n] -> 算了，忽略这次操作。")
                print(" [任意其他文字] -> 打回给 AI，让它按照你的意见修改。")

                user_choice = input("\n请输入指令: ").strip()

                if user_choice.lower() == 'y':
                    resume_action = [{"type": "accept", "args": {}}]
                elif user_choice.lower() == 'n':
                    resume_action = [{"type": "ignore", "args": {}}]
                else:
                    resume_action = [{"type": "response", "args": user_choice}]

                # 把用户的指令打包成 Command，准备在下一轮 while 循环中唤醒 AI
                current_input = Command(resume=resume_action)
                break  # 跳出当前的 for 循环流，马上进入下一轮 while 循环去“唤醒”它

        # 如果走完了 for 循环，并且没有触发任何中断，说明图已经跑到 END 了，彻底结束
        if not interrupted:
            break

    print("\n[测试结束] 整个工作流已彻底跑完。")


if __name__ == "__main__":
    test_workflow_with_mock_data()


