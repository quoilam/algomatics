"""
TaskParser: 将用户自然语言需求解析为结构化任务表示。

职责:
- 识别任务类型 (simple/medium/complex)
- 提取关键词和约束条件
- 输出置信度，低置信度时触发保守策略

TaskParser 是 Controller 的决策输入，不是独立的 Agent。
"""

import os
import json
import re
from typing import Dict, Any, List
from openai import OpenAI


class TaskParser:
    """任务解析器，将自然语言需求映射到结构化的任务类型和约束"""

    # 基于关键词的启发式回退规则
    SIMPLE_KEYWORDS = [
        "裁剪", "crop", "缩放", "resize", "旋转", "rotate",
        "灰度", "grayscale", "翻转", "flip", "镜像", "mirror",
        "二值化", "threshold", "格式转换", "format convert",
        "尺寸", "dimension", "通道转换", "channel",
    ]
    MEDIUM_KEYWORDS = [
        "降噪", "denoise", "锐化", "sharpen", "增强", "enhance",
        "模糊", "blur", "边缘检测", "edge detect", "直方图", "histogram",
        "均衡化", "equalize", "形态学", "morphology", "膨胀", "腐蚀",
        "色彩校正", "color correct", "对比度", "contrast", "亮度", "brightness",
        "平滑", "smooth", "滤波", "filter", "高斯", "gaussian",
    ]
    COMPLEX_KEYWORDS = [
        "风格迁移", "style transfer", "超分辨率", "super resolution",
        "去水印", "watermark", "水印",
        "分割", "segmentation",
        "目标检测", "object detection", "修复", "inpainting",
        "多步骤", "multi-step", "组合", "composition",
        "深度学习", "deep learning", "神经网络", "neural network",
        "生成", "generation", "合成", "synthesis",
        "去雾", "dehaze", "去噪(深度学习)", "超分", "高清化",
    ]
    SPEED_KEYWORDS = ["快速", "fast", "quick", "尽快", "立即", "马上"]

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = os.getenv("OPENROUTER_MODEL")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        self._system_prompt = (
            "你是一个图像处理任务分类专家。分析用户需求并返回一个 JSON 对象。\n\n"
            "任务类型定义:\n"
            "- simple: 基础变换操作（裁剪、缩放、旋转、灰度、翻转、二值化、格式转换、通道操作）\n"
            "- medium: 常见图像处理（降噪、锐化、增强、模糊、边缘检测、直方图均衡、色彩校正、对比度调整、滤波）\n"
            "- complex: 高级任务（风格迁移、超分辨率、去水印、分割、目标检测、修复inpainting、多步骤组合操作、深度学习相关）\n\n"
            "约束识别:\n"
            "- speed: 用户要求快速处理\n"
            "- quality: 用户要求高质量/最佳效果\n"
            "- none: 无特殊约束\n\n"
            "返回格式（仅 JSON，不要其他文字）:\n"
            '{"task_type": "simple|medium|complex", "keywords": ["提取的关键词"], '
            '"constraint": "speed|quality|none", "confidence": 0.0-1.0, '
            '"explanation": "一句话解释分类原因"}'
        )

    def parse(self, user_request: str, has_input_image: bool = True) -> Dict[str, Any]:
        """
        解析用户请求，返回结构化任务表示。

        Returns:
            {
                "task_type": str,     # simple / medium / complex
                "keywords": [str],
                "constraint": str,    # speed / quality / none
                "confidence": float,  # 0.0-1.0
                "explanation": str,
                "source": str,        # "llm" or "heuristic"
            }
        """
        # 先用启发式检测 speed 约束（不依赖 LLM）
        heuristic_speed = self._detect_speed(user_request)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": f"用户需求: {user_request}"},
                ],
                temperature=0.2,
                max_tokens=300,
            )

            if isinstance(response, str):
                raise ValueError(f"API returned string: {response[:200]}")

            if not hasattr(response, 'choices') or not response.choices:
                raise ValueError(f"Invalid response: {type(response)}")

            message = response.choices[0].message
            raw = message.content or getattr(message, 'reasoning', '') or ""

            result = self._parse_json(raw)
            if result:
                result["source"] = "llm"
                # 启发式 speed 检测覆盖 LLM 判断
                if heuristic_speed and result.get("constraint") != "speed":
                    result["constraint"] = "speed"
                return self._validate(result, user_request)

        except Exception as e:
            print(f"[TaskParser] LLM classification failed: {e}, falling back to heuristic")

        # 回退到关键词启发式
        return self._heuristic_classify(user_request, heuristic_speed)

    def _parse_json(self, raw: str) -> dict | None:
        """从 LLM 输出中提取 JSON 对象"""
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        match = re.search(r'\{[^}]+\}', raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None

    def _detect_speed(self, text: str) -> bool:
        """检测用户是否有快速处理的需求"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.SPEED_KEYWORDS)

    def _validate(self, parsed: dict, user_request: str) -> Dict[str, Any]:
        """校验和规范化解析结果"""
        task_type = parsed.get("task_type", "medium")
        if task_type not in ("simple", "medium", "complex"):
            task_type = "medium"

        keywords = parsed.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []

        constraint = parsed.get("constraint", "none")
        if constraint not in ("speed", "quality", "none"):
            constraint = "none"

        confidence = float(parsed.get("confidence", 0.5))
        confidence = min(1.0, max(0.0, confidence))

        return {
            "task_type": task_type,
            "keywords": keywords,
            "constraint": constraint,
            "confidence": confidence,
            "explanation": parsed.get("explanation", f"分类为 {task_type} 任务"),
            "source": parsed.get("source", "llm"),
        }

    def _heuristic_classify(self, user_request: str, speed_detected: bool = False) -> Dict[str, Any]:
        """基于关键词的启发式分类，作为 LLM 调用失败时的回退"""
        text_lower = user_request.lower()
        constraint = "speed" if speed_detected else "none"

        # 复杂关键词匹配
        complex_matches = [kw for kw in self.COMPLEX_KEYWORDS if kw in text_lower]
        if complex_matches:
            return {
                "task_type": "complex",
                "keywords": complex_matches,
                "constraint": constraint,
                "confidence": 0.5,
                "explanation": f"检测到复杂任务关键词: {complex_matches}",
                "source": "heuristic",
            }

        # 简单关键词匹配
        simple_matches = [kw for kw in self.SIMPLE_KEYWORDS if kw in text_lower]
        medium_matches = [kw for kw in self.MEDIUM_KEYWORDS if kw in text_lower]

        if simple_matches and not medium_matches:
            return {
                "task_type": "simple",
                "keywords": simple_matches,
                "constraint": constraint,
                "confidence": 0.6,
                "explanation": f"检测到简单任务关键词: {simple_matches}",
                "source": "heuristic",
            }

        if medium_matches:
            return {
                "task_type": "medium",
                "keywords": medium_matches,
                "constraint": constraint,
                "confidence": 0.55,
                "explanation": f"检测到中等任务关键词: {medium_matches}",
                "source": "heuristic",
            }

        # 默认：无关键词匹配，保守处理
        return {
            "task_type": "medium",
            "keywords": [],
            "constraint": constraint,
            "confidence": 0.3,
            "explanation": "无法从关键词判断任务类型，采用保守策略",
            "source": "heuristic",
        }
