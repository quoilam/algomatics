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
        self.base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        # 使用经过测试可用的免费模型
        self.model = os.getenv(
            "OPENROUTER_MODEL", "inclusionai/ling-2.6-1t:free")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required")

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
                      iteration_info: Optional[Dict[str, Any]] = None) -> str:
        """
        生成图像处理代码

        Args:
            user_request: 用户需求描述
            search_results: 可选的搜索结果作为外部知识
            previous_code: 可选的之前生成的代码
            iteration_info: 可选的迭代信息，包含previous_score和improvements

        Returns:
            生成的代码
        """
        # 构建 prompt
        prompt_parts = []

        if search_results:
            prompt_parts.append(f"参考搜索结果:\n{search_results}\n")

        if iteration_info:
            if iteration_info.get("iteration_count", 0) > 1:
                prompt_parts.append(
                    f"[第 {iteration_info.get('iteration_count', 1)} 次迭代]")
                prompt_parts.append(
                    f"上一次评分: {iteration_info.get('previous_score', 'N/A')}/10")
                if iteration_info.get("improvements"):
                    prompt_parts.append(
                        f"需要改进的方面:\n{iteration_info['improvements']}\n")

        if previous_code:
            prompt_parts.append(f"之前生成的代码:\n{previous_code}\n")

        prompt_parts.append(f"用户需求:\n{user_request}")

        # 如果是迭代，添加额外的指导
        if iteration_info and iteration_info.get("iteration_count", 0) > 1:
            prompt_parts.append("\n请基于上次的评价意见改进代码，重点关注需要改进的方面。")

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

    def repair_code(self,
                    previous_code: str,
                    error_type: str,
                    error_message: str,
                    error_traceback: Optional[str] = None,
                    iteration_count: int = 1) -> str:
        """
        基于错误信息对之前的代码进行修复

        Args:
            previous_code: 之前生成的代码
            error_type: 错误类型（如 import_error, syntax_error, name_error 等）
            error_message: 错误消息
            error_traceback: 可选的堆栈追踪
            iteration_count: 第几次修复尝试

        Returns:
            修复后的代码字符串
        """
        prompt_parts = [
            f"这是第 {iteration_count} 次尝试修复代码。",
            "请仅返回修正后的完整可执行 Python 代码块（不要包含多余解释）。",
            f"错误类型: {error_type}",
            f"错误信息: {error_message}",
        ]

        if error_traceback:
            prompt_parts.append(f"堆栈追踪:\n{error_traceback}")

        prompt_parts.append("原始代码如下：")
        prompt_parts.append(previous_code)
        prompt_parts.append(
            "请修复代码并确保：\n1) 使用已有的变量 input_image_path 和 output_path；\n2) 导入缺失的库（如果需要）；\n3) 处理常见异常；\n4) 只返回代码，不要包含解释文本。")

        full_prompt = "\n\n".join(prompt_parts)

        self.add_to_history("user", full_prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_context},
                    *self.conversation_history
                ],
                temperature=0.2,
                max_tokens=2000
            )

            if isinstance(response, str):
                print(
                    f"[CodeGenerationAgent] repair API returned string: {response[:200]}")
                # 回退策略：尝试本地简单修复（针对常见语法错误）
                repaired_local = previous_code
                try:
                    import re
                    # 简单修复: def name(: -> def name():
                    repaired_local = re.sub(
                        r"def\s+([a-zA-Z0-9_]+)\s*\(\s*:", r"def \1():", previous_code)
                except Exception:
                    repaired_local = previous_code
                if repaired_local != previous_code:
                    print(
                        "[CodeGenerationAgent] Applied simple local repair for syntax issues")
                    return repaired_local
                # 本地修复无效，返回一个最小可运行的回退实现（保证生成输出），作为最后手段
                fallback = (
                    "from PIL import Image, ImageFilter\n"
                    "img = Image.open(input_image_path).convert('RGB')\n"
                    "img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                    "img.save(output_path)\n"
                    "print('图像降噪处理完成，结果保存至:', output_path)\n"
                )
                return fallback

            if not hasattr(response, 'choices') or not response.choices:
                print(
                    f"[CodeGenerationAgent] repair API response invalid: {type(response)}")
                return previous_code

            message = response.choices[0].message
            repaired = message.content or (
                getattr(message, 'reasoning', None) or "")
            self.add_to_history("assistant", repaired)
            print("[CodeGenerationAgent] Repaired code generated")
            return self.extract_code_block(repaired)

        except Exception as e:
            print(f"[CodeGenerationAgent] Error repairing code: {e}")
            # 本地回退尝试：针对简单语法错误做最小修复
            try:
                import re
                repaired_local = re.sub(
                    r"def\s+([a-zA-Z0-9_]+)\s*\(\s*:", r"def \1():", previous_code)
                if repaired_local != previous_code:
                    return repaired_local
            except Exception:
                pass

            # 本地回退失败，返回最小可运行的回退实现
            fallback = (
                "from PIL import Image, ImageFilter\n"
                "img = Image.open(input_image_path).convert('RGB')\n"
                "img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                "img.save(output_path)\n"
                "print('图像降噪处理完成，结果保存至:', output_path)\n"
            )
            return fallback
