"""
评估 Agent: 调用多模态大模型以及结合外部知识，对生成的图片质量做出评价
"""

import os
import re
import base64
from typing import Optional, Dict, Any
from openai import OpenAI


class EvaluationAgent:
    """评估 Agent，负责评估生成图片的质量"""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        # 使用经过测试可用的免费模型 (主模型)
        self.model_text = os.getenv("OPENROUTER_MODEL")
        # 多模态模型 - 如果不可用会回退到文本模型进行评估
        self.model_multimodal = os.getenv("OPENROUTER_IMAGE_MODEL")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        self.system_context = """
你是一个专业的图像质量评估专家。你需要对生成的图片进行客观、全面的评估。

评估维度:
1. 技术质量：清晰度、色彩还原、噪点控制等（1-10分）
2. 内容匹配度：是否符合用户的原始需求（1-10分）
3. 艺术效果：美感、创意性等（1-10分）
4. 处理效果：算法处理是否到位，有无明显瑕疵（1-10分）

评估时必须优先对齐用户的原始任务目标。比如用户要求高斯模糊时，细节变模糊本身不是缺陷；
用户要求锐化时，边缘增强才是正向信号。不要用通用清晰度指标反向惩罚目标效果。
对于“边缘检测后与原图拼合/叠加”类任务，需要检查非边缘区域是否仍保留原图亮度和色彩。
如果结果因为全局混合黑底边缘图而整体变灰或变暗，应明确指出这是拼合策略问题，并建议使用边缘 mask 局部叠加。

**重要**：请严格按以下格式返回评估结果，第一行必须包含机器可解析的评分标识：

SCORE: X/10

## 总体评分：X/10

## 维度评分
- 技术质量：X/10
- 内容匹配度：X/10
- 艺术效果：X/10
- 处理效果：X/10

## 主要优点
列出3个主要优点

## 需要改进的方面
列出3个主要改进方面，并提供可直接指导代码修改的具体建议

## 整体评语
一句话总结整体质量
"""

    def _encode_image(self, image_path: str) -> str:
        """将图片编码为 base64"""
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        return image_data

    def _extract_score(self, text: str) -> int:
        """从评估文本中提取总体评分 (0-10)，多模式回退"""
        patterns = [
            # 机器可解析格式: SCORE: X/10
            r'SCORE[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            # 中文格式: 总体评分：X/10
            r'总体评分[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            # 英文格式: Overall Score: X/10 或 Score: X/10
            r'(?:Overall\s+)?Score[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            # 综合评分：X/10
            r'综合评分[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            # labeled score patterns
            r'(?:得分|评分|score)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*/?\s*10',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    return min(10, max(0, int(round(score))))
                except (ValueError, IndexError):
                    continue

        # 回退: 尝试维度评分计算平均分
        dimension_scores = self._extract_dimension_scores(text)
        if dimension_scores:
            avg = sum(dimension_scores) / len(dimension_scores)
            print(f"[EvaluationAgent] No overall score found, using dimension average: {avg:.1f}/10")
            return min(10, max(0, int(round(avg))))

        # 最终回退: 搜索所有 X/10 模式取最后一个
        matches = re.findall(r'(\d+(?:\.\d+)?)\s*/?\s*10', text)
        if matches:
            try:
                return min(10, max(0, int(round(float(matches[-1])))))
            except (ValueError, IndexError):
                pass

        print("[EvaluationAgent] WARNING: Could not extract any score from evaluation text, defaulting to 5")
        return 5

    def _extract_dimension_scores(self, text: str) -> list:
        """从评估文本中提取各维度评分，用于回退计算总体分"""
        dimension_patterns = [
            r'技术质量[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            r'内容匹配度[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            r'艺术效果[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            r'处理效果[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            r'正确性[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            r'可读性[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
            r'效率[:：]\s*(\d+(?:\.\d+)?)\s*/?\s*10',
        ]
        scores = []
        for pattern in dimension_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                try:
                    s = float(m)
                    if 0 <= s <= 10:
                        scores.append(s)
                except (ValueError, TypeError):
                    continue
        return scores

    def _extract_improvements(self, text: str) -> str:
        """从评估文本中提取改进建议，多模式回退"""
        header_patterns = [
            r'需要改进的方面',
            r'改进建议',
            r'可改进之处',
            r'改进方向',
            r'建议改进',
            r'优化建议',
        ]
        stop_headers = [
            r'总体评分', r'维度评分', r'主要优点', r'整体评语',
            r'Score', r'Strengths', r'Summary',
            r'结论', r'总结',
        ]

        for header in header_patterns:
            stop_alt = '|'.join(stop_headers)
            pattern = (
                r'(?:^|\n)\s*(?:#{1,6}\s*)?(?:' + header + r')\s*[:：]?\s*'
                r'(.*?)'
                r'(?=\n\s*(?:#{1,6}\s*)?(?:' + stop_alt + r')\s*[:：]?|\Z)'
            )
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                improvements = match.group(1).strip()
                if len(improvements) > 50:
                    if len(improvements) > 1000:
                        improvements = improvements[:1000] + "..."
                    return improvements

        # 回退: 找所有列表项作为潜在改进建议
        list_items = re.findall(
            r'(?:^|\n)\s*(?:[-*]\s+|\d+[.)]\s+)(.*?)(?=\n\s*(?:[-*]\s+|\d+[.)]\s+|$))',
            text, re.DOTALL
        )
        if list_items and len(list_items) >= 2:
            improvements = '\n'.join(
                f'- {item.strip()[:200]}' for item in list_items[:6])
            if len(improvements) > 50:
                return improvements

        return ""

    def evaluate_image(self,
                       image_path: str,
                       user_request: str,
                       algorithm_code: Optional[str] = None,
                       search_results: Optional[str] = None) -> Dict[str, Any]:
        """
        评估图片质量

        Args:
            image_path: 图片路径
            user_request: 用户原始需求
            algorithm_code: 可选的算法代码
            search_results: 可选的搜索结果

        Returns:
            评估结果字典
        """
        try:
            # 构建评估 prompt
            prompt_parts = [f"用户需求：{user_request}"]

            if algorithm_code:
                prompt_parts.append(f"使用的算法代码:\n{algorithm_code}")

            if search_results:
                prompt_parts.append(f"参考信息:\n{search_results}")

            prompt_parts.append(
                "请对这张生成的图片进行全面评估。评分和改进建议必须以用户需求为首要标准，"
                "并在“需要改进的方面”中给出可直接指导下一轮代码修改的具体建议。")

            full_prompt = "\n\n".join(prompt_parts)

            # 尝试使用多模态模型 (带图片)
            try:
                # 编码图片
                image_base64 = self._encode_image(image_path)

                response = self.client.chat.completions.create(
                    model=self.model_multimodal,
                    messages=[
                        {"role": "system", "content": self.system_context},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": full_prompt},
                                {"type": "image_url", "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"}}
                            ]
                        }
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )

                # 检查是否支持图像输入
                if isinstance(response, str) and 'No endpoints found that support image input' in response:
                    raise ValueError("Model does not support image input")

            except Exception as multimodal_error:
                # 如果多模态失败，回退到纯文本评估 (只评估代码)
                print(
                    f"[EvaluationAgent] 多模态评估失败 ({multimodal_error}), 回退到代码评估...")
                return self.evaluate_code(
                    code=algorithm_code or "",
                    user_request=user_request,
                    search_results=search_results
                )

            # Check if response is a string (error case) or has choices attribute
            if isinstance(response, str):
                error_msg = f"API returned a string instead of response object: {response[:200]}"
                print(f"[EvaluationAgent] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "evaluation_text": f"评估失败：{error_msg}"
                }

            if not hasattr(response, 'choices') or not response.choices:
                error_msg = f"API response has no choices attribute: {type(response)}"
                print(f"[EvaluationAgent] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "evaluation_text": f"评估失败：{error_msg}"
                }

            evaluation_text = response.choices[0].message.content

            # 提取结构化评分和改进建议
            score = self._extract_score(evaluation_text)
            improvements = self._extract_improvements(evaluation_text)

            print(
                f"[EvaluationAgent] Evaluation completed - Score: {score}/10")

            return {
                "success": True,
                "score": score,
                "evaluation_text": evaluation_text,
                "improvements": improvements,
                "image_path": image_path
            }

        except Exception as e:
            print(f"[EvaluationAgent] Error evaluating image: {e}")
            # 最后回退方案：只评估代码
            return self.evaluate_code(
                code=algorithm_code or "",
                user_request=user_request,
                search_results=search_results
            )

    def evaluate_code(self,
                      code: str,
                      user_request: str,
                      search_results: Optional[str] = None) -> Dict[str, Any]:
        """
        评估代码质量（不依赖图片）

        Args:
            code: 生成的代码
            user_request: 用户原始需求
            search_results: 可选的搜索结果

        Returns:
            评估结果字典
        """
        try:
            prompt_parts = [
                f"用户需求：{user_request}",
                f"生成的代码:\n{code}"
            ]

            if search_results:
                prompt_parts.append(f"参考信息:\n{search_results}")

            prompt_parts.append(
                "请评估这段代码的质量，包括正确性、可读性、效率等方面。"
                "请在“需要改进的方面”中给出可直接指导下一轮代码修改的具体建议。")

            full_prompt = "\n\n".join(prompt_parts)

            response = self.client.chat.completions.create(
                model=self.model_text,
                messages=[
                    {"role": "system", "content": (
                        "你是一个专业的代码审查专家。请严格按以下格式返回评估结果，第一行必须包含 SCORE: X/10。\n\n"
                        "SCORE: X/10\n\n"
                        "## 总体评分：X/10\n\n"
                        "## 维度评分\n"
                        "- 正确性：X/10\n"
                        "- 可读性：X/10\n"
                        "- 效率：X/10\n\n"
                        "## 主要优点\n"
                        "列出2-3个主要优点\n\n"
                        "## 需要改进的方面\n"
                        "列出2-3个主要改进方面，并提供可直接指导代码修改的具体建议\n\n"
                        "## 整体评语\n"
                        "一句话总结"
                    )},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            # Check if response is a string (error case) or has choices attribute
            if isinstance(response, str):
                error_msg = f"API returned a string instead of response object: {response[:200]}"
                print(f"[EvaluationAgent] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "evaluation_text": f"代码评估失败：{error_msg}"
                }

            if not hasattr(response, 'choices') or not response.choices:
                error_msg = f"API response has no choices attribute: {type(response)}"
                print(f"[EvaluationAgent] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "evaluation_text": f"代码评估失败：{error_msg}"
                }

            # Handle models that put content in reasoning field
            message = response.choices[0].message
            evaluation_text = message.content

            # Some models (like nvidia/nemotron) may put content in reasoning field
            if evaluation_text is None and hasattr(message, 'reasoning') and message.reasoning:
                evaluation_text = message.reasoning

            if evaluation_text is None:
                error_msg = f"API response has no content: {message}"
                print(f"[EvaluationAgent] {error_msg}")
                return {
                    "success": False,
                    "score": 0,
                    "error": error_msg,
                    "evaluation_text": f"代码评估失败：{error_msg}",
                    "improvements": ""
                }

            # 提取结构化评分和改进建议
            score = self._extract_score(evaluation_text)
            improvements = self._extract_improvements(evaluation_text)

            print(
                f"[EvaluationAgent] Code evaluation completed - Score: {score}/10")

            return {
                "success": True,
                "score": score,
                "evaluation_text": evaluation_text,
                "improvements": improvements
            }

        except Exception as e:
            print(f"[EvaluationAgent] Error evaluating code: {e}")
            return {
                "success": False,
                "score": 0,
                "error": str(e),
                "evaluation_text": f"代码评估失败：{str(e)}",
                "improvements": ""
            }

    # ── Stage 4: 轻量级前置评估 ─────────────────────────────

    def pre_evaluate_code(self, code: str, user_request: str) -> Dict[str, Any]:
        """
        快速预评估代码（不执行），秒级完成。

        检查:
        - Python 语法正确性 (compile)
        - 必要的变量使用 (input_image_path, output_path)
        - 常用库导入 (cv2, PIL, numpy)
        - 输出保存逻辑

        Returns:
            {
                "quick_score": float 0-10,
                "issues": [str],
                "suggestion": str,
                "should_revise": bool,
                "checks": dict
            }
        """
        issues = []
        checks = {
            "syntax_ok": True,
            "has_input_var": False,
            "has_output_var": False,
            "has_output_save": False,
            "has_imports": False,
        }

        # 1. 语法检查
        try:
            compile(code, "<generated_code>", "exec")
        except SyntaxError as e:
            checks["syntax_ok"] = False
            issues.append(f"语法错误: {e}")

        # 2. 变量检查
        if "input_image_path" in code:
            checks["has_input_var"] = True
        else:
            issues.append("未使用 input_image_path 变量读取输入图片")

        if "output_path" in code:
            checks["has_output_var"] = True
        else:
            issues.append("未使用 output_path 变量保存输出图片")

        # 3. 输出保存逻辑
        save_patterns = [".save(", "cv2.imwrite(", "imwrite("]
        if any(p in code for p in save_patterns):
            checks["has_output_save"] = True
        else:
            issues.append("未检测到图片保存逻辑 (.save / cv2.imwrite)")

        # 4. 导入检查
        import_keywords = ["import cv2", "import cv ", "from PIL",
                           "import PIL", "import numpy", "from numpy"]
        if any(kw in code for kw in import_keywords):
            checks["has_imports"] = True
        else:
            issues.append("未检测到图像处理库导入 (cv2/PIL/numpy)")

        # 5. 计算快速评分
        total_checks = len(checks)
        passed = sum(1 for v in checks.values() if v)
        base_score = (passed / total_checks) * 10

        # 严重问题扣分
        if not checks["syntax_ok"]:
            base_score = min(base_score, 3)
        if not checks["has_output_save"]:
            base_score = min(base_score, 4)

        quick_score = round(base_score, 1)

        should_revise = quick_score < 4 or len(issues) >= 2

        suggestion = ""
        if issues:
            suggestion = "；".join(issues)
            suggestion += "。建议修改后再执行。"

        print(
            f"[EvaluationAgent] Pre-evaluation: score={quick_score}/10, "
            f"issues={len(issues)}, should_revise={should_revise}"
        )

        return {
            "quick_score": quick_score,
            "issues": issues,
            "suggestion": suggestion,
            "should_revise": should_revise,
            "checks": checks,
        }
