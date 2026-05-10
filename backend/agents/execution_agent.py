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
                     output_filename: str = "result.png",
                     output_dir: Optional[str] = None,
                     work_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        执行生成的代码

        Args:
            code: 要执行的 Python 代码
            input_image_path: 可选的输入图片路径
            output_filename: 输出文件名
            output_dir: 可选的会话输出目录
            work_dir: 可选的会话代码工作目录

        Returns:
            执行结果字典
        """
        active_output_dir = output_dir or self.output_dir
        os.makedirs(active_output_dir, exist_ok=True)
        if work_dir:
            os.makedirs(work_dir, exist_ok=True)
        output_path = os.path.abspath(
            os.path.join(active_output_dir, output_filename))
        if input_image_path:
            input_image_path = os.path.abspath(input_image_path)

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
        error_type = None
        error_context = {}
        repair_suggestion = {}

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
            previous_cwd = os.getcwd()
            try:
                if work_dir:
                    os.chdir(work_dir)
                    execution_log.append(f"使用会话工作区：{work_dir}")
                exec(code, env)
            finally:
                os.chdir(previous_cwd)

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

            # 详细的错误诊断和分类，为自动修复提供上下文
            error_info = self._diagnose_error(e, error_traceback, code)
            error_type = error_info["error_type"]
            error_context = error_info["context"]
            repair_suggestion = error_info["repair_suggestion"]

        return {
            "success": success,
            "output_path": output_path if success else None,
            "output_path_raw": output_path,
            "execution_log": "\n".join(execution_log),
            "error": error_message,
            "error_type": error_type,
            "error_traceback": locals().get('error_traceback', None),
            "error_context": error_context,
            "repair_suggestion": repair_suggestion
        }

    def _diagnose_error(self,
                        exception: Exception,
                        error_traceback: str,
                        code: str) -> Dict[str, Any]:
        """
        诊断执行错误，提供详细分类和修复建议

        Args:
            exception: 异常对象
            error_traceback: 堆栈追踪
            code: 执行的代码

        Returns:
            包含错误诊断信息的字典
        """
        error_message = str(exception)
        exc_type = type(exception).__name__

        # 初始化诊断信息
        error_type = "runtime_error"
        context = {
            "exception_type": exc_type,
            "error_message": error_message,
            "affected_line": None,
            "missing_import": None,
            "undefined_name": None
        }
        repair_suggestion = {
            "strategy": "retry",
            "hints": []
        }

        # 导入错误诊断
        if exc_type == "ModuleNotFoundError" or exc_type == "ImportError":
            error_type = "import_error"
            repair_suggestion["strategy"] = "add_import"

            # 提取缺失的模块名
            import re
            match = re.search(
                r"No module named ['\"]?([^'\"]+)['\"]?", error_message)
            if match:
                missing_module = match.group(1)
                context["missing_import"] = missing_module
                repair_suggestion["hints"].append(
                    f"缺失模块: {missing_module}. 请添加导入: import {missing_module.split('.')[0]}"
                )

        # 名称错误诊断
        elif exc_type == "NameError":
            error_type = "name_error"
            import re
            match = re.search(r"name '([^']+)' is not defined", error_message)
            if match:
                undefined_name = match.group(1)
                context["undefined_name"] = undefined_name
                repair_suggestion["hints"].append(
                    f"未定义的变量或函数: {undefined_name}"
                )
                # 检查是否是常见的库别名问题
                if undefined_name in ["cv2", "np", "pd", "plt"]:
                    repair_suggestion["hints"].append(
                        f"请确保导入了 {undefined_name} 库"
                    )

        # 属性错误诊断
        elif exc_type == "AttributeError":
            error_type = "attribute_error"
            import re
            match = re.search(
                r"module '([^']+)' has no attribute '([^']+)'", error_message)
            if match:
                module_name = match.group(1)
                attr_name = match.group(2)
                repair_suggestion["hints"].append(
                    f"模块 {module_name} 没有属性 {attr_name}. 请检查拼写或使用的库版本"
                )

        # 类型错误诊断
        elif exc_type == "TypeError":
            error_type = "type_error"
            repair_suggestion["hints"].append(
                "类型不匹配。请检查函数参数类型是否正确"
            )

        # 文件/IO错误诊断
        elif exc_type == "FileNotFoundError" or exc_type == "IOError":
            error_type = "file_error"
            repair_suggestion["hints"].append(
                "文件不存在或路径错误。请确保输入图片路径正确"
            )

        # 语法错误（通常不会在exec时出现，但保留以防万一）
        elif exc_type == "SyntaxError":
            error_type = "syntax_error"
            repair_suggestion["strategy"] = "fix_syntax"
            repair_suggestion["hints"].append(
                "代码语法错误。请检查括号、引号等是否匹配"
            )

        # 通用运行时错误
        else:
            error_type = "runtime_error"
            repair_suggestion["hints"].append(
                "运行时错误。请检查代码逻辑和输入数据"
            )

        # 尝试从堆栈追踪中提取出错行信息
        if "line" in error_traceback.lower():
            import re
            match = re.search(r'line (\d+)', error_traceback)
            if match:
                context["affected_line"] = int(match.group(1))

        return {
            "error_type": error_type,
            "context": context,
            "repair_suggestion": repair_suggestion
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
