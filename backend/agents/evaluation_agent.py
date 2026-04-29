"""
评估 Agent: 调用多模态大模型以及结合外部知识，对生成的图片质量做出评价
"""

import os
import base64
from typing import Optional, Dict, Any
from openai import OpenAI


class EvaluationAgent:
    """评估 Agent，负责评估生成图片的质量"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        self.system_context = """
你是一个专业的图像质量评估专家。你需要对生成的图片进行客观、全面的评估。

评估维度:
1. 技术质量：清晰度、色彩还原、噪点控制等
2. 内容匹配度：是否符合用户的原始需求
3. 艺术效果：美感、创意性等
4. 处理效果：算法处理是否到位，有无明显瑕疵

请给出详细的评语和各项评分 (1-10 分)。
"""
    
    def _encode_image(self, image_path: str) -> str:
        """将图片编码为 base64"""
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        return image_data
    
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
            # 编码图片
            image_base64 = self._encode_image(image_path)
            
            # 构建评估 prompt
            prompt_parts = [f"用户需求：{user_request}"]
            
            if algorithm_code:
                prompt_parts.append(f"使用的算法代码:\n{algorithm_code}")
            
            if search_results:
                prompt_parts.append(f"参考信息:\n{search_results}")
            
            prompt_parts.append("请对这张生成的图片进行全面评估，包括技术质量、内容匹配度、艺术效果等方面。")
            
            full_prompt = "\n\n".join(prompt_parts)
            
            # 调用多模态模型
            response = self.client.chat.completions.create(
                model="openai/gpt-4o",  # GPT-4o 支持多模态
                messages=[
                    {"role": "system", "content": self.system_context},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": full_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            evaluation_text = response.choices[0].message.content
            
            print("[EvaluationAgent] Evaluation completed")
            
            return {
                "success": True,
                "evaluation_text": evaluation_text,
                "image_path": image_path
            }
            
        except Exception as e:
            print(f"[EvaluationAgent] Error evaluating image: {e}")
            return {
                "success": False,
                "error": str(e),
                "evaluation_text": f"评估失败：{str(e)}"
            }
    
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
            
            prompt_parts.append("请评估这段代码的质量，包括正确性、可读性、效率等方面。")
            
            full_prompt = "\n\n".join(prompt_parts)
            
            response = self.client.chat.completions.create(
                model="openai/gpt-4o",
                messages=[
                    {"role": "system", "content": "你是一个专业的代码审查专家。"},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            evaluation_text = response.choices[0].message.content
            
            print("[EvaluationAgent] Code evaluation completed")
            
            return {
                "success": True,
                "evaluation_text": evaluation_text
            }
            
        except Exception as e:
            print(f"[EvaluationAgent] Error evaluating code: {e}")
            return {
                "success": False,
                "error": str(e),
                "evaluation_text": f"代码评估失败：{str(e)}"
            }
