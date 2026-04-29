"""
检索 Agent: 联网检索场景相关内容，例如实现思路、评价指标等等
- 调用 TavilyAPI 实现，并且能够将结果结构化输出
- 能够做本地搜索记录缓存，避免重复检索 (简单实现)
"""

import os
import json
import hashlib
from typing import Optional, List, Dict, Any
from tavily import TavilyClient


class RetrievalAgent:
    """检索 Agent，负责联网搜索相关信息"""
    
    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY environment variable is required")
        self.client = TavilyClient(api_key=self.api_key)
        self.cache_file = "search_cache.json"
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """加载搜索缓存"""
        if os.path.exists(self.cache_file):
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _save_cache(self):
        """保存搜索缓存"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    def _get_cache_key(self, query: str) -> str:
        """生成缓存键"""
        return hashlib.md5(query.encode()).hexdigest()
    
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        执行搜索
        
        Args:
            query: 搜索查询
            max_results: 最大返回结果数
            
        Returns:
            搜索结果列表
        """
        cache_key = self._get_cache_key(query)
        
        # 检查缓存
        if cache_key in self.cache:
            print(f"[RetrievalAgent] Using cached results for: {query}")
            return self.cache[cache_key]
        
        # 执行搜索
        print(f"[RetrievalAgent] Searching for: {query}")
        try:
            response = self.client.search(query, max_results=max_results)
            results = []
            
            if isinstance(response, dict) and 'results' in response:
                for item in response['results']:
                    results.append({
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'content': item.get('content', ''),
                        'snippet': item.get('content', '')
                    })
            elif isinstance(response, list):
                for item in response:
                    results.append({
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'content': item.get('content', ''),
                        'snippet': item.get('content', '')
                    })
            
            # 缓存结果
            self.cache[cache_key] = results
            self._save_cache()
            
            print(f"[RetrievalAgent] Found {len(results)} results")
            return results
            
        except Exception as e:
            print(f"[RetrievalAgent] Search error: {e}")
            return []
    
    def get_structured_results(self, query: str, max_results: int = 5) -> str:
        """
        获取结构化的搜索结果
        
        Args:
            query: 搜索查询
            max_results: 最大返回结果数
            
        Returns:
            格式化的搜索结果字符串
        """
        results = self.search(query, max_results)
        
        if not results:
            return "未找到相关搜索结果"
        
        formatted = []
        formatted.append(f"## 搜索结果：{query}\n")
        
        for i, result in enumerate(results, 1):
            formatted.append(f"### {i}. {result['title']}")
            formatted.append(f"URL: {result['url']}")
            formatted.append(f"内容：{result['content']}\n")
        
        return "\n".join(formatted)
