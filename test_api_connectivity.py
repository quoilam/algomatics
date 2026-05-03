#!/usr/bin/env python3
"""
API 连接性测试脚本
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def test_openrouter_api():
    """测试 OpenRouter API 连接"""
    print("="*80)
    print("测试 OpenRouter API")
    print("="*80)
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENROUTER_MODEL", "qwen/qwen-turbo")
    
    print(f"✓ API Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"✓ Base URL: {base_url}")
    print(f"✓ Model: {model}")
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        print("\n发送测试请求...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个有帮助的助手。"},
                {"role": "user", "content": "请简单回复：ok"}
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        print(f"✓ 响应成功!")
        print(f"  - 模型: {response.model}")
        print(f"  - 内容: {response.choices[0].message.content[:100]}")
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tavily_api():
    """测试 Tavily API 连接"""
    print("\n" + "="*80)
    print("测试 Tavily API")
    print("="*80)
    
    api_key = os.getenv("TAVILY_API_KEY")
    print(f"✓ API Key: {api_key[:20]}...{api_key[-10:]}")
    
    try:
        from tavily import TavilyClient
        
        client = TavilyClient(api_key=api_key)
        print("\n发送测试搜索...")
        
        response = client.search("python image processing")
        
        print(f"✓ 搜索成功!")
        print(f"  - 结果数量: {len(response.get('results', []))}")
        if response.get('results'):
            print(f"  - 第一个结果: {response['results'][0].get('title', 'N/A')[:80]}")
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success1 = test_openrouter_api()
    success2 = test_tavily_api()
    
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    if success1 and success2:
        print("✅ 所有API测试通过!")
    else:
        if not success1:
            print("❌ OpenRouter API 测试失败")
        if not success2:
            print("❌ Tavily API 测试失败")
