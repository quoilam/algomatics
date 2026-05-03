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
                    iteration_count: int = 1,
                    error_context: Optional[Dict[str, Any]] = None) -> str:
        """
        基于错误信息对之前的代码进行修复 - Phase 2增强版本

        Args:
            previous_code: 之前生成的代码
            error_type: 错误类型（如 import_error, syntax_error, name_error 等）
            error_message: 错误消息
            error_traceback: 可选的堆栈追踪
            iteration_count: 第几次修复尝试
            error_context: 可选的详细错误上下文信息

        Returns:
            修复后的代码字符串
        """
        # 尝试本地修复策略（无需LLM，更快）
        local_repair = self._try_local_repair(
            previous_code, error_type, error_message, error_context)
        if local_repair != previous_code:
            print(
                f"[CodeGenerationAgent] Local repair applied for {error_type}")
            return local_repair

        # 本地修复失败，调用LLM进行修复
        repair_strategy = self._get_repair_strategy(
            error_type, error_message, error_context)

        prompt_parts = [
            f"这是第 {iteration_count} 次尝试修复代码。",
            "请仅返回修正后的完整可执行 Python 代码块（用```python包裹）（不要包含多余解释或警告）。",
            f"错误类型: {error_type}",
            f"错误信息: {error_message}",
        ]

        # 添加修复策略指导
        prompt_parts.append("\n修复策略指导:")
        prompt_parts.extend(repair_strategy["hints"])

        if error_traceback:
            prompt_parts.append(f"\n堆栈追踪:\n{error_traceback}")

        prompt_parts.append("\n原始代码如下：")
        prompt_parts.append("```python")
        prompt_parts.append(previous_code)
        prompt_parts.append("```")

        prompt_parts.append(
            "\n请根据上述错误信息和修复策略修复代码，确保：\n"
            "1) 使用已有的变量 input_image_path 和 output_path；\n"
            "2) 导入缺失的库（如果需要）；\n"
            "3) 修复特定的错误类型；\n"
            "4) 添加必要的错误处理；\n"
            "5) 代码必须能够生成输出图片。\n"
            "6) 只返回代码，用```python和```包裹，不要包含任何解释文本。")

        full_prompt = "\n\n".join(prompt_parts)
        self.add_to_history("user", full_prompt)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_context},
                    *self.conversation_history
                ],
                temperature=0.3,  # 降低temperature以获得更稳定的修复
                max_tokens=2500
            )

            if isinstance(response, str):
                print(
                    f"[CodeGenerationAgent] repair API returned string: {response[:200]}")
                return self._get_fallback_code(error_type)

            if not hasattr(response, 'choices') or not response.choices:
                print(
                    f"[CodeGenerationAgent] repair API response invalid: {type(response)}")
                return self._get_fallback_code(error_type)

            message = response.choices[0].message
            repaired = message.content or (
                getattr(message, 'reasoning', None) or "")
            self.add_to_history("assistant", repaired)
            print("[CodeGenerationAgent] Repaired code generated")
            return self.extract_code_block(repaired)

        except Exception as e:
            print(f"[CodeGenerationAgent] Error repairing code: {e}")
            return self._get_fallback_code(error_type)

    def _try_local_repair(self,
                          code: str,
                          error_type: str,
                          error_message: str,
                          error_context: Optional[Dict[str, Any]] = None) -> str:
        """
        尝试本地修复，无需调用LLM（快速路径）

        Args:
            code: 要修复的代码
            error_type: 错误类型
            error_message: 错误信息
            error_context: 错误上下文

        Returns:
            修复后的代码，如果无法修复则返回原代码
        """
        import re

        # 缺失导入修复
        if error_type == "import_error" and error_context:
            missing_module = error_context.get("missing_import")
            if missing_module:
                # 通用导入修复策略
                import_map = {
                    "cv2": "import cv2",
                    "Image": "from PIL import Image",
                    "ImageFilter": "from PIL import Image, ImageFilter",
                    "np": "import numpy as np",
                    "pd": "import pandas as pd",
                    "scipy": "import scipy",
                }

                if missing_module in import_map:
                    import_stmt = import_map[missing_module]
                    # 检查是否已经有import语句
                    if import_stmt not in code:
                        # 在代码开头添加import
                        code = import_stmt + "\n" + code
                        return code

        # 简单语法错误修复
        if error_type == "syntax_error":
            # 修复: def name(: -> def name():
            fixed = re.sub(
                r"def\s+([a-zA-Z0-9_]+)\s*\(\s*:", r"def \1():", code)
            if fixed != code:
                return fixed

            # 修复缺失的冒号
            fixed = re.sub(r"(if|elif|else|for|while|def|class)\b(.*)([^\s:])$",
                           r"\1\2\3:", code, flags=re.MULTILINE)
            if fixed != code:
                return fixed

        # 名称错误修复（常见的库别名）
        if error_type == "name_error" and error_context:
            undefined_name = error_context.get("undefined_name")
            if undefined_name == "cv2" and "import cv2" not in code:
                code = "import cv2\n" + code
                return code
            elif undefined_name == "np" and "import numpy" not in code:
                code = "import numpy as np\n" + code
                return code

        return code  # 无法修复，返回原代码

    def _get_repair_strategy(self,
                             error_type: str,
                             error_message: str,
                             error_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        根据错误类型获取修复策略

        Args:
            error_type: 错误类型
            error_message: 错误信息
            error_context: 错误上下文

        Returns:
            包含修复策略和提示的字典
        """
        strategies = {
            "import_error": {
                "hints": [
                    "✓ 确保导入了所需的库（cv2, Image, np 等）",
                    "✓ 添加缺失的导入语句到代码开头",
                    "✓ 检查库名是否拼写正确"
                ]
            },
            "name_error": {
                "hints": [
                    "✓ 检查变量是否已定义",
                    "✓ 如果使用了库别名（np, pd, cv2），需要先导入库",
                    "✓ 检查变量名拼写是否正确"
                ]
            },
            "attribute_error": {
                "hints": [
                    "✓ 检查对象方法或属性名是否正确",
                    "✓ 使用正确的库API（例如 Image.open() 而不是 Image.read()）",
                    "✓ 验证库的版本兼容性"
                ]
            },
            "type_error": {
                "hints": [
                    "✓ 检查函数参数的类型是否正确",
                    "✓ 如果期望 np.ndarray，检查是否需要转换类型",
                    "✓ 检查图像对象的格式（RGB vs BGR vs Grayscale）"
                ]
            },
            "file_error": {
                "hints": [
                    "✓ 使用提供的 input_image_path 变量读取输入图片",
                    "✓ 使用 output_path 变量保存输出图片",
                    "✓ 不要硬编码文件路径"
                ]
            },
            "syntax_error": {
                "hints": [
                    "✓ 检查括号、引号是否配对",
                    "✓ 检查缩进是否正确",
                    "✓ if/for/while/def 等语句是否以冒号结尾"
                ]
            },
            "runtime_error": {
                "hints": [
                    "✓ 检查代码逻辑是否正确",
                    "✓ 添加必要的错误处理（try-except）",
                    "✓ 验证输入数据的格式和范围"
                ]
            }
        }

        return strategies.get(error_type, {"hints": ["✓ 根据错误信息修复代码"]})

    def _get_fallback_code(self, error_type: str) -> str:
        """
        获取回退代码 - 简单但可运行的默认实现

        Args:
            error_type: 错误类型

        Returns:
            回退代码
        """
        fallback_map = {
            "import_error": (
                "import cv2\n"
                "from PIL import Image, ImageFilter\n"
                "import numpy as np\n\n"
                "img = Image.open(input_image_path).convert('RGB')\n"
                "img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                "img.save(output_path)\n"
                "print('Fallback: Image processing completed')\n"
            ),
            "name_error": (
                "from PIL import Image, ImageFilter\n\n"
                "img = Image.open(input_image_path).convert('RGB')\n"
                "img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                "img.save(output_path)\n"
                "print('Fallback: Name error fixed, using PIL')\n"
            ),
            "syntax_error": (
                "from PIL import Image, ImageFilter\n\n"
                "try:\n"
                "    img = Image.open(input_image_path).convert('RGB')\n"
                "    img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                "    img.save(output_path)\n"
                "except Exception as e:\n"
                "    print(f'Error: {e}')\n"
            ),
            "type_error": (
                "from PIL import Image, ImageFilter\n\n"
                "img = Image.open(input_image_path).convert('RGB')\n"
                "img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                "img.save(output_path)\n"
                "print('Fallback: Using PIL with proper type handling')\n"
            ),
            "file_error": (
                "from PIL import Image, ImageFilter\n"
                "import os\n\n"
                "if input_image_path and os.path.exists(input_image_path):\n"
                "    img = Image.open(input_image_path).convert('RGB')\n"
                "    img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                "    img.save(output_path)\n"
                "else:\n"
                "    print(f'File not found: {input_image_path}')\n"
            )
        }

        # 默认回退代码
        default_fallback = (
            "from PIL import Image, ImageFilter\n\n"
            "img = Image.open(input_image_path).convert('RGB')\n"
            "img = img.filter(ImageFilter.MedianFilter(size=3))\n"
            "img.save(output_path)\n"
            "print('Fallback: Image denoising completed')\n"
        )

        return fallback_map.get(error_type, default_fallback)
