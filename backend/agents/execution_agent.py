"""
执行 Agent: 用于执行算法代码生成图片，总结前序操作链路，以及执行过程中遇到的错误
- 不需要考虑沙箱、隔离等安全问题
"""

import os
import traceback
from typing import Optional, Dict, Any, Tuple
from PIL import Image
import io


class ExecutionAgent:
    """执行 Agent，负责执行生成的算法代码"""

    def __init__(self):
        self.output_dir = "output_images"
        os.makedirs(self.output_dir, exist_ok=True)

        # 预导入常用库
        try:
            import cv2
            self.cv2 = cv2
        except ImportError:
            self.cv2 = None

        try:
            from PIL import Image
            self.Image = Image
        except ImportError:
            self.Image = None

        try:
            import numpy as np
            self.np = np
        except ImportError:
            self.np = None

    def execute_code(self,
                     code: str,
                     input_image_path: Optional[str] = None,
                     output_filename: str = "result.png") -> Dict[str, Any]:
        """
        执行生成的代码

        Args:
            code: 要执行的 Python 代码
            input_image_path: 可选的输入图片路径
            output_filename: 输出文件名

        Returns:
            执行结果字典
        """
        output_path = os.path.join(self.output_dir, output_filename)

        # 准备执行环境
        env = {
            '__builtins__': __builtins__,
            'cv2': self.cv2,
            'Image': self.Image,
            'np': self.np,
            'input_image_path': input_image_path,
            'output_path': output_path,
            'os': os,
            'io': io,
        }

        # 添加常用导入
        if self.cv2:
            env['cv'] = self.cv2
        if self.Image:
            env['PIL'] = self.Image

        execution_log = []
        success = False
        error_message = None

        try:
            execution_log.append("开始执行代码...")

            # 如果提供了输入图片，加载它
            if input_image_path and os.path.exists(input_image_path):
                execution_log.append(f"加载输入图片：{input_image_path}")
                if self.cv2:
                    env['input_image'] = self.cv2.imread(input_image_path)
                if self.Image:
                    env['input_image_pil'] = self.Image.open(input_image_path)

            # 执行代码
            execution_log.append("执行算法代码...")
            exec(code, env)

            # 检查是否生成了输出图片
            if os.path.exists(output_path):
                success = True
                execution_log.append(f"成功生成输出图片：{output_path}")
            else:
                # 尝试从环境变量中获取生成的图片
                if 'output_image' in env:
                    output_img = env['output_image']
                    if isinstance(output_img, Image.Image):
                        output_img.save(output_path)
                        success = True
                        execution_log.append(f"成功保存输出图片：{output_path}")
                    elif self.np is not None and isinstance(output_img, self.np.ndarray):
                        if self.Image:
                            pil_img = self.Image.fromarray(output_img)
                            pil_img.save(output_path)
                            success = True
                            execution_log.append(f"成功保存输出图片：{output_path}")
                        else:
                            if self.cv2:
                                self.cv2.imwrite(output_path, output_img)
                                success = True
                                execution_log.append(f"成功保存输出图片：{output_path}")

            execution_log.append("代码执行完成")

        except Exception as e:
            success = False
            error_message = str(e)
            error_traceback = traceback.format_exc()
            execution_log.append(f"执行出错：{error_message}")
            execution_log.append(f"堆栈跟踪:\n{error_traceback}")
            print(f"[ExecutionAgent] Error executing code: {e}")

            # 错误分类，供自动修复逻辑使用
            exc_type = type(e).__name__.lower()
            if 'importerror' in exc_type or 'module' in error_message.lower():
                error_type = 'import_error'
            elif 'syntaxerror' in exc_type or 'invalid syntax' in error_message.lower():
                error_type = 'syntax_error'
            elif 'nameerror' in exc_type:
                error_type = 'name_error'
            elif 'attributeerror' in exc_type:
                error_type = 'attribute_error'
            elif 'typeerror' in exc_type:
                error_type = 'type_error'
            else:
                error_type = 'runtime_error'

        return {
            "success": success,
            "output_path": output_path if success else None,
            "output_path_raw": output_path,
            "execution_log": "\n".join(execution_log),
            "error": error_message,
            "error_type": locals().get('error_type', None),
            "error_traceback": locals().get('error_traceback', None)
        }

    def summarize_execution(self,
                            execution_result: Dict[str, Any],
                            previous_steps: list) -> str:
        """
        总结执行过程

        Args:
            execution_result: 执行结果
            previous_steps: 之前的步骤列表

        Returns:
            总结文本
        """
        summary_parts = ["## 执行总结\n"]

        # 添加前序步骤
        if previous_steps:
            summary_parts.append("### 前序操作链路")
            for i, step in enumerate(previous_steps, 1):
                summary_parts.append(f"{i}. {step}")
            summary_parts.append("")

        # 添加执行结果
        summary_parts.append("### 执行结果")
        summary_parts.append(execution_result.get('execution_log', '无日志'))

        if execution_result.get('success'):
            summary_parts.append(
                f"\n✅ 执行成功！输出图片：{execution_result.get('output_path')}")
        else:
            summary_parts.append(f"\n❌ 执行失败：{execution_result.get('error')}")

        return "\n".join(summary_parts)
