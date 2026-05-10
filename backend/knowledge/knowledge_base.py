"""
知识库 — Stage 5 MVP。

从历史案例中学习，提供:
- 问题模式存储与匹配（关键词相似度）
- 最佳实践记录（算法方案 + 评分 + 成功率）
- 反馈驱动的权重更新
- 时间衰减遗忘机制

设计原则: 轻量级 JSON 存储，避免过度工程化。
"""

import os
import json
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime


class KnowledgeBase:
    """轻量级知识库，存储问题模式和成功方案"""

    def __init__(self, storage_path: str = "knowledge_base.json"):
        self.storage_path = storage_path
        self.data: Dict[str, Any] = self._load()

    # ── 持久化 ────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"problems": {}, "stats": {"total_recorded": 0, "total_queries": 0}}

    def _save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ── 问题 ID 生成 ──────────────────────────────────────────

    @staticmethod
    def _problem_id(user_request: str) -> str:
        normalized = " ".join(user_request.strip().lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:12]

    # ── 关键词提取 ────────────────────────────────────────────

    @staticmethod
    def _extract_keywords(user_request: str) -> List[str]:
        """从用户请求中提取关键词，用于相似度匹配"""
        # 中文+英文混合关键词库
        keyword_candidates = [
            # 操作类型
            "降噪", "denoise", "去噪",
            "锐化", "sharpen", "增强", "enhance",
            "模糊", "blur", "gaussian",
            "边缘检测", "edge detect", "canny",
            "裁剪", "crop", "缩放", "resize", "旋转", "rotate",
            "灰度", "grayscale", "二值化", "threshold",
            "直方图", "histogram", "均衡化", "equalize",
            "对比度", "contrast", "亮度", "brightness",
            "色彩校正", "color correct",
            "风格迁移", "style transfer",
            "超分辨率", "super resolution", "超分",
            "去水印", "watermark",
            "分割", "segmentation",
            "目标检测", "object detection",
            "修复", "inpainting",
            "形态学", "morphology", "膨胀", "腐蚀",
            "滤波", "filter", "median", "中值",
            "平滑", "smooth", "高斯", "双边", "bilateral",
            "翻转", "flip", "镜像", "mirror",
        ]
        text_lower = user_request.lower()
        found = []
        for kw in keyword_candidates:
            if kw.lower() in text_lower:
                found.append(kw)
        return found

    # ── 相似度计算 ────────────────────────────────────────────

    @staticmethod
    def _keyword_similarity(kw1: List[str], kw2: List[str]) -> float:
        """基于关键词重叠的 Jaccard 相似度"""
        if not kw1 or not kw2:
            return 0.0
        set1, set2 = set(k.lower() for k in kw1), set(k.lower() for k in kw2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    # ── 查询相似问题 ──────────────────────────────────────────

    def find_similar(self,
                     user_request: str,
                     min_similarity: float = 0.3,
                     max_results: int = 5) -> List[Dict[str, Any]]:
        """
        根据用户请求查找相似的历史问题及成功方案。

        Returns:
            [{problem_id, description, keywords, similarity, solutions: [...]}]
        """
        query_keywords = self._extract_keywords(user_request)
        self.data["stats"]["total_queries"] += 1

        results = []
        for pid, entry in self.data["problems"].items():
            stored_keywords = entry.get("keywords", [])
            sim = self._keyword_similarity(query_keywords, stored_keywords)
            if sim >= min_similarity:
                solutions = entry.get("solutions", [])
                # 只返回有成功案例的
                active_solutions = [
                    s for s in solutions
                    if s.get("active", True) and s.get("success_count", 0) > 0
                ]
                if active_solutions:
                    results.append({
                        "problem_id": pid,
                        "description": entry["description"],
                        "keywords": stored_keywords,
                        "similarity": round(sim, 3),
                        "solutions": self._rank_solutions(active_solutions),
                    })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        self._save()
        return results[:max_results]

    def _rank_solutions(self, solutions: List[Dict]) -> List[Dict]:
        """按综合得分排序方案"""
        now = time.time()

        def solution_weight(s: Dict) -> float:
            score = s.get("score", 5)
            success_rate = s.get("success_count", 0) / \
                max(s.get("total_count", 1), 1)
            # 时间衰减：超过 30 天未使用降低权重
            last_used = s.get("last_used_ts", now)
            days_since = (now - last_used) / 86400
            decay = max(0.3, 1.0 - (days_since / 180)
                        * 0.7)  # 180天线性衰减到30%
            return score * 0.4 + success_rate * 10 * 0.4 + decay * 2

        ranked = sorted(solutions, key=solution_weight, reverse=True)
        # 只返回排名前三的方案
        return ranked[:3]

    # ── 记录成功案例 ──────────────────────────────────────────

    def record_success(self,
                       user_request: str,
                       approach: str,
                       score: float,
                       code: str = "",
                       parameters: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        记录一次成功的处理案例。

        Args:
            user_request: 用户原始需求
            approach: 算法方案描述（简短摘要）
            score: 评估评分 (0-10)
            code: 生成的代码（可选，用于未来推荐时参考）
            parameters: 参数配置

        Returns:
            problem_id 或 None（评分太低不记录）
        """
        if score < 5:
            return None  # 低质量结果不记录

        pid = self._problem_id(user_request)
        keywords = self._extract_keywords(user_request)
        now_ts = time.time()

        if pid not in self.data["problems"]:
            self.data["problems"][pid] = {
                "description": user_request,
                "keywords": keywords,
                "created_at": datetime.now().isoformat(),
                "solutions": [],
            }

        problem = self.data["problems"][pid]

        # 检查是否已有相似方案
        for sol in problem["solutions"]:
            if self._approach_similar(sol["approach"], approach):
                # 更新现有方案
                sol["success_count"] += 1
                sol["total_count"] += 1
                sol["last_used_ts"] = now_ts
                sol["last_used"] = datetime.now().isoformat()
                # 更新评分为指数移动平均
                alpha = 0.3
                sol["score"] = round(
                    alpha * score + (1 - alpha) * sol["score"], 1)
                if code:
                    sol["code_samples"].append(code[:2000])
                    if len(sol["code_samples"]) > 5:
                        sol["code_samples"] = sol["code_samples"][-5:]
                self.data["stats"]["total_recorded"] += 1
                self._save()
                print(
                    f"[KnowledgeBase] Updated solution for {pid}: score={sol['score']}")
                return pid

        # 新增方案
        problem["solutions"].append({
            "approach": approach,
            "parameters": parameters or {},
            "score": round(score, 1),
            "success_count": 1,
            "total_count": 1,
            "active": True,
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
            "last_used_ts": now_ts,
            "code_samples": [code[:2000]] if code else [],
        })

        self.data["stats"]["total_recorded"] += 1
        self._save()
        print(
            f"[KnowledgeBase] Recorded new solution for {pid}: score={score}/10, approach={approach[:80]}")
        return pid

    # ── 记录失败案例 ──────────────────────────────────────────

    def record_failure(self,
                       user_request: str,
                       approach: str,
                       score: float,
                       reason: str = "") -> Optional[str]:
        """记录失败案例，降低对应方案的权重"""
        if score >= 5:
            return None  # 不是真正的失败

        pid = self._problem_id(user_request)
        if pid not in self.data["problems"]:
            return None

        problem = self.data["problems"][pid]
        for sol in problem["solutions"]:
            if self._approach_similar(sol["approach"], approach):
                sol["total_count"] += 1
                # 失败惩罚：降低评分
                sol["score"] = round(max(1, sol["score"] - 1.0), 1)
                # 如果成功率低于 30%，标记为不活跃
                success_rate = sol["success_count"] / \
                    max(sol["total_count"], 1)
                if success_rate < 0.3 and sol["total_count"] >= 3:
                    sol["active"] = False
                    print(
                        f"[KnowledgeBase] Deactivated low-performing solution: {sol['approach'][:80]}")
                self._save()
                return pid
        return None

    # ── 推荐方案 ──────────────────────────────────────────────

    def recommend(self,
                  user_request: str,
                  task_type: str = "",
                  max_results: int = 3) -> List[Dict[str, Any]]:
        """
        为新请求推荐最佳实践。

        Returns:
            [{similarity, approach, score, success_rate, code_sample}]
        """
        similar = self.find_similar(
            user_request, min_similarity=0.25, max_results=max_results)

        recommendations = []
        for item in similar:
            for sol in item["solutions"]:
                success_rate = sol["success_count"] / \
                    max(sol["total_count"], 1)
                recommendations.append({
                    "similarity": item["similarity"],
                    "problem_description": item["description"],
                    "approach": sol["approach"],
                    "score": sol["score"],
                    "success_rate": round(success_rate, 2),
                    "success_count": sol["success_count"],
                    "total_count": sol["total_count"],
                    "code_sample": sol.get("code_samples", [None])[0] if sol.get("code_samples") else None,
                })

        recommendations.sort(
            key=lambda x: (x["similarity"] * 0.5 + x["score"] / 10 * 0.3 + x["success_rate"] * 0.2),
            reverse=True,
        )
        return recommendations[:max_results]

    # ── 辅助 ──────────────────────────────────────────────────

    @staticmethod
    def _approach_similar(a1: str, a2: str) -> bool:
        """简单判断两个方案描述是否相似（关键词重叠）"""
        words1 = set(a1.lower().split())
        words2 = set(a2.lower().split())
        if not words1 or not words2:
            return False
        overlap = len(words1 & words2)
        return overlap >= 2 or overlap / max(len(words1), len(words2)) > 0.5

    # ── 维护 ──────────────────────────────────────────────────

    def cleanup_stale(self, max_age_days: int = 180):
        """清理过期知识（超过 max_age_days 天未使用）"""
        now_ts = time.time()
        removed = 0
        for pid, entry in list(self.data["problems"].items()):
            solutions = entry.get("solutions", [])
            active_solutions = []
            for sol in solutions:
                days_since = (now_ts - sol.get("last_used_ts", 0)) / 86400
                if days_since < max_age_days:
                    active_solutions.append(sol)
                else:
                    removed += 1
            if active_solutions:
                entry["solutions"] = active_solutions
            else:
                del self.data["problems"][pid]
        self._save()
        print(
            f"[KnowledgeBase] Cleanup: removed {removed} stale solutions")

    def get_stats(self) -> Dict[str, Any]:
        total_problems = len(self.data["problems"])
        total_solutions = sum(
            len(p.get("solutions", [])) for p in self.data["problems"].values())
        return {
            "total_problems": total_problems,
            "total_solutions": total_solutions,
            "total_recorded": self.data["stats"]["total_recorded"],
            "total_queries": self.data["stats"]["total_queries"],
        }
