#!/usr/bin/env python3
"""
端到端测试脚本 - 不经过前端，直接测试完整业务流程
使用真实的 API Key 进行测试
"""

import os
import sys
import json
from datetime import datetime

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from controller.controller import ControllerAgent


def test_end_to_end():
    """执行端到端测试"""
    
    print("=" * 60)
    print("端到端业务流程测试")
    print("=" * 60)
    
    # 检查环境变量
    print("\n[1] 检查环境变量...")
    required_vars = ['TAVILY_API_KEY', 'OPENROUTER_API_KEY']
    for var in required_vars:
        if not os.getenv(var):
            print(f"❌ 缺少环境变量: {var}")
            return False
        print(f"✓ {var} 已设置")
    
    # 准备测试图片
    print("\n[2] 准备测试图片...")
    from PIL import Image
    import numpy as np
    
    # 创建一张简单的测试图片
    test_image_path = "test_input.png"
    img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    Image.fromarray(img).save(test_image_path)
    print(f"✓ 测试图片已创建: {test_image_path}")
    
    # 初始化控制器
    print("\n[3] 初始化 ControllerAgent...")
    try:
        controller = ControllerAgent()
        print("✓ ControllerAgent 初始化成功")
    except Exception as e:
        print(f"❌ ControllerAgent 初始化失败: {e}")
        return False
    
    # 创建会话
    print("\n[4] 创建会话...")
    session_id = controller.create_session(user_id="test_user")
    print(f"✓ 会话 ID: {session_id}")
    
    # 用户请求
    user_request = "给图片添加复古滤镜"
    print(f"\n[5] 用户请求: {user_request}")
    
    # 执行完整流程
    print("\n[6] 开始执行完整业务流程...")
    print("-" * 60)
    
    start_time = datetime.now()
    
    try:
        result = controller.process_user_request(
            session_id=session_id,
            user_request=user_request,
            input_image_path=test_image_path,
            enable_search=True
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("-" * 60)
        print(f"\n[7] 执行完成，耗时: {duration:.2f} 秒")
        
        # 检查结果
        print("\n[8] 检查结果...")
        
        if not result.get('success'):
            print(f"❌ 流程失败: {result.get('error', '未知错误')}")
            return False
        
        print("✓ 流程执行成功")
        
        # 打印各步骤状态
        print("\n[9] 各 Agent 执行情况:")
        for i, step in enumerate(result.get('steps', []), 1):
            agent = step['agent']
            action = step['action']
            status = step['status']
            emoji = "✅" if status == 'completed' else "❌"
            print(f"   {i}. {agent} - {action}: {emoji} {status}")
            
            # 打印关键信息
            if agent == 'RetrievalAgent':
                search_result = step.get('result', '')
                if isinstance(search_result, str):
                    preview = search_result[:100].replace('\n', ' ')
                    print(f"      搜索结果预览: {preview}...")
                elif isinstance(search_result, list):
                    print(f"      找到 {len(search_result)} 条结果")
            
            if agent == 'CodeGenerationAgent':
                code = step.get('result', '')
                if isinstance(code, str):
                    lines = code.split('\n')
                    print(f"      代码行数: {len(lines)}")
                    print(f"      代码预览: {code[:80]}...")
            
            if agent == 'ExecutionAgent':
                exec_result = step.get('result', {})
                if exec_result.get('success'):
                    output_path = exec_result.get('output_path')
                    print(f"      输出路径: {output_path}")
                    if output_path and os.path.exists(output_path):
                        file_size = os.path.getsize(output_path)
                        print(f"      文件大小: {file_size} bytes")
                else:
                    print(f"      执行错误: {exec_result.get('error', '未知')}")
            
            if agent == 'EvaluationAgent':
                eval_result = step.get('result', {})
                if isinstance(eval_result, dict):
                    eval_text = eval_result.get('evaluation_text', '')[:100]
                    print(f"      评估预览: {eval_text}...")
        
        # 获取会话摘要
        print("\n[10] 会话摘要:")
        summary = controller.get_session_summary(session_id)
        print(f"   状态: {summary.get('status')}")
        print(f"   迭代次数: {summary.get('iteration_count')}")
        
        # 检查输出文件
        if summary.get('output_image'):
            output_path = summary['output_image']
            if os.path.exists(output_path):
                print(f"   ✓ 输出图片存在: {output_path}")
            else:
                print(f"   ⚠ 输出图片路径无效: {output_path}")
        
        print("\n" + "=" * 60)
        print("✅ 端到端测试 PASSED")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print("-" * 60)
        print(f"\n❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理测试文件
        if os.path.exists(test_image_path):
            os.remove(test_image_path)
            print(f"\n[清理] 已删除测试图片: {test_image_path}")


if __name__ == "__main__":
    success = test_end_to_end()
    sys.exit(0 if success else 1)
