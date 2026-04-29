"""
Controller: 系统的核心 agent，负责其他 agent 的编排和调度，以及对用户输入的处理，任务设计与拆分

责任边界:
- 任务理解与分发：接受用户提示词，根据任务类型和需求，将任务分发给对应的 agent 进行处理
- 结果汇总：收集不同 agent 的处理结果，进行整合和分析，最终形成一个完整的结果返回给用户界面

能力要求:
- Memory: 需要具备一定的记忆能力，能够记录和管理不同 agent 的状态和历史操作
- 错误处理：在 agent 执行过程中，可能会遇到各种错误和异常情况，能够进行处理和恢复
- 任务调度：根据不同 agent 的能力和当前任务的需求，动态地进行调度和编排
"""

import os
import json
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

from agents.retrieval_agent import RetrievalAgent
from agents.code_generation_agent import CodeGenerationAgent
from agents.evaluation_agent import EvaluationAgent
from agents.execution_agent import ExecutionAgent


class ControllerAgent:
    """控制器 Agent，负责编排和调度其他 agent"""
    
    def __init__(self):
        # 初始化各个子 agent
        self.retrieval_agent = RetrievalAgent()
        self.code_generation_agent = CodeGenerationAgent()
        self.evaluation_agent = EvaluationAgent()
        self.execution_agent = ExecutionAgent()
        
        # 会话状态管理
        self.sessions: Dict[str, Dict[str, Any]] = {}
        
        # 状态历史用于展示
        self.state_history: List[Dict[str, Any]] = []
    
    def create_session(self, user_id: str = "default") -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "status": "initialized",
            "user_request": None,
            "input_image": None,
            "search_results": None,
            "generated_code": None,
            "execution_result": None,
            "evaluation_result": None,
            "feedback_history": [],
            "iteration_count": 0
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        return self.sessions.get(session_id)
    
    def add_state_log(self, session_id: str, agent_name: str, action: str, 
                     status: str, data: Optional[Dict] = None):
        """添加状态日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "agent": agent_name,
            "action": action,
            "status": status,
            "data": data or {}
        }
        self.state_history.append(log_entry)
        
        if session_id in self.sessions:
            if "state_logs" not in self.sessions[session_id]:
                self.sessions[session_id]["state_logs"] = []
            self.sessions[session_id]["state_logs"].append(log_entry)
    
    def process_user_request(self, 
                            session_id: str,
                            user_request: str,
                            input_image_path: Optional[str] = None,
                            enable_search: bool = True) -> Dict[str, Any]:
        """
        处理用户请求的主流程
        
        Args:
            session_id: 会话 ID
            user_request: 用户需求描述
            input_image_path: 可选的输入图片路径
            enable_search: 是否启用联网搜索
            
        Returns:
            处理结果
        """
        if session_id not in self.sessions:
            return {"success": False, "error": "Session not found"}
        
        session = self.sessions[session_id]
        session["user_request"] = user_request
        session["input_image"] = input_image_path
        session["status"] = "processing"
        session["iteration_count"] += 1
        
        result = {
            "session_id": session_id,
            "iteration": session["iteration_count"],
            "steps": []
        }
        
        try:
            # Step 1: 检索相关信息 (可选)
            if enable_search:
                self.add_state_log(session_id, "RetrievalAgent", "search_start", "running",
                                  {"query": user_request})
                
                search_query = f"image processing {user_request} algorithm implementation python opencv pil"
                search_results = self.retrieval_agent.get_structured_results(search_query)
                session["search_results"] = search_results
                
                self.add_state_log(session_id, "RetrievalAgent", "search_complete", "success",
                                  {"results_preview": search_results[:200] + "..."})
                
                result["steps"].append({
                    "agent": "RetrievalAgent",
                    "action": "search",
                    "status": "completed",
                    "result": search_results
                })
            
            # Step 2: 生成代码
            self.add_state_log(session_id, "CodeGenerationAgent", "code_gen_start", "running",
                              {"request": user_request[:100]})
            
            generated_code = self.code_generation_agent.generate_code(
                user_request=user_request,
                search_results=session.get("search_results"),
                previous_code=session.get("generated_code"),
                feedback=session["feedback_history"][-1] if session["feedback_history"] else None
            )
            
            # 提取代码块
            generated_code = self.code_generation_agent.extract_code_block(generated_code)
            session["generated_code"] = generated_code
            
            self.add_state_log(session_id, "CodeGenerationAgent", "code_gen_complete", "success",
                              {"code_preview": generated_code[:200] + "..."})
            
            result["steps"].append({
                "agent": "CodeGenerationAgent",
                "action": "generate_code",
                "status": "completed",
                "result": generated_code
            })
            
            # Step 3: 执行代码
            self.add_state_log(session_id, "ExecutionAgent", "execution_start", "running",
                              {"input_image": input_image_path})
            
            output_filename = f"result_{session_id}_{session['iteration_count']}.png"
            execution_result = self.execution_agent.execute_code(
                code=generated_code,
                input_image_path=input_image_path,
                output_filename=output_filename
            )
            
            session["execution_result"] = execution_result
            
            if execution_result["success"]:
                self.add_state_log(session_id, "ExecutionAgent", "execution_complete", "success",
                                  {"output_path": execution_result["output_path"]})
            else:
                self.add_state_log(session_id, "ExecutionAgent", "execution_failed", "error",
                                  {"error": execution_result["error"]})
            
            result["steps"].append({
                "agent": "ExecutionAgent",
                "action": "execute",
                "status": "completed" if execution_result["success"] else "failed",
                "result": execution_result
            })
            
            # Step 4: 评估结果
            self.add_state_log(session_id, "EvaluationAgent", "evaluation_start", "running")
            
            if execution_result["success"] and execution_result["output_path"]:
                evaluation_result = self.evaluation_agent.evaluate_image(
                    image_path=execution_result["output_path"],
                    user_request=user_request,
                    algorithm_code=generated_code
                )
            else:
                evaluation_result = self.evaluation_agent.evaluate_code(
                    code=generated_code,
                    user_request=user_request
                )
            
            session["evaluation_result"] = evaluation_result
            
            self.add_state_log(session_id, "EvaluationAgent", "evaluation_complete", "success",
                              {"evaluation_preview": evaluation_result.get("evaluation_text", "")[:200]})
            
            result["steps"].append({
                "agent": "EvaluationAgent",
                "action": "evaluate",
                "status": "completed",
                "result": evaluation_result
            })
            
            session["status"] = "completed"
            result["success"] = True
            
        except Exception as e:
            session["status"] = "error"
            session["error"] = str(e)
            self.add_state_log(session_id, "Controller", "process_failed", "error",
                              {"error": str(e)})
            result["success"] = False
            result["error"] = str(e)
        
        return result
    
    def submit_feedback(self, 
                       session_id: str, 
                       feedback_type: str, 
                       suggestions: Optional[str] = None) -> Dict[str, Any]:
        """
        提交用户反馈
        
        Args:
            session_id: 会话 ID
            feedback_type: "accept" 或 "reject"
            suggestions: 如果是 reject，可以提供改进建议
            
        Returns:
            处理结果
        """
        if session_id not in self.sessions:
            return {"success": False, "error": "Session not found"}
        
        session = self.sessions[session_id]
        
        feedback_entry = {
            "type": feedback_type,
            "suggestions": suggestions,
            "timestamp": datetime.now().isoformat(),
            "iteration": session["iteration_count"]
        }
        
        session["feedback_history"].append(feedback_entry)
        
        self.add_state_log(session_id, "Controller", "feedback_received", "info",
                          {"feedback_type": feedback_type, "suggestions": suggestions})
        
        if feedback_type == "reject" and suggestions:
            # 用户拒绝并提供建议，需要重新生成
            session["status"] = "iterating"
            return {
                "success": True,
                "message": "收到反馈，正在根据建议重新生成...",
                "action": "regenerate"
            }
        elif feedback_type == "accept":
            session["status"] = "accepted"
            return {
                "success": True,
                "message": "感谢您的认可！",
                "action": "complete"
            }
        else:
            return {
                "success": True,
                "message": "反馈已记录",
                "action": "none"
            }
    
    def get_state_diagram(self, session_id: str) -> str:
        """
        生成状态流程图 (Mermaid 格式)
        
        Args:
            session_id: 会话 ID
            
        Returns:
            Mermaid 格式的流程图
        """
        if session_id not in self.sessions:
            return "Session not found"
        
        session = self.sessions[session_id]
        state_logs = session.get("state_logs", [])
        
        # 构建 Mermaid 流程图
        mermaid_parts = ["graph TD"]
        mermaid_parts.append("    Start([用户输入]) --> Retrieval[检索 Agent]")
        
        for i, log in enumerate(state_logs):
            agent = log["agent"]
            action = log["action"]
            status = log["status"]
            
            node_id = f"Node{i}"
            status_emoji = "✅" if status == "success" else ("❌" if status == "error" else "🔄")
            
            if i > 0:
                prev_node = f"Node{i-1}"
                mermaid_parts.append(f"    {prev_node} --> {node_id}[{agent}: {action} {status_emoji}]")
            else:
                mermaid_parts.append(f"    Retrieval --> {node_id}[{agent}: {action} {status_emoji}]")
        
        mermaid_parts.append(f"    Node{len(state_logs)-1 if state_logs else 'Retrieval'} --> End([结束])")
        
        return "\n".join(mermaid_parts)
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """获取会话摘要"""
        if session_id not in self.sessions:
            return {"error": "Session not found"}
        
        session = self.sessions[session_id]
        return {
            "session_id": session_id,
            "status": session["status"],
            "iteration_count": session["iteration_count"],
            "user_request": session["user_request"],
            "generated_code": session.get("generated_code"),
            "execution_result": session.get("execution_result"),
            "evaluation_result": session.get("evaluation_result"),
            "output_image": session.get("execution_result", {}).get("output_path") if session.get("execution_result", {}).get("success") else None,
            "feedback_history": session.get("feedback_history", []),
            "state_logs": session.get("state_logs", [])
        }
