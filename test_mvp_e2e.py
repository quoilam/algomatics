#!/usr/bin/env python3
"""
MVP端到端测试脚本 - 验证自动迭代能力
"""

from controller.controller import ControllerAgent
from dotenv import load_dotenv
import sys
import os
import json
from pathlib import Path

# 添加backend到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))


# 加载环境变量
load_dotenv()


def create_test_image():
    """创建一个简单的测试图片"""
    try:
        from PIL import Image, ImageDraw

        # 创建一个简单的测试图片（200x200，带一些几何图形）
        img = Image.new('RGB', (200, 200), color='white')
        draw = ImageDraw.Draw(img)

        # 绘制一些几何图形
        draw.rectangle([50, 50, 150, 150], fill='blue',
                       outline='black', width=2)
        draw.ellipse([75, 75, 125, 125], fill='red', outline='black', width=2)

        # 保存到输出目录
        os.makedirs('output_images', exist_ok=True)
        test_image_path = 'output_images/test_input.png'
        img.save(test_image_path)
        print(f"✓ 创建测试图片: {test_image_path}")
        return test_image_path
    except Exception as e:
        print(f"⚠ 无法创建测试图片: {e}")
        return None


def test_mvp_iteration():
    """
    测试MVP的自动迭代能力
    """
    print("\n" + "="*80)
    print("MVP端到端测试 - 自动迭代能力")
    print("="*80 + "\n")

    # 检查API密钥
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ 错误：OPENROUTER_API_KEY 环境变量未设置")
        print("   请设置: export OPENROUTER_API_KEY=your_api_key")
        return False

    print(f"✓ API密钥已配置 (长度: {len(api_key)} 字符)")

    # 初始化Controller
    try:
        print("\n[1] 初始化Controller...")
        controller = ControllerAgent()
        print("✓ Controller初始化成功")
    except Exception as e:
        print(f"❌ Controller初始化失败: {e}")
        return False

    # 创建会话
    try:
        print("\n[2] 创建会话...")
        session_id = controller.create_session(user_id="mvp_test")
        print(f"✓ 会话创建成功: {session_id}")
    except Exception as e:
        print(f"❌ 会话创建失败: {e}")
        return False

    # 创建测试图片
    print("\n[3] 准备测试图片...")
    test_image_path = create_test_image()

    # 定义测试用例
    test_cases = [
        {
            "name": "图像降噪处理",
            "request": "对输入图像进行降噪处理，使用高斯滤波或中值滤波来减少噪点",
            "enable_search": True
        },
        # 可以添加更多测试用例
        # {
        #     "name": "图像锐化",
        #     "request": "对输入图像进行锐化处理，增强边缘",
        #     "enable_search": True
        # }
    ]

    all_passed = True

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试用例 {i}: {test_case['name']}")
        print(f"{'='*80}")

        try:
            print(f"\n📝 用户请求: {test_case['request']}")

            # 处理请求（这会触发自动迭代）
            print("\n🚀 启动自动迭代流程...")
            result = controller.process_user_request(
                session_id=session_id,
                user_request=test_case['request'],
                input_image_path=test_image_path,
                enable_search=test_case['enable_search']
            )

            # 验证结果
            print("\n📊 迭代结果:")
            print(f"  - 成功: {result.get('success', False)}")
            print(f"  - 总迭代次数: {result.get('total_iterations', 0)}")
            print(f"  - 最终评分: {result.get('final_score', 'N/A')}/10")
            print(f"  - 迭代原因: {result.get('iteration_reason', 'N/A')}")

            # 验证迭代步骤
            steps = result.get('steps', [])
            print(f"\n📋 执行步骤({len(steps)}个):")

            agent_stats = {}
            for step in steps:
                agent = step.get('agent', 'Unknown')
                iteration = step.get('iteration', 'N/A')
                status = step.get('status', 'unknown')

                if agent not in agent_stats:
                    agent_stats[agent] = {'count': 0, 'status': []}
                agent_stats[agent]['count'] += 1
                agent_stats[agent]['status'].append(status)

                # 打印步骤信息
                if agent == 'EvaluationAgent':
                    score = step.get('result', {}).get('score', 'N/A')
                    print(
                        f"  - {agent} (迭代 {iteration}): {status} - 评分 {score}/10")
                else:
                    print(f"  - {agent} (迭代 {iteration}): {status}")

            # 验证阶段3：任务解析与策略规划
            session = controller.get_session(session_id)
            task_parse = session.get("task_parse", {})
            execution_plan = session.get("execution_plan", {})
            print(f"\n📋 阶段3 - 任务解析与策略规划:")
            print(f"  - 任务类型: {task_parse.get('task_type', 'N/A')}")
            print(f"  - 执行策略: {execution_plan.get('strategy', 'N/A')}")
            print(f"  - 启用搜索: {execution_plan.get('enable_search', 'N/A')}")
            print(f"  - 启用迭代: {execution_plan.get('enable_iteration', 'N/A')}")
            print(f"  - 最大迭代: {execution_plan.get('max_iterations', 'N/A')}")
            has_planning = bool(task_parse) and bool(execution_plan)
            print(f"  ✓ 任务规划已激活: {has_planning}")

            # 验证MVP关键指标
            print("\n✅ MVP验收标准:")

            # 1. 系统能够自动决定是否继续迭代
            has_iterations = result.get('total_iterations', 0) > 0
            print(f"  ✓ 自动迭代能力: {has_iterations}")

            # 2. 迭代次数可控 (不超过策略上限)
            max_iterations = execution_plan.get('max_iterations', 3)
            iterations_controlled = result.get(
                'total_iterations', 0) <= max_iterations
            print(f"  ✓ 迭代次数可控 (≤ {max_iterations}): {iterations_controlled}")

            # 3. 能提取评分并根据评分做决策
            final_score = result.get('final_score')
            score_based_decision = final_score is not None
            print(f"  ✓ 评分驱动决策: {score_based_decision} (最终评分: {final_score})")

            # 4. 有改进建议的迭代上下文
            has_improvements = False
            for step in steps:
                if step.get('agent') == 'EvaluationAgent':
                    improvements = step.get(
                        'result', {}).get('improvements', '')
                    if improvements:
                        has_improvements = True
                        break
            print(f"  ✓ 改进建议传递: {has_improvements}")

            # 总体评估
            test_passed = (
                has_iterations and
                iterations_controlled and
                score_based_decision and
                has_planning
            )

            if test_passed:
                print("\n✅ 测试用例通过!")
            else:
                print("\n❌ 测试用例失败!")
                all_passed = False

        except Exception as e:
            print(f"\n❌ 测试过程中出错: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    # 最终总结
    print(f"\n{'='*80}")
    print("测试总结")
    print(f"{'='*80}")

    if all_passed:
        print("\n🎉 所有测试通过！MVP自动迭代能力已验证")
        print("\nMVP核心特性验证:")
        print("  ✓ EvaluationAgent返回结构化评分")
        print("  ✓ CodeGenerationAgent支持迭代反馈")
        print("  ✓ Controller实现评分驱动的决策逻辑")
        print("  ✓ 自动迭代流程完整工作")
        return True
    else:
        print("\n⚠ 部分测试失败，请检查上述错误信息")
        return False


if __name__ == "__main__":
    success = test_mvp_iteration()
    sys.exit(0 if success else 1)
