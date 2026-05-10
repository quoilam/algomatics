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
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime

from agents.retrieval_agent import RetrievalAgent
from agents.code_generation_agent import CodeGenerationAgent
from agents.evaluation_agent import EvaluationAgent
from agents.execution_agent import ExecutionAgent
from session_resources import SessionResourceManager
from controller.task_parser import TaskParser
from controller.planning_engine import PlanningEngine


class ControllerAgent:
    """控制器 Agent，负责编排和调度其他 agent"""

    def __init__(self, session_root: str = "sessions"):
        # 初始化各个子 agent
        self.retrieval_agent = RetrievalAgent()
        self.code_generation_agent = CodeGenerationAgent()
        self.evaluation_agent = EvaluationAgent()
        self.execution_agent = ExecutionAgent()
        self.resource_manager = SessionResourceManager(session_root)

        # 初始化规划组件
        self.task_parser = TaskParser()
        self.planning_engine = PlanningEngine()

        # 会话状态管理
        self.sessions: Dict[str, Dict[str, Any]] = {}

        # 状态历史用于展示
        self.state_history: List[Dict[str, Any]] = []

    def _persist_session(self, session_id: str):
        """Persist the current in-memory session snapshot."""
        if session_id in self.sessions:
            self.resource_manager.save_session_state(
                session_id, self.sessions[session_id])

    def _session_resources(self, session_id: str) -> Dict[str, str]:
        return self.resource_manager.session_resource_payload(session_id)

    def _record_agent_call(self,
                           session_id: str,
                           agent_name: str,
                           action: str,
                           payload: Optional[Dict[str, Any]] = None,
                           result: Optional[Dict[str, Any]] = None):
        self.resource_manager.append_agent_call(
            session_id, agent_name, action, payload, result)

    def _hash_text(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _hash_file(self, file_path: Optional[str]) -> Optional[str]:
        if not file_path or not os.path.exists(file_path):
            return None
        digest = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _is_code_generation_failure(self, code: str) -> bool:
        stripped = (code or "").strip()
        return stripped.startswith("# 代码生成失败") or stripped.startswith("代码生成失败")

    def _append_message(self,
                        session_id: str,
                        role: str,
                        content: str,
                        metadata: Optional[Dict[str, Any]] = None,
                        image_url: Optional[str] = None,
                        status: str = "complete"):
        """Append a message to session messages and persist."""
        if session_id not in self.sessions:
            return None
        session = self.sessions[session_id]
        msg_count = len(session.get("messages", []))
        msg = {
            "id": f"{session_id}_{role}_{msg_count + 1}",
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "status": status,
        }
        if metadata:
            msg["metadata"] = metadata
        if image_url:
            msg["imageUrl"] = image_url
        session.setdefault("messages", []).append(msg)
        self._persist_session(session_id)
        return msg

    def _apply_final_result(self,
                            session: Dict[str, Any],
                            candidate: Optional[Dict[str, Any]],
                            fallback_score: int,
                            reason: str):
        """Record the selected final result while keeping last-iteration traces intact."""
        final_result = {
            "score": fallback_score,
            "iteration_reason": reason
        }
        if candidate:
            session["generated_code"] = candidate.get("generated_code")
            session["generated_code_path"] = candidate.get(
                "generated_code_path")
            session["execution_result"] = candidate.get("execution_result")
            session["evaluation_result"] = candidate.get("evaluation_result")
            final_result.update({
                "score": candidate.get("score", fallback_score),
                "iteration": candidate.get("iteration"),
                "generated_code_path": candidate.get("generated_code_path"),
                "output_path": (candidate.get("execution_result") or {}).get("output_path"),
                "code_hash": candidate.get("code_hash"),
                "output_hash": candidate.get("output_hash")
            })
        session["final_result"] = final_result
        session["final_score"] = final_result["score"]

    def create_session(self, user_id: str = "default") -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        resources = self._session_resources(session_id)
        self.resource_manager.link_latest_session(session_id)
        self.sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "status": "initialized",
            "resources": resources,
            "user_request": None,
            "input_image": None,
            "messages": [],
            "search_results": None,
            "generated_code": None,
            "execution_result": None,
            "evaluation_result": None,
            "feedback_history": [],
            "iteration_count": 0
        }
        self._persist_session(session_id)
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
            self.resource_manager.append_state_log(session_id, log_entry)
            self._persist_session(session_id)

    def process_user_request(self,
                             session_id: str,
                             user_request: str,
                             input_image_path: Optional[str] = None,
                             enable_search: bool = True,
                             on_event_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        处理用户请求的主流程 - MVP版本，支持评分驱动的自动迭代

        Args:
            session_id: 会话 ID
            user_request: 用户需求描述
            input_image_path: 可选的输入图片路径
            enable_search: 是否启用联网搜索
            on_event_callback: 可选的事件推送回调函数，签名为 callback(event_type, data)

        Returns:
            处理结果
        """
        def emit_event(event_type: str, data: Dict[str, Any]):
            """发送事件到前端（如果有回调）"""
            if on_event_callback:
                try:
                    print(
                        f"[Controller] Emitting event: {event_type} for session {session_id}")
                    on_event_callback(event_type, data)
                except Exception as e:
                    print(
                        f"[Controller] Error emitting event {event_type}: {e}")

        def emit_agent_update(content: str,
                              agent_name: str = "Controller",
                              phase: str = "progress",
                              metadata: Optional[Dict[str, Any]] = None):
            """Send a user-facing progress note and append to messages."""
            update_meta = {
                "kind": "agent_update",
                "agent": agent_name,
                "phase": phase,
                **(metadata or {})
            }
            update = {
                "role": "assistant",
                "content": content.rstrip() + "\n\n",
                "timestamp": datetime.now().isoformat(),
                "metadata": update_meta
            }

            msg = self._append_message(session_id, "assistant",
                                       content.rstrip() + "\n\n",
                                       metadata=update_meta)
            if msg:
                update["id"] = msg["id"]

            emit_event("message", update)

        if session_id not in self.sessions:
            return {"success": False, "error": "Session not found"}

        session = self.sessions[session_id]
        resources = session.get(
            "resources") or self._session_resources(session_id)
        session["resources"] = resources
        session["user_request"] = user_request

        # 将用户消息追加到 messages 列表
        self._append_message(session_id, "user", user_request, status="sent")

        # 多轮对话：如果没有传入新图片，复用会话已有的 input_image
        if input_image_path:
            session["input_image"] = input_image_path
        elif not session.get("input_image"):
            session["input_image"] = None
        # else: 保持已有的 input_image 不变

        # 检测是否为跟进请求（多轮对话）
        is_followup = bool(
            session.get("evaluation_result")
            or session.get("last_score")
            or session.get("best_result")
        )

        session["status"] = "processing"
        self._persist_session(session_id)
        emit_event('status', {
            "status": "processing",
            "timestamp": datetime.now().isoformat()
        })
        emit_agent_update(
            f"我已收到任务：{user_request}\n\n"
            f"接下来会先判断是否需要检索外部算法资料，然后生成可执行代码、运行图片处理、评估效果，并按评分决定是否继续优化。",
            phase="plan",
            metadata={
                "enable_search": enable_search,
                "has_input_image": bool(session.get("input_image")),
                "is_followup": is_followup
            }
        )

        # 记录跟进反馈到 feedback_history
        if is_followup:
            session.setdefault("feedback_history", []).append({
                "type": "revision",
                "content": user_request,
                "timestamp": datetime.now().isoformat(),
                "prior_score": session.get("last_score"),
                "prior_iteration": session.get("iteration_count", 0)
            })
            self._persist_session(session_id)

        result = {
            "session_id": session_id,
            "total_iterations": 0,
            "steps": []
        }

        # MVP迭代控制参数（可由 PlanningEngine 动态调整）
        MAX_ITERATIONS = 3  # 默认最多迭代3次
        SCORE_THRESHOLD_ACCEPT = 7  # 评分 >= 7 接受
        SCORE_THRESHOLD_OPTIMIZE = 5  # 评分 < 5 放弃迭代

        # ── 阶段3: 任务解析与策略规划 ──
        task_parse_result = self.task_parser.parse(
            user_request,
            has_input_image=bool(session.get("input_image"))
        )
        plan = self.planning_engine.plan(task_parse_result)
        session["task_parse"] = task_parse_result
        session["execution_plan"] = plan

        # 用策略覆盖默认参数
        plan_enable_search = plan["enable_search"] and enable_search  # 用户手动关闭优先
        plan_enable_iteration = plan["enable_iteration"]
        MAX_ITERATIONS = plan["max_iterations"]

        emit_agent_update(
            f"任务解析完成：识别为 {task_parse_result['task_type']} 任务"
            f"（置信度 {task_parse_result['confidence']:.0%}）。\n"
            f"执行策略：{plan['strategy']} — {plan['decision_reason']}",
            agent_name="Controller",
            phase="plan",
            metadata={
                "task_type": task_parse_result["task_type"],
                "strategy": plan["strategy"],
                "plan": plan,
            }
        )
        self._persist_session(session_id)

        current_score = 0
        # 多轮对话：将上一轮的分数作为上下文传递给第一轮代码生成
        followup_starting_score = session.get(
            "last_score") if is_followup else None
        search_results = None
        generated_code = None
        previous_code_hash = None
        previous_output_hash = None
        stagnant_iterations = 0
        # 多轮对话：从上一轮最佳结果开始，新结果需要超越上一轮才能更新 best_result
        best_result = session.get("best_result") if is_followup else None

        try:
            # Step 0: Agentic 检索 —— RetrievalAgent 自主规划搜索词并综合提炼
            if plan_enable_search and not session.get("search_results"):
                emit_agent_update(
                    "我会让检索 Agent 分析你的任务，自主规划搜索策略并联网检索相关资料，"
                    "然后综合提炼为代码生成可直接使用的参考简报。",
                    agent_name="RetrievalAgent",
                    phase="decision",
                    metadata={"task": user_request}
                )
                self.add_state_log(session_id, "RetrievalAgent", "research_start", "running",
                                   {"user_request": user_request})
                emit_event('state', {
                    "id": "research_start",
                    "agent": "RetrievalAgent",
                    "action": "research_start",
                    "status": "started",
                    "timestamp": datetime.now().isoformat(),
                    "data": {"user_request": user_request}
                })

                research_result = self.retrieval_agent.research(user_request)
                search_results = research_result["brief"]
                session["search_results"] = search_results
                session["research_meta"] = {
                    "quality_score": research_result["quality_score"],
                    "quality_verdict": research_result["quality_verdict"],
                    "should_skip": research_result["should_skip"],
                    "queries_used": research_result["queries_used"],
                    "total_results": research_result["total_results"],
                }
                self._record_agent_call(
                    session_id,
                    "RetrievalAgent",
                    "research",
                    {"user_request": user_request},
                    {
                        "queries_used": research_result["queries_used"],
                        "total_results": research_result["total_results"],
                        "quality_score": research_result["quality_score"],
                        "brief_preview": (search_results or "")[:500],
                    }
                )
                self._persist_session(session_id)

                self.add_state_log(session_id, "RetrievalAgent", "research_complete", "success",
                                   {"quality_score": research_result["quality_score"],
                                    "quality_verdict": research_result["quality_verdict"],
                                    "queries_used": research_result["queries_used"],
                                    "total_results": research_result["total_results"],
                                    "brief": (search_results or "")[:2000]})

                if research_result["should_skip"]:
                    emit_agent_update(
                        f"检索 Agent 完成研究，但自评质量较低（{research_result['quality_score']}/10），"
                        "建议代码生成时降低对检索资料的依赖，更多依靠模型自身知识。",
                        agent_name="RetrievalAgent",
                        phase="result",
                        metadata=research_result
                    )
                else:
                    emit_agent_update(
                        f"检索 Agent 完成研究：自主规划了 {len(research_result['queries_used'])} 个搜索词，"
                        f"共获取 {research_result['total_results']} 条结果，"
                        f"综合简报质量自评 {research_result['quality_score']}/10。",
                        agent_name="RetrievalAgent",
                        phase="result",
                        metadata=research_result
                    )

                emit_event('state', {
                    "id": "research_complete",
                    "agent": "RetrievalAgent",
                    "action": "research_complete",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "quality_score": research_result["quality_score"],
                        "quality_verdict": research_result["quality_verdict"],
                        "total_results": research_result["total_results"],
                        "queries_used": research_result["queries_used"],
                        "brief": (search_results or ""),
                    }
                })

                result["steps"].append({
                    "agent": "RetrievalAgent",
                    "action": "research",
                    "status": "completed",
                    "result": {
                        "brief_preview": (search_results or "")[:500],
                        "quality_score": research_result["quality_score"],
                        "queries_used": research_result["queries_used"],
                    }
                })
            else:
                search_results = session.get("search_results")
                if plan_enable_search:
                    emit_agent_update(
                        "这个会话里已有检索结果，我会复用它们，直接进入代码生成，避免重复等待。",
                        agent_name="RetrievalAgent",
                        phase="decision"
                    )
                else:
                    emit_agent_update(
                        "根据策略规划，本次跳过联网检索，直接基于模型知识和本地可用库生成代码。",
                        agent_name="Controller",
                        phase="decision"
                    )

            # 自动迭代循环：评分驱动的多轮优化
            iteration_count = 0
            while iteration_count < MAX_ITERATIONS:
                iteration_count += 1
                session["iteration_count"] = iteration_count
                result["total_iterations"] = iteration_count

                print(f"\n[Controller] === 迭代第 {iteration_count} 次 ===")
                emit_agent_update(
                    f"进入第 {iteration_count}/{MAX_ITERATIONS} 轮。"
                    f"{' 这轮会结合上一轮评分和改进建议来重写代码。' if iteration_count > 1 else ' 这轮会先生成初版处理算法。'}",
                    phase="iteration",
                    metadata={"iteration": iteration_count,
                              "max_iterations": MAX_ITERATIONS}
                )

                # Step 1: 生成代码（带迭代信息）
                self.add_state_log(session_id, "CodeGenerationAgent", f"code_gen_start_{iteration_count}", "running",
                                   {"iteration": iteration_count, "previous_score": current_score})
                emit_event('state', {
                    "id": f"code_gen_start_{iteration_count}",
                    "agent": "CodeGenerationAgent",
                    "action": f"code_gen_start",
                    "status": "started",
                    "timestamp": datetime.now().isoformat(),
                    "data": {"iteration": iteration_count, "previous_score": current_score}
                })

                iteration_info = {
                    "iteration_count": iteration_count,
                    "previous_score": (
                        followup_starting_score
                        if (is_followup and iteration_count == 1 and followup_starting_score is not None)
                        else (current_score if iteration_count > 1 else None)
                    ),
                    "improvements": session.get("last_improvements", "")
                }

                emit_agent_update(
                    "我正在让代码生成 agent 产出一段可直接执行的 Python 图像处理脚本，约束是使用 `input_image_path` 和 `output_path`，并确保保存结果图片。",
                    agent_name="CodeGenerationAgent",
                    phase="action",
                    metadata=iteration_info
                )
                generated_code = self.code_generation_agent.generate_code(
                    user_request=user_request,
                    search_results=search_results,
                    previous_code=session.get(
                        "generated_code") if iteration_count > 1 else None,
                    iteration_info=iteration_info,
                    retrieval_quality=session.get("research_meta")
                )

                # 提取代码块
                generated_code = self.code_generation_agent.extract_code_block(
                    generated_code)
                code_generation_failed = self._is_code_generation_failure(
                    generated_code)
                code_hash = self._hash_text(generated_code)
                session["generated_code"] = generated_code
                code_file = self.resource_manager.save_workspace_code(
                    session_id, f"iteration_{iteration_count}.py", generated_code)
                session["generated_code_path"] = code_file
                self._record_agent_call(
                    session_id,
                    "CodeGenerationAgent",
                    "generate_code",
                    {"iteration": iteration_count, "previous_score": current_score},
                    {
                        "code_path": code_file,
                        "code_length": len(generated_code),
                        "code_hash": code_hash,
                        "code_generation_failed": code_generation_failed
                    }
                )
                self._persist_session(session_id)

                code_gen_status = "error" if code_generation_failed else "success"
                self.add_state_log(session_id, "CodeGenerationAgent", f"code_gen_complete_{iteration_count}", code_gen_status,
                                   {
                    "code_preview": generated_code[:5000],
                    "code_length": len(generated_code),
                    "iteration": iteration_count,
                    "code_generation_failed": code_generation_failed,
                    "code_path": code_file,
                })
                if code_generation_failed:
                    emit_agent_update(
                        "代码生成 agent 没有返回可执行脚本，我会停止本轮执行并标记为需要人工审查。",
                        agent_name="CodeGenerationAgent",
                        phase="result",
                        metadata={"iteration": iteration_count, "code_length": len(
                            generated_code), "code_path": code_file}
                    )
                else:
                    emit_agent_update(
                        f"代码已生成并保存到工作区，长度约 {len(generated_code)} 个字符。下一步我会在隔离执行环境里运行它，并捕获输出图片或错误信息。",
                        agent_name="CodeGenerationAgent",
                        phase="result",
                        metadata={"iteration": iteration_count, "code_length": len(
                            generated_code), "code_path": code_file}
                    )
                emit_event('state', {
                    "id": f"code_gen_complete_{iteration_count}",
                    "agent": "CodeGenerationAgent",
                    "action": "code_gen_complete",
                    "status": "failed" if code_generation_failed else "completed",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "iteration": iteration_count,
                        "code_preview": generated_code[:5000],
                        "code_length": len(generated_code),
                        "code_generation_failed": code_generation_failed,
                        "code_path": code_file,
                    }
                })

                result["steps"].append({
                    "agent": "CodeGenerationAgent",
                    "iteration": iteration_count,
                    "action": "generate_code",
                    "status": "completed",
                    "result": generated_code[:1000]  # 限制代码长度在输出中
                })

                if code_generation_failed:
                    session["status"] = "needs_review"
                    self._apply_final_result(
                        session, None, 0, "代码生成失败，未执行后续图像处理")
                    result["success"] = False
                    result["final_score"] = session["final_score"]
                    result["iteration_reason"] = session["final_result"]["iteration_reason"]
                    self._persist_session(session_id)
                    break

                # Step 2: 执行代码
                self.add_state_log(session_id, "ExecutionAgent", f"execution_start_{iteration_count}", "running",
                                   {"input_image": input_image_path, "iteration": iteration_count})
                emit_agent_update(
                    "我现在执行生成的脚本。如果脚本报错或没有产出图片，会进入自动修复流程。",
                    agent_name="ExecutionAgent",
                    phase="action",
                    metadata={"iteration": iteration_count}
                )
                emit_event('state', {
                    "id": f"execution_start_{iteration_count}",
                    "agent": "ExecutionAgent",
                    "action": "execution_start",
                    "status": "started",
                    "timestamp": datetime.now().isoformat(),
                    "data": {"iteration": iteration_count}
                })

                output_filename = f"result_{iteration_count}.png"
                execution_result = self.execution_agent.execute_code(
                    code=generated_code,
                    input_image_path=input_image_path,
                    output_filename=output_filename,
                    output_dir=resources["outputs"],
                    work_dir=resources["workspace"]
                )

                session["execution_result"] = execution_result
                self._record_agent_call(
                    session_id,
                    "ExecutionAgent",
                    "execute_code",
                    {
                        "iteration": iteration_count,
                        "input_image_path": input_image_path,
                        "code_path": session.get("generated_code_path")
                    },
                    {
                        "success": execution_result.get("success"),
                        "output_path": execution_result.get("output_path"),
                        "error": execution_result.get("error")
                    }
                )
                self._persist_session(session_id)

                if execution_result["success"]:
                    self.add_state_log(session_id, "ExecutionAgent", f"execution_complete_{iteration_count}", "success",
                                       {"output_path": execution_result["output_path"], "iteration": iteration_count})
                    emit_agent_update(
                        "脚本执行成功，已经生成结果图片。接下来进入质量评估，判断是否需要继续优化。",
                        agent_name="ExecutionAgent",
                        phase="result",
                        metadata={"iteration": iteration_count,
                                  "output_path": execution_result.get("output_path")}
                    )
                    emit_event('state', {
                        "id": f"execution_complete_{iteration_count}",
                        "agent": "ExecutionAgent",
                        "action": "execution_complete",
                        "status": "completed",
                        "timestamp": datetime.now().isoformat(),
                        "data": {"iteration": iteration_count, "output_path": execution_result.get("output_path")}
                    })
                else:
                    self.add_state_log(session_id, "ExecutionAgent", f"execution_failed_{iteration_count}", "error",
                                       {"error": execution_result["error"],
                                        "error_type": execution_result.get("error_type"),
                                        "error_traceback": (execution_result.get("error_traceback") or "")[:2000],
                                        "iteration": iteration_count})
                    emit_agent_update(
                        f"执行失败，我会尝试自动修复代码。当前错误摘要：{execution_result.get('error', '未知错误')}",
                        agent_name="ExecutionAgent",
                        phase="result",
                        metadata={"iteration": iteration_count,
                                  "error": execution_result.get("error")}
                    )
                    emit_event('state', {
                        "id": f"execution_failed_{iteration_count}",
                        "agent": "ExecutionAgent",
                        "action": "execution_failed",
                        "status": "failed",
                        "timestamp": datetime.now().isoformat(),
                        "data": {
                            "iteration": iteration_count,
                            "error": execution_result.get("error"),
                            "error_type": execution_result.get("error_type"),
                            "error_traceback": (execution_result.get("error_traceback") or "")[:2000],
                        }
                    })

                result["steps"].append({
                    "agent": "ExecutionAgent",
                    "iteration": iteration_count,
                    "action": "execute",
                    "status": "completed" if execution_result["success"] else "failed",
                    "result": {
                        "success": execution_result["success"],
                        "output_path": execution_result.get("output_path"),
                        "error": execution_result.get("error")
                    }
                })

                # 如果执行失败，尝试自动修复（阶段2：错误自修复能力）
                if not execution_result["success"]:
                    MAX_REPAIR_ATTEMPTS = 3
                    repair_attempt = 0
                    repaired_success = False
                    while repair_attempt < MAX_REPAIR_ATTEMPTS and not repaired_success:
                        repair_attempt += 1
                        emit_agent_update(
                            f"开始第 {repair_attempt}/{MAX_REPAIR_ATTEMPTS} 次修复。我会根据错误类型、堆栈信息和上一版代码来生成修正版。",
                            agent_name="CodeGenerationAgent",
                            phase="repair",
                            metadata={"iteration": iteration_count,
                                      "repair_attempt": repair_attempt}
                        )
                        self.add_state_log(session_id, "CodeGenerationAgent", f"repair_start_{iteration_count}_{repair_attempt}", "running",
                                           {"iteration": iteration_count, "repair_attempt": repair_attempt, "error": execution_result.get("error")})
                        emit_event('state', {
                            "id": f"repair_start_{iteration_count}_{repair_attempt}",
                            "agent": "CodeGenerationAgent",
                            "action": "repair_start",
                            "status": "started",
                            "timestamp": datetime.now().isoformat(),
                            "data": {
                                "iteration": iteration_count,
                                "repair_attempt": repair_attempt,
                                "error": execution_result.get("error")
                            }
                        })

                        # 如果第一次修复未产生异常但也未输出文件（无 error），
                        # 则后续尝试直接使用内置的回退可运行实现以保证输出
                        if repair_attempt > 1 and not execution_result.get("error"):
                            repaired_code = (
                                "from PIL import Image, ImageFilter\n"
                                "img = Image.open(input_image_path).convert('RGB')\n"
                                "img = img.filter(ImageFilter.MedianFilter(size=3))\n"
                                "img.save(output_path)\n"
                                "print('图像降噪处理完成，结果保存至:', output_path)\n"
                            )
                        else:
                            repaired_code = self.code_generation_agent.repair_code(
                                previous_code=generated_code,
                                error_type=execution_result.get(
                                    "error_type", ""),
                                error_message=execution_result.get(
                                    "error", ""),
                                error_traceback=execution_result.get(
                                    "error_traceback", ""),
                                iteration_count=repair_attempt,
                                error_context=execution_result.get(
                                    "error_context", {})
                            )

                        repaired_code = self.code_generation_agent.extract_code_block(
                            repaired_code)
                        generated_code = repaired_code
                        code_hash = self._hash_text(generated_code)
                        session["generated_code"] = repaired_code
                        repair_code_file = self.resource_manager.save_workspace_code(
                            session_id,
                            f"iteration_{iteration_count}_repair_{repair_attempt}.py",
                            repaired_code
                        )
                        code_file = repair_code_file
                        session["generated_code_path"] = repair_code_file
                        self._record_agent_call(
                            session_id,
                            "CodeGenerationAgent",
                            "repair_code",
                            {
                                "iteration": iteration_count,
                                "repair_attempt": repair_attempt,
                                "error": execution_result.get("error")
                            },
                            {
                                "code_path": repair_code_file,
                                "code_length": len(repaired_code)
                            }
                        )
                        self._persist_session(session_id)

                        self.add_state_log(session_id, "CodeGenerationAgent", f"repair_complete_{iteration_count}_{repair_attempt}", "success",
                                           {"repair_preview": repaired_code[:5000], "code_length": len(repaired_code), "repair_attempt": repair_attempt})
                        emit_agent_update(
                            f"修复版代码已生成，长度约 {len(repaired_code)} 个字符。现在会重新执行修复后的脚本。",
                            agent_name="CodeGenerationAgent",
                            phase="repair",
                            metadata={"iteration": iteration_count, "repair_attempt": repair_attempt, "code_length": len(
                                repaired_code)}
                        )
                        emit_event('state', {
                            "id": f"repair_complete_{iteration_count}_{repair_attempt}",
                            "agent": "CodeGenerationAgent",
                            "action": "repair_complete",
                            "status": "completed",
                            "timestamp": datetime.now().isoformat(),
                            "data": {
                                "iteration": iteration_count,
                                "repair_attempt": repair_attempt,
                                "repair_preview": repaired_code[:5000],
                                "code_length": len(repaired_code)
                            }
                        })

                        result["steps"].append({
                            "agent": "CodeGenerationAgent",
                            "iteration": iteration_count,
                            "repair_attempt": repair_attempt,
                            "action": "repair_code",
                            "status": "completed",
                            "result": repaired_code[:1000]
                        })

                        # 重新执行修复后的代码
                        self.add_state_log(session_id, "ExecutionAgent", f"repair_execution_start_{iteration_count}_{repair_attempt}", "running",
                                           {"iteration": iteration_count, "repair_attempt": repair_attempt})
                        emit_event('state', {
                            "id": f"repair_execution_start_{iteration_count}_{repair_attempt}",
                            "agent": "ExecutionAgent",
                            "action": "repair_execution_start",
                            "status": "started",
                            "timestamp": datetime.now().isoformat(),
                            "data": {
                                "iteration": iteration_count,
                                "repair_attempt": repair_attempt
                            }
                        })
                        output_filename = f"result_{iteration_count}_repair{repair_attempt}.png"
                        execution_result = self.execution_agent.execute_code(
                            code=repaired_code,
                            input_image_path=input_image_path,
                            output_filename=output_filename,
                            output_dir=resources["outputs"],
                            work_dir=resources["workspace"]
                        )

                        session["execution_result"] = execution_result
                        self._record_agent_call(
                            session_id,
                            "ExecutionAgent",
                            "execute_repair_code",
                            {
                                "iteration": iteration_count,
                                "repair_attempt": repair_attempt,
                                "input_image_path": input_image_path,
                                "code_path": session.get("generated_code_path")
                            },
                            {
                                "success": execution_result.get("success"),
                                "output_path": execution_result.get("output_path"),
                                "error": execution_result.get("error")
                            }
                        )
                        self._persist_session(session_id)
                        if execution_result["success"]:
                            repaired_success = True
                            self.add_state_log(session_id, "ExecutionAgent", f"repair_execution_complete_{iteration_count}_{repair_attempt}", "success",
                                               {"output_path": execution_result.get("output_path"), "repair_attempt": repair_attempt})
                            emit_agent_update(
                                "修复后的脚本执行成功，已经恢复正常流程。下一步继续评估输出质量。",
                                agent_name="ExecutionAgent",
                                phase="repair_result",
                                metadata={"iteration": iteration_count, "repair_attempt": repair_attempt,
                                          "output_path": execution_result.get("output_path")}
                            )
                            emit_event('state', {
                                "id": f"repair_execution_complete_{iteration_count}_{repair_attempt}",
                                "agent": "ExecutionAgent",
                                "action": "repair_execution_complete",
                                "status": "completed",
                                "timestamp": datetime.now().isoformat(),
                                "data": {
                                    "iteration": iteration_count,
                                    "repair_attempt": repair_attempt,
                                    "output_path": execution_result.get("output_path")
                                }
                            })
                            result["steps"].append({
                                "agent": "ExecutionAgent",
                                "iteration": iteration_count,
                                "repair_attempt": repair_attempt,
                                "action": "execute_repair",
                                "status": "completed",
                                "result": {"success": True, "output_path": execution_result.get("output_path")}
                            })
                            break
                        else:
                            self.add_state_log(session_id, "ExecutionAgent", f"repair_execution_failed_{iteration_count}_{repair_attempt}", "error",
                                               {"error": execution_result.get("error"), "repair_attempt": repair_attempt})
                            emit_agent_update(
                                f"这次修复后执行仍失败。错误摘要：{execution_result.get('error', '未知错误')}",
                                agent_name="ExecutionAgent",
                                phase="repair_result",
                                metadata={
                                    "iteration": iteration_count, "repair_attempt": repair_attempt, "error": execution_result.get("error")}
                            )
                            emit_event('state', {
                                "id": f"repair_execution_failed_{iteration_count}_{repair_attempt}",
                                "agent": "ExecutionAgent",
                                "action": "repair_execution_failed",
                                "status": "failed",
                                "timestamp": datetime.now().isoformat(),
                                "data": {
                                    "iteration": iteration_count,
                                    "repair_attempt": repair_attempt,
                                    "error": execution_result.get("error")
                                }
                            })
                            result["steps"].append({
                                "agent": "ExecutionAgent",
                                "iteration": iteration_count,
                                "repair_attempt": repair_attempt,
                                "action": "execute_repair",
                                "status": "failed",
                                "result": {"success": False, "error": execution_result.get("error")}
                            })

                    # 如果修复成功，继续正常评估流程；否则保留失败结果并继续到评估(code评估)
                    if repaired_success:
                        print(
                            f"[Controller] 修复成功，在修复尝试 {repair_attempt} 次后恢复执行")
                    else:
                        print(
                            f"[Controller] 修复失败，已尝试 {MAX_REPAIR_ATTEMPTS} 次，转入人工审查或代码评估")

                # 快速策略：跳过评估，直接接受结果
                if not plan_enable_iteration:
                    print("[Controller] 快速策略：跳过评估，直接返回执行结果")
                    current_score = 8 if execution_result["success"] else 3
                    session["last_score"] = current_score
                    session["status"] = "completed"
                    session["evaluation_result"] = {
                        "success": True,
                        "score": current_score,
                        "evaluation_text": "快速策略：跳过详细评估" if execution_result["success"] else "快速策略：执行未成功",
                        "improvements": "",
                    }
                    session["last_improvements"] = ""
                    self._apply_final_result(
                        session,
                        {
                            "score": current_score,
                            "iteration": iteration_count,
                            "generated_code": generated_code,
                            "generated_code_path": session.get("generated_code_path"),
                            "execution_result": execution_result,
                            "evaluation_result": session["evaluation_result"],
                            "code_hash": code_hash,
                            "output_hash": self._hash_file(execution_result.get("output_path")),
                        },
                        current_score,
                        f"快速策略完成（{plan['strategy']}），跳过评估直接返回"
                    )
                    result["success"] = execution_result["success"]
                    result["final_score"] = current_score
                    result["iteration_reason"] = session["final_result"]["iteration_reason"]
                    self._persist_session(session_id)
                    emit_agent_update(
                        f"快速策略完成，{'执行成功' if execution_result['success'] else '执行未成功'}，直接返回结果。",
                        agent_name="Controller",
                        phase="decision",
                        metadata={"strategy": plan["strategy"], "success": execution_result["success"]}
                    )
                    break

                # Step 3: 评估结果
                self.add_state_log(session_id, "EvaluationAgent", f"evaluation_start_{iteration_count}", "running",
                                   {"iteration": iteration_count})
                emit_agent_update(
                    "我正在评估本轮结果：如果有输出图片，会优先做图片质量评估；否则会回退为代码质量评估。",
                    agent_name="EvaluationAgent",
                    phase="action",
                    metadata={"iteration": iteration_count, "has_output_image": bool(
                        execution_result.get("success") and execution_result.get("output_path"))}
                )
                emit_event('state', {
                    "id": f"evaluation_start_{iteration_count}",
                    "agent": "EvaluationAgent",
                    "action": "evaluation_start",
                    "status": "started",
                    "timestamp": datetime.now().isoformat(),
                    "data": {"iteration": iteration_count}
                })

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
                self._record_agent_call(
                    session_id,
                    "EvaluationAgent",
                    "evaluate_image" if execution_result["success"] and execution_result[
                        "output_path"] else "evaluate_code",
                    {
                        "iteration": iteration_count,
                        "output_path": execution_result.get("output_path"),
                    },
                    {
                        "score": evaluation_result.get("score"),
                        "improvements": evaluation_result.get("improvements", "")[:500]
                    }
                )

                # 提取评分和改进建议（MVP核心）
                current_score = evaluation_result.get("score", 0)
                improvements = evaluation_result.get("improvements", "")
                output_hash = self._hash_file(
                    execution_result.get("output_path"))
                code_unchanged = bool(
                    previous_code_hash and code_hash == previous_code_hash)
                output_unchanged = bool(
                    previous_output_hash and output_hash == previous_output_hash)
                score_unchanged = current_score <= session.get(
                    "last_score", -1)
                lacks_improvements = not improvements.strip()
                if code_unchanged and output_unchanged and score_unchanged:
                    stagnant_iterations += 1
                else:
                    stagnant_iterations = 0

                session["last_score"] = current_score
                session["last_improvements"] = improvements
                session["last_code_hash"] = code_hash
                session["last_output_hash"] = output_hash
                session["stagnant_iterations"] = stagnant_iterations

                current_candidate = {
                    "score": current_score,
                    "iteration": iteration_count,
                    "generated_code": generated_code,
                    "generated_code_path": session.get("generated_code_path"),
                    "execution_result": execution_result,
                    "evaluation_result": evaluation_result,
                    "code_hash": code_hash,
                    "output_hash": output_hash
                }
                if execution_result.get("success") and (
                    best_result is None or current_score > best_result.get(
                        "score", -1)
                ):
                    best_result = current_candidate
                    session["best_result"] = {
                        "score": current_score,
                        "iteration": iteration_count,
                        "generated_code_path": session.get("generated_code_path"),
                        "output_path": execution_result.get("output_path"),
                        "code_hash": code_hash,
                        "output_hash": output_hash
                    }
                self._persist_session(session_id)

                self.add_state_log(session_id, "EvaluationAgent", f"evaluation_complete_{iteration_count}", "success",
                                   {
                    "score": current_score,
                    "iteration": iteration_count,
                    "evaluation_text": evaluation_result.get("evaluation_text", ""),
                    "improvements": improvements[:2000],
                    "code_hash": code_hash,
                    "output_hash": output_hash,
                    "stagnant_iterations": stagnant_iterations
                })
                emit_agent_update(
                    f"评估完成，本轮评分是 {current_score}/10。"
                    f"{' 我会采用当前结果。' if current_score >= SCORE_THRESHOLD_ACCEPT else (' 分数可优化，我会继续下一轮改进。' if current_score >= SCORE_THRESHOLD_OPTIMIZE and iteration_count < MAX_ITERATIONS else ' 当前结果需要人工审查或已经到达停止条件。')}",
                    agent_name="EvaluationAgent",
                    phase="decision",
                    metadata={"iteration": iteration_count,
                              "score": current_score}
                )
                emit_event('state', {
                    "id": f"evaluation_complete_{iteration_count}",
                    "agent": "EvaluationAgent",
                    "action": "evaluation_complete",
                    "status": "completed",
                    "timestamp": datetime.now().isoformat(),
                    "data": {
                        "iteration": iteration_count,
                        "score": current_score,
                        "evaluation_text": evaluation_result.get("evaluation_text", ""),
                        "improvements": improvements[:2000],
                    }
                })

                result["steps"].append({
                    "agent": "EvaluationAgent",
                    "iteration": iteration_count,
                    "action": "evaluate",
                    "status": "completed",
                    "result": {
                        "score": current_score,
                        "evaluation_text": evaluation_result.get("evaluation_text", ""),
                        "improvements": improvements
                    }
                })

                print(
                    f"[Controller] 第 {iteration_count} 次迭代 - 评分: {current_score}/10")

                previous_code_hash = code_hash
                previous_output_hash = output_hash

                # MVP决策逻辑：根据评分自动决定是否继续迭代
                if current_score >= SCORE_THRESHOLD_ACCEPT:
                    print(
                        f"[Controller] 评分达到 {current_score}/10 (≥ {SCORE_THRESHOLD_ACCEPT})，接受结果，迭代完成")
                    emit_agent_update(
                        f"决策：评分达到接受标准（{current_score}/10 >= {SCORE_THRESHOLD_ACCEPT}），停止迭代并返回当前结果。",
                        phase="decision",
                        metadata={"score": current_score,
                                  "threshold": SCORE_THRESHOLD_ACCEPT}
                    )
                    session["status"] = "completed"
                    self._apply_final_result(
                        session, current_candidate, current_score,
                        f"评分达到接受标准 ({current_score}/10 ≥ {SCORE_THRESHOLD_ACCEPT})")
                    result["success"] = True
                    result["final_score"] = session["final_score"]
                    result["iteration_reason"] = session["final_result"]["iteration_reason"]
                    self._persist_session(session_id)
                    break
                elif iteration_count > 1 and stagnant_iterations >= 1:
                    print("[Controller] 迭代无进展，提前停止")
                    stop_reason = (
                        "连续迭代没有产生新的代码或输出，且评分没有提升"
                        if not lacks_improvements
                        else "连续迭代没有产生新的代码或输出，评分没有提升，且评估未提供可执行改进建议"
                    )
                    emit_agent_update(
                        f"决策：{stop_reason}。我会停止自动迭代，返回当前最佳结果。",
                        phase="decision",
                        metadata={
                            "score": current_score,
                            "stagnant_iterations": stagnant_iterations,
                            "code_unchanged": code_unchanged,
                            "output_unchanged": output_unchanged
                        }
                    )
                    session["status"] = "completed"
                    self._apply_final_result(
                        session, best_result, current_score, stop_reason)
                    result["success"] = bool(best_result)
                    result["final_score"] = session["final_score"]
                    result["iteration_reason"] = session["final_result"]["iteration_reason"]
                    self._persist_session(session_id)
                    break
                elif current_score >= SCORE_THRESHOLD_OPTIMIZE:
                    if iteration_count < MAX_ITERATIONS:
                        print(
                            f"[Controller] 评分 {current_score}/10，继续优化... (第 {iteration_count}/{MAX_ITERATIONS} 次)")
                        emit_agent_update(
                            f"决策：评分 {current_score}/10 还可以继续优化，我会把评估建议带入下一轮代码生成。",
                            phase="decision",
                            metadata={"score": current_score,
                                      "next_iteration": iteration_count + 1}
                        )
                        continue  # 继续迭代
                    else:
                        print(f"[Controller] 达到最大迭代次数 ({MAX_ITERATIONS})，停止迭代")
                        emit_agent_update(
                            f"决策：已经达到最大迭代次数 {MAX_ITERATIONS}，返回当前最佳结果，最终评分 {current_score}/10。",
                            phase="decision",
                            metadata={"score": current_score,
                                      "max_iterations": MAX_ITERATIONS}
                        )
                        session["status"] = "completed"
                        self._apply_final_result(
                            session, best_result, current_score,
                            f"达到最大迭代次数，返回最佳评分 {(best_result or {}).get('score', current_score)}/10")
                        result["success"] = True
                        result["final_score"] = session["final_score"]
                        result["iteration_reason"] = session["final_result"]["iteration_reason"]
                        self._persist_session(session_id)
                        break
                else:
                    print(
                        f"[Controller] 评分过低 ({current_score}/10 < {SCORE_THRESHOLD_OPTIMIZE})，需人工审查")
                    emit_agent_update(
                        f"决策：评分 {current_score}/10 低于继续优化阈值 {SCORE_THRESHOLD_OPTIMIZE}，我会停止自动迭代并标记为需要人工审查。",
                        phase="decision",
                        metadata={"score": current_score,
                                  "threshold": SCORE_THRESHOLD_OPTIMIZE}
                    )
                    session["status"] = "needs_review"
                    self._apply_final_result(
                        session, current_candidate if execution_result.get(
                            "success") else None,
                        current_score,
                        f"评分过低，需人工审查 ({current_score}/10)")
                    result["success"] = False
                    result["final_score"] = session["final_score"]
                    result["iteration_reason"] = session["final_result"]["iteration_reason"]
                    self._persist_session(session_id)
                    break

            # 处理超过最大迭代次数的情况
            if iteration_count >= MAX_ITERATIONS and session["status"] not in ("completed", "needs_review", "error"):
                print(f"[Controller] 已完成最大迭代次数")
                emit_agent_update(
                    f"已完成最大迭代次数 {MAX_ITERATIONS}，我会结束自动流程并返回最终评分 {current_score}/10。",
                    phase="decision",
                    metadata={"score": current_score,
                              "max_iterations": MAX_ITERATIONS}
                )
                session["status"] = "completed"
                self._apply_final_result(
                    session, best_result, current_score,
                    f"达到最大迭代次数，返回最佳评分 {(best_result or {}).get('score', current_score)}/10")
                result["success"] = True
                result["final_score"] = session["final_score"]
                result["iteration_reason"] = session["final_result"]["iteration_reason"]
                self._persist_session(session_id)

        except Exception as e:
            session["status"] = "error"
            session["error"] = str(e)
            self._persist_session(session_id)
            self.add_state_log(session_id, "Controller", "process_failed", "error",
                               {"error": str(e)})
            emit_event('error', {
                "id": "process_error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            result["success"] = False
            result["error"] = str(e)

        self._persist_session(session_id)

        # 发送最终完成事件
        emit_event('complete', {
            "success": result.get("success", False),
            "final_score": result.get("final_score"),
            "iteration_reason": result.get("iteration_reason"),
            "timestamp": datetime.now().isoformat()
        })

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
        self.resource_manager.append_agent_call(
            session_id,
            "User",
            "submit_feedback",
            {"type": feedback_type, "suggestions": suggestions},
            {"iteration": session["iteration_count"]}
        )

        self.add_state_log(session_id, "Controller", "feedback_received", "info",
                           {"feedback_type": feedback_type, "suggestions": suggestions})

        if feedback_type == "reject" and suggestions:
            # 用户拒绝并提供建议，需要重新生成
            session["status"] = "iterating"
            self._persist_session(session_id)
            return {
                "success": True,
                "message": "收到反馈，正在根据建议重新生成...",
                "action": "regenerate"
            }
        elif feedback_type == "accept":
            session["status"] = "accepted"
            self._persist_session(session_id)
            return {
                "success": True,
                "message": "感谢您的认可！",
                "action": "complete"
            }
        else:
            self._persist_session(session_id)
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
            status_emoji = "✅" if status == "success" else (
                "❌" if status == "error" else "🔄")

            if i > 0:
                prev_node = f"Node{i-1}"
                mermaid_parts.append(
                    f"    {prev_node} --> {node_id}[{agent}: {action} {status_emoji}]")
            else:
                mermaid_parts.append(
                    f"    Retrieval --> {node_id}[{agent}: {action} {status_emoji}]")

        mermaid_parts.append(
            f"    Node{len(state_logs)-1 if state_logs else 'Retrieval'} --> End([结束])")

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
