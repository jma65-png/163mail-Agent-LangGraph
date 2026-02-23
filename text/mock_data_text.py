import uuid
from langgraph.types import Command
from core.graph import overall_workflow

def test_workflow_with_mock_data():
    # 🌟 重点：这里换成了一封专门测试 RAG（知识库）的 HR 邮件
    mock_email_input = {
        "author": "张煦 <zhangxu@163.com>",
        "to": "AI 助手 <agent@local>",
        "subject": "帮我写一封求职信",
        "email_thread": """
            小助手，我想投递这个岗位：
            https://www.zhipin.com/web/geek/jobs?query=%E6%95%B0%E6%8D%AE%E5%BC%80%E5%8F%91&city=101210100
            
    
            请你：
            1. 先读取这个链接里的岗位要求。
            2. 然后去我的简历库里找找我有哪些经历能匹配上。
            3. 最后结合岗位要求和我的真实经历，给 HR (hr@target-company.com) 写一封热情、专业的求职邮件草稿。
            """
    }

    graph = overall_workflow
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("等待 Agent 思考...")

    current_input = {"email_input": mock_email_input}

    while True:
        interrupted = False

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
                print(f"触发人工审核 (等待你的决定)")
                print(f"拟调用工具: {action}")
                print(f"邮件草稿预览:\n{description}")
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

                current_input = Command(resume=resume_action)
                break

        if not interrupted:
            break

    print("\n[测试结束] 整个工作流已彻底跑完。")


if __name__ == "__main__":
    test_workflow_with_mock_data()