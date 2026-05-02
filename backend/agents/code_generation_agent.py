"""
代码生成 Agent: 通过外部知识或大模型本身的知识，结合本地图像处理库生成代码
- 需要有系统上下文 (用户设备 硬件配置 操作系统等)
- 需要有环境上下文 (开发者提前安装好的图像处理工具库)
- 需要有独立的对话上下文
"""

import os
from typing import Optional, List, Dict, Any
from openai import OpenAI


class CodeGenerationAgent:
    """代码生成 Agent，负责生成图像处理代码"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        # 使用经过测试可用的免费模型
        self.model = os.getenv("OPENROUTER_MODEL", "inclusionai/ling-2.6-1t:free")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # 系统上下文 - 初始化时通过 prompt 给出
        self.system_context = """
你是一个专业的图像处理代码生成专家。你需要根据用户的需求生成 Python 代码。

系统环境信息:
- 操作系统：Linux/Ubuntu
- Python 版本：3.9+
- 已安装的图像处理库：opencv-python, Pillow (PIL), numpy, scipy, matplotlib

可用库说明:
- opencv-python (cv2): 用于图像读取、处理、变换等
- Pillow (PIL): 用于图像打开、编辑、保存
- numpy: 用于数组和矩阵操作
- matplotlib: 用于图像显示和可视化

代码要求:
1. 生成的代码必须是可以直接运行的完整代码，不要定义函数后不调用
2. 使用上述已安装的库
3. 代码需要包含必要的注释
4. **重要**: 输入图片路径使用变量 `input_image_path`，输出图片路径使用变量 `output_path`，这两个变量在执行环境中已经提供，不要硬编码文件名
5. 错误处理要完善
6. 代码执行后必须生成输出图片到 output_path 指定的位置
7. 不要使用 input() 或 cv2.imshow() 等需要用户交互的函数
8. 不要使用 ImageFilter 等未导入的模块，如果需要使用请先导入
9. 直接使用 input_image_path 和 output_path 变量，不要重新赋值
"""
        
        # 对话历史上下文
        self.conversation_history: List[Dict[str, str]] = []
    
    def set_system_context(self, context: str):
        """设置系统上下文"""
        self.system_context = context
    
    def add_to_history(self, role: str, content: str):
        """添加对话到历史"""
        self.conversation_history.append({"role": role, "content": content})
    
    def clear_history(self):
        """清除对话历史"""
        self.conversation_history = []
    
    def generate_code(self, 
                     user_request: str, 
                     search_results: Optional[str] = None,
                     previous_code: Optional[str] = None,
                     feedback: Optional[str] = None) -> str:
        """
        生成图像处理代码
        
        Args:
            user_request: 用户需求描述
            search_results: 可选的搜索结果作为外部知识
            previous_code: 可选的之前生成的代码
            feedback: 可选的用户反馈
            
        Returns:
            生成的代码
        """
        # 构建 prompt
        prompt_parts = []
        
        if search_results:
            prompt_parts.append(f"参考搜索结果:\n{search_results}\n")
        
        if previous_code:
            prompt_parts.append(f"之前生成的代码:\n{previous_code}\n")
        
        if feedback:
            prompt_parts.append(f"用户反馈:\n{feedback}\n")
        
        prompt_parts.append(f"用户需求:\n{user_request}")
        
        full_prompt = "\n\n".join(prompt_parts)
        
        # 添加到历史
        self.add_to_history("user", full_prompt)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,  # 使用环境变量中的模型，默认使用免费的 OpenRouter 模型
                messages=[
                    {"role": "system", "content": self.system_context},
                    *self.conversation_history
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            # Check if response is a string (error case) or has choices attribute
            if isinstance(response, str):
                error_msg = f"API returned a string instead of response object: {response[:200]}"
                print(f"[CodeGenerationAgent] {error_msg}")
                return f"# 代码生成失败：{error_msg}"
            
            if not hasattr(response, 'choices') or not response.choices:
                error_msg = f"API response has no choices attribute: {type(response)}"
                print(f"[CodeGenerationAgent] {error_msg}")
                return f"# 代码生成失败：{error_msg}"
            
            # Handle models that put content in reasoning field
            message = response.choices[0].message
            generated_code = message.content
            
            # Some models (like nvidia/nemotron) may put content in reasoning field
            if generated_code is None and hasattr(message, 'reasoning') and message.reasoning:
                generated_code = message.reasoning
            
            if generated_code is None:
                error_msg = f"API response has no content: {message}"
                print(f"[CodeGenerationAgent] {error_msg}")
                return f"# 代码生成失败：{error_msg}"
            
            # 将 AI 响应添加到历史
            self.add_to_history("assistant", generated_code)
            
            print("[CodeGenerationAgent] Code generated successfully")
            return generated_code
            
        except Exception as e:
            print(f"[CodeGenerationAgent] Error generating code: {e}")
            return f"# 代码生成失败：{str(e)}"
    
    def extract_code_block(self, text: str) -> str:
        """从响应中提取代码块"""
        import re
        pattern = r'```(?:python)?\s*(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return matches[0].strip()
        return text.strip()
