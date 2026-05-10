"""
检索 Agent: 一个真正的 LLM agent，通过规划搜索策略、执行多路检索、综合提取信息，
为下游代码生成提供高质量的领域知识参考。

Agentic 能力体现:
- 查询规划: 根据用户任务用 LLM 生成多角度搜索词（而非固定模板拼接）
- 结果综合: 用 LLM 从原始搜索结果中提取算法要点、代码片段、关键注意事项
- 质量自评: 对综合结果做自我评估，质量低时主动告知 Controller 降低依赖
"""

import os
import json
import hashlib
import time
from typing import Optional, List, Dict, Any
from tavily import TavilyClient
from openai import OpenAI


class RetrievalAgent:
    """检索 Agent，具备查询规划与结果综合能力的 agentic 搜索"""

    def __init__(self):
        # Tavily 搜索客户端
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY environment variable is required")
        self.tavily = TavilyClient(api_key=self.tavily_api_key)

        # LLM 客户端（和项目其他 agent 一致，使用 OpenRouter）
        self.llm_api_key = os.getenv("OPENROUTER_API_KEY")
        self.llm_base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.llm_model = os.getenv(
            "OPENROUTER_MODEL", "inclusionai/ling-2.6-1t:free")
        if not self.llm_api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")
        self.llm = OpenAI(
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
        )

        # 缓存：存储原始结构化结果，带时间戳用于 TTL
        self.cache_file = "search_cache.json"
        self.cache_ttl_seconds = 3600  # 1 小时 TTL，demo 场景足够
        self.cache = self._load_cache()

    # ── 缓存管理 ─────────────────────────────────────────────

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _cache_key(self, query: str) -> str:
        normalized = " ".join(query.strip().lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _cache_get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        entry = self.cache.get(key)
        if not entry:
            return None
        if time.time() - entry.get("ts", 0) > self.cache_ttl_seconds:
            del self.cache[key]
            self._save_cache()
            return None
        return entry.get("data")

    def _cache_set(self, key: str, data: List[Dict[str, Any]]):
        self.cache[key] = {"ts": time.time(), "data": data}
        self._save_cache()

    # ── LLM 调用辅助 ─────────────────────────────────────────

    def _llm_chat(self, system: str, user: str, temperature: float = 0.3,
                  max_tokens: int = 2000) -> str:
        """调用 LLM，返回文本内容"""
        try:
            resp = self.llm.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if isinstance(resp, str):
                return resp
            msg = resp.choices[0].message
            return msg.content or getattr(msg, 'reasoning', '') or ""
        except Exception as e:
            print(f"[RetrievalAgent] LLM call failed: {e}")
            return ""

    # ── 文本清洗 ─────────────────────────────────────────────

    @staticmethod
    def _clean_text(text: str) -> str:
        if not isinstance(text, str):
            return str(text)
        return text.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')

    # ── 单次搜索（带缓存） ───────────────────────────────────

    def _search_single(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """执行单次 Tavily 搜索，带缓存。返回结构化结果列表。"""
        key = self._cache_key(query)
        cached = self._cache_get(key)
        if cached is not None:
            print(f"[RetrievalAgent] Cache hit for: {query}")
            return cached

        try:
            print(f"[RetrievalAgent] Searching: {query}")
            resp = self.tavily.search(
                query,
                search_depth="advanced",
                max_results=max_results,
                include_answer=True,
            )
        except Exception as e:
            print(f"[RetrievalAgent] Search error for '{query}': {e}")
            return []

        results = []
        # Tavily 返回的 AI 答案
        if isinstance(resp, dict) and resp.get("answer"):
            results.append({
                "title": "AI-Generated Answer",
                "url": "",
                "content": self._clean_text(resp["answer"]),
            })

        items = []
        if isinstance(resp, dict) and 'results' in resp:
            items = resp['results']
        elif isinstance(resp, list):
            items = resp

        for item in items:
            results.append({
                "title": self._clean_text(item.get("title", "")),
                "url": item.get("url", ""),
                "content": self._clean_text(item.get("content", "")),
            })

        if results:
            self._cache_set(key, results)
        print(f"[RetrievalAgent] Got {len(results)} results for: {query}")
        return results

    # ── Agentic 查询规划 ─────────────────────────────────────

    def _plan_queries(self, user_request: str) -> List[str]:
        """
        用 LLM 分析用户需求，生成 2-3 个不同角度的搜索词。
        这是 agentic 行为的核心体现：agent 自主决策"搜什么"。
        """
        system = (
            "你是一个搜索策略规划专家。根据用户的图像处理任务描述，"
            "生成 2-3 个英文搜索查询，每个查询从不同角度切入，"
            "以获得更好、更全面的搜索结果。\n\n"
            "规则:\n"
            "- 查询使用英文（搜索效果更好）\n"
            "- 每行一个查询，不要编号、不要额外解释\n"
            "- 一个查询侧重算法原理，一个侧重 Python/OpenCV 实现，一个侧重最佳实践\n"
            "- 查询应简洁、具体、适合搜索引擎"
        )
        user = f"用户任务: {user_request}"
        raw = self._llm_chat(system, user, temperature=0.4, max_tokens=300)
        queries = [q.strip() for q in raw.strip().split('\n') if q.strip()]
        # 去掉可能的编号前缀如 "1. " "2. "
        import re
        queries = [re.sub(r'^[\d]+[\.\)]\s*', '', q) for q in queries]
        if not queries:
            # fallback: 至少用原始请求构造一个查询
            queries = [f"image processing {user_request} python opencv"]
        print(f"[RetrievalAgent] Planned queries: {queries}")
        return queries[:3]

    # ── Agentic 结果综合 ─────────────────────────────────────

    def _synthesize(self, user_request: str,
                    all_results: List[Dict[str, Any]]) -> str:
        """
        用 LLM 将多路搜索结果综合成一份"代码生成参考简报"。
        提炼算法思路、代码片段、注意事项，过滤无关信息。
        """
        if not all_results:
            return ""

        # 构建搜索结果摘要给 LLM
        results_text_parts = []
        total_len = 0
        max_input = 6000  # 控制输入长度，避免 token 浪费
        for i, r in enumerate(all_results, 1):
            chunk = f"[{i}] {r['title']}\n{r['content'][:400]}"
            if total_len + len(chunk) > max_input:
                break
            results_text_parts.append(chunk)
            total_len += len(chunk)
        results_text = "\n\n".join(results_text_parts)

        system = (
            "你是一个图像处理技术研究员。根据搜索结果，为代码生成 agent "
            "编写一份简明的参考简报，帮助生成高质量的 Python 图像处理代码。\n\n"
            "简报格式要求（使用中文）:\n"
            "## 推荐算法\n"
            "- 列出 1-3 个最相关的算法/技术，简要说明原理\n\n"
            "## 实现要点\n"
            "- 列出在 Python/OpenCV/PIL 中实现的关键步骤和注意事项\n\n"
            "## 代码片段参考\n"
            "- 如果搜索结果中包含代码片段，提取并适当简化（保留核心逻辑）\n\n"
            "## 潜在问题\n"
            "- 列出实现时可能遇到的坑或常见错误\n\n"
            "要求: 只写简报内容，不要写\"以下是根据搜索结果...\"之类的引导语。"
            "内容精简，每条不超过 3 行。如果搜索结果不相关或质量差，直接说明。"
        )
        user = (
            f"用户任务: {user_request}\n\n"
            f"搜索结果:\n{results_text}"
        )
        synthesized = self._llm_chat(system, user, temperature=0.3, max_tokens=1500)
        return synthesized.strip()

    # ── 质量自评 ─────────────────────────────────────────────

    def _assess_quality(self, user_request: str, synthesis: str) -> Dict[str, Any]:
        """
        Agent 自我评估搜索结果质量。
        返回 {"score": int 1-10, "verdict": str, "should_skip": bool}
        """
        if not synthesis:
            return {"score": 1, "verdict": "无搜索结果", "should_skip": True}

        system = (
            "你是一个信息质量评估专家。评估搜索资料对实现用户图像处理任务的帮助程度。\n"
            "返回一个 JSON 对象（仅 JSON，不要其他文字）:\n"
            '{"score": 整数1-10, "verdict": "一句话评价", "should_skip": true/false}\n\n'
            "评分标准:\n"
            "- 8-10: 资料高度相关，包含可落地的算法和代码\n"
            "- 5-7: 有一定参考价值，但缺少具体实现细节\n"
            "- 1-4: 内容不相关或质量低，不应作为代码生成依据\n"
            "should_skip 为 true 表示质量太低建议跳过这些搜索结果。"
        )
        user = f"用户任务: {user_request}\n\n综合简报:\n{synthesis[:2000]}"
        raw = self._llm_chat(system, user, temperature=0.1, max_tokens=200)
        try:
            # 尝试提取 JSON
            import re
            match = re.search(r'\{[^}]+\}', raw)
            if match:
                return json.loads(match.group())
        except (json.JSONDecodeError, AttributeError):
            pass
        return {"score": 5, "verdict": "无法评估", "should_skip": False}

    # ── 主入口: Agentic Research ─────────────────────────────

    def research(self, user_request: str,
                 input_image_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Agentic 研究流程:
        1. LLM 规划搜索查询
        2. 多路 Tavily 搜索（带缓存）
        3. LLM 综合提取关键信息
        4. 质量自评

        Returns:
            {
                "brief": str,           # 综合简报，可直接注入代码生成 prompt
                "quality_score": int,   # 1-10
                "quality_verdict": str,
                "should_skip": bool,     # 质量太低时建议跳过
                "queries_used": [str],  # 实际使用的搜索词
                "total_results": int,   # 原始搜索结果总数
            }
        """
        print(f"[RetrievalAgent] Agentic research for: {user_request[:100]}")

        # Step 1: 查询规划（LLM 自主决策搜什么）
        queries = self._plan_queries(user_request)

        # Step 2: 执行多路搜索
        all_results = []
        for q in queries:
            results = self._search_single(q, max_results=4)
            all_results.extend(results)

        print(f"[RetrievalAgent] Total raw results: {len(all_results)}")

        # Step 3: 综合提取（LLM 从原始结果提炼知识）
        brief = self._synthesize(user_request, all_results)

        # Step 4: 质量自评（Agent 自我判断结果是否有用）
        quality = self._assess_quality(user_request, brief)

        return {
            "brief": brief,
            "quality_score": quality["score"],
            "quality_verdict": quality["verdict"],
            "should_skip": quality["should_skip"],
            "queries_used": queries,
            "total_results": len(all_results),
        }
