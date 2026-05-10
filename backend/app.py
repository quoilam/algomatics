"""
Flask Web API 服务
提供 RESTful API 供前端调用
"""

import os
import base64
import mimetypes
import json
import threading
from datetime import datetime, timezone
from collections import defaultdict
from queue import Queue
from typing import Optional, Dict, List, Any

from flask import Flask, request, jsonify, send_from_directory, make_response, Response
from controller.controller import ControllerAgent
from dotenv import load_dotenv

load_dotenv()  # 加载环境变量

app = Flask(__name__)

# ============ SSE 事件队列和管理 ============


class EventQueueManager:
    """管理每个会话的SSE事件队列和订阅者"""

    def __init__(self):
        self.session_queues: Dict[str, Queue] = defaultdict(Queue)
        self.session_subscribers: Dict[str, List] = defaultdict(list)
        self.lock = threading.Lock()

    def ensure_queue(self, session_id: str) -> Queue:
        """确保会话有队列（提前创建，不等待订阅）"""
        with self.lock:
            if session_id not in self.session_queues:
                self.session_queues[session_id] = Queue(maxsize=100)
                print(
                    f"[EventQueueManager] Created queue for session {session_id}")
            return self.session_queues[session_id]

    def push_event(self, session_id: str, event_type: str, data: Any):
        """推送事件到会话队列"""
        with self.lock:
            # 确保队列存在
            if session_id not in self.session_queues:
                self.session_queues[session_id] = Queue(maxsize=100)
                print(
                    f"[EventQueueManager] Auto-created queue for session {session_id}")

            queue = self.session_queues[session_id]
            event = {'type': event_type, 'data': data, 'timestamp': _now_ms()}
            try:
                queue.put_nowait(event)
                print(
                    f"[EventQueueManager] Event pushed to queue for {session_id}: {event_type}")
            except Exception as e:
                print(
                    f"[EventQueueManager] Failed to push event for session {session_id}: {e}")

    def subscribe(self, session_id: str) -> Queue:
        """为会话创建/获取队列并返回给订阅者"""
        with self.lock:
            if session_id not in self.session_queues:
                self.session_queues[session_id] = Queue(maxsize=100)
                print(
                    f"[EventQueueManager] Created queue on subscribe for session {session_id}")
            return self.session_queues[session_id]

    def unsubscribe(self, session_id: str):
        """取消订阅（不删除队列，以便后续重新连接可以继续接收事件）"""
        with self.lock:
            # 保持队列以便后续的订阅者可以继续接收
            print(
                f"[EventQueueManager] Unsubscribed from session {session_id}")


event_queue_manager = EventQueueManager()

# 兼容旧资源目录；新资源统一放在 sessions/<session_id>/ 下
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('output_images', exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SESSION_RESOURCE_ROOT'] = 'sessions'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 最大 16MB

# 初始化控制器
controller = ControllerAgent()

# 存储当前会话 ID (简化实现，实际应该用 session 或数据库)
current_sessions = {}


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _to_ms(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        candidate = value.replace('Z', '+00:00')
        try:
            return int(datetime.fromisoformat(candidate).timestamp() * 1000)
        except ValueError:
            return _now_ms()
    return _now_ms()


def _bool_from_value(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _request_payload():
    if request.is_json:
        return request.get_json(silent=True) or {}
    if request.form:
        return request.form.to_dict(flat=True)
    return {}


def _session_exists(session_id: str) -> bool:
    return bool(session_id) and session_id in controller.sessions


def _ensure_session(session_id: str | None, user_id: str = 'web') -> str:
    if session_id and _session_exists(session_id):
        return session_id

    created_session_id = controller.create_session(user_id=user_id)
    current_sessions[user_id] = created_session_id
    return created_session_id


def _session_resources(session_id: str):
    session = controller.get_session(session_id) or {}
    resources = session.get('resources')
    if resources:
        return resources
    return controller.resource_manager.session_resource_payload(session_id)


def _normalize_session_status(status):
    if not status:
        return 'idle'

    status_text = str(status).strip().lower()
    mapping = {
        'initialized': 'idle',
        'processing': 'processing',
        'iterating': 'processing',
        'completed': 'completed',
        'accepted': 'accepted',
        'needs_review': 'needs_review',
        'error': 'error',
        'idle': 'idle',
    }
    return mapping.get(status_text, status_text)


def _normalize_log_status(status):
    if not status:
        return 'running'

    status_text = str(status).strip().lower()
    mapping = {
        'started': 'started',
        'running': 'running',
        'processing': 'running',
        'success': 'completed',
        'completed': 'completed',
        'finished': 'completed',
        'done': 'completed',
        'failed': 'failed',
        'error': 'failed',
        'paused': 'paused',
        'info': 'running',
        'warning': 'running',
    }
    return mapping.get(status_text, status_text)


def _encode_file_as_data_uri(file_path: str):
    if not file_path or not os.path.exists(file_path):
        return None

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type or not mime_type.startswith('image/'):
        mime_type = 'image/png'

    with open(file_path, 'rb') as file_handle:
        encoded = base64.b64encode(file_handle.read()).decode('utf-8')
    return f'data:{mime_type};base64,{encoded}'


def _render_state_logs(session):
    state_logs = []
    for index, log_entry in enumerate(session.get('state_logs', []) or []):
        data = dict(log_entry.get('data') or {})
        output_path = data.get('output_path')
        output_image_base64 = data.get('output_image_base64')

        if not output_image_base64 and output_path:
            output_image_base64 = _encode_file_as_data_uri(output_path)

        rendered_log = {
            'id': log_entry.get('id') or f'log_{index + 1}',
            'agent': log_entry.get('agent', 'Unknown'),
            'action': log_entry.get('action', 'unknown'),
            'status': _normalize_log_status(log_entry.get('status')),
            'timestamp': _to_ms(log_entry.get('timestamp')) or _now_ms(),
            'data': data,
        }

        if output_path:
            rendered_log['output_path'] = output_path
        if output_image_base64:
            rendered_log['output_image_base64'] = output_image_base64

        state_logs.append(rendered_log)

    return state_logs


def _enrich_state_event(data):
    if not isinstance(data, dict):
        return data

    enriched = dict(data)
    event_data = dict(enriched.get('data') or {})
    output_path = enriched.get('output_path') or event_data.get('output_path')
    input_image_path = enriched.get(
        'input_image_path') or event_data.get('input_image_path')

    if output_path:
        enriched['output_path'] = output_path
        event_data['output_path'] = output_path
        if not enriched.get('output_image_base64'):
            output_image_base64 = _encode_file_as_data_uri(output_path)
            if output_image_base64:
                enriched['output_image_base64'] = output_image_base64

    if input_image_path:
        enriched['input_image_path'] = input_image_path
        event_data['input_image_path'] = input_image_path
        if not enriched.get('input_image_base64'):
            input_image_base64 = _encode_file_as_data_uri(input_image_path)
            if input_image_base64:
                enriched['input_image_base64'] = input_image_base64

    enriched['data'] = event_data
    return enriched


def _render_messages(session_id: str, session):
    # Primary path: use canonical messages array
    msgs = session.get('messages')
    if msgs:
        return msgs

    # Fallback: synthesize from legacy fields for old sessions
    messages = []
    user_request = session.get('user_request')
    if user_request:
        messages.append({
            'id': f'{session_id}_user',
            'role': 'user',
            'content': user_request,
            'timestamp': _to_ms(session.get('created_at')) or _now_ms(),
        })

    for index, dialogue_entry in enumerate(session.get('agent_dialogue', []) or []):
        if not isinstance(dialogue_entry, dict):
            continue
        content = dialogue_entry.get('content')
        if not content:
            continue
        messages.append({
            'id': dialogue_entry.get('id') or f'{session_id}_agent_update_{index + 1}',
            'role': dialogue_entry.get('role') or 'assistant',
            'content': content,
            'timestamp': _to_ms(dialogue_entry.get('timestamp')) or _now_ms(),
            'status': 'complete',
            'metadata': dialogue_entry.get('metadata') or {'kind': 'agent_update'},
        })

    final_response = _build_final_response(session)
    if final_response:
        messages.append({
            'id': f'{session_id}_assistant',
            'role': 'assistant',
            'content': final_response,
            'timestamp': _now_ms(),
        })

    return messages


def _build_final_response(session):
    if not session:
        return None

    evaluation_result = session.get('evaluation_result') or {}
    execution_result = session.get('execution_result') or {}
    status = _normalize_session_status(session.get('status'))

    if evaluation_result.get('evaluation_text'):
        return evaluation_result.get('evaluation_text')

    if session.get('generated_code') and status in {'completed', 'accepted', 'needs_review'}:
        score = evaluation_result.get('score')
        if score is not None:
            return f'处理完成，评分 {score}/10'
        return '处理完成'

    if execution_result.get('error'):
        return execution_result.get('error')

    if session.get('error'):
        return session.get('error')

    return None


def _build_session_response(session_id: str):
    session = controller.get_session(session_id)
    if not session:
        return None

    state_logs = _render_state_logs(session)
    execution_result = session.get('execution_result') or {}
    output_path = execution_result.get(
        'output_path') if execution_result.get('success') else None
    output_image_base64 = _encode_file_as_data_uri(
        output_path) if output_path else None
    final_response = _build_final_response(session)

    current_agent = None
    current_action = None
    if state_logs:
        last_log = state_logs[-1]
        current_agent = last_log.get('agent')
        current_action = last_log.get('action')

    created_at_ms = _to_ms(session.get('created_at')) or _now_ms()
    updated_at_ms = state_logs[-1]['timestamp'] if state_logs else created_at_ms

    return {
        'success': True,
        'session_id': session_id,
        'title': session.get('title', ''),
        'status': _normalize_session_status(session.get('status')),
        'created_at': created_at_ms,
        'updated_at': updated_at_ms,
        'messages': _render_messages(session_id, session),
        'state_logs': state_logs,
        'current_agent': current_agent,
        'current_action': current_action,
        'output_image_base64': output_image_base64,
        'input_image_base64': _encode_file_as_data_uri(session.get('input_image')),
        'final_response': final_response,
        'user_request': session.get('user_request'),
        'iteration_count': session.get('iteration_count', 0),
        'feedback_history': session.get('feedback_history', []),
        'collaboration_log': session.get('collaboration_log', []),
        'kb_recommendations': session.get('kb_recommendations', []),
        'resources': session.get('resources'),
    }


def _attach_output_images(result):
    if not result or not result.get('steps'):
        return result

    for step in result['steps']:
        step_result = step.get('result')
        if not isinstance(step_result, dict):
            continue

        output_path = step_result.get('output_path')
        if output_path and os.path.exists(output_path) and not step_result.get('output_image_base64'):
            step_result['output_image_base64'] = _encode_file_as_data_uri(
                output_path)

    return result


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,PATCH,DELETE,OPTIONS'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response


@app.route('/api/<path:path>', methods=['OPTIONS'])
def api_options(path):
    return make_response('', 204)



@app.route('/api/session/create', methods=['POST'])
def create_session():
    """创建新会话"""
    payload = _request_payload()
    user_id = payload.get('user_id', 'default')
    title = payload.get('title', '')
    session_id = controller.create_session(user_id, title=title)
    current_sessions[user_id] = session_id
    created_at = _to_ms(controller.get_session(session_id).get('created_at'))
    return jsonify({
        'success': True,
        'session_id': session_id,
        'created_at': created_at,
        'title': controller.get_session(session_id).get('title', ''),
        'resources': controller.get_session(session_id).get('resources'),
        'message': '会话创建成功'
    })


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """获取会话状态"""
    summary = _build_session_response(session_id)
    if not summary:
        return jsonify({'success': False, 'error': 'Session not found'}), 404
    return jsonify(summary)


@app.route('/api/session/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除会话"""
    ok = controller.delete_session(session_id)
    if not ok:
        return jsonify({'success': False, 'error': 'Session not found'}), 404
    return jsonify({'success': True, 'message': '会话已删除'})


@app.route('/api/session/<session_id>', methods=['PATCH'])
def rename_session(session_id):
    """重命名会话"""
    payload = _request_payload()
    title = payload.get('title', '')
    if not title:
        return jsonify({'success': False, 'error': 'Missing title field'}), 400
    ok = controller.rename_session(session_id, title)
    if not ok:
        return jsonify({'success': False, 'error': 'Session not found'}), 404
    return jsonify({'success': True, 'message': '会话已重命名'})


@app.route('/api/stream', methods=['GET'])
def stream_events():
    """SSE 流事件端点，推送会话的实时事件"""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'error': 'Missing session_id'}), 400

    print(f"[SSE] Client connected for session: {session_id}")
    queue = event_queue_manager.subscribe(session_id)

    def event_generator():
        """生成SSE格式的事件流"""
        timeout_count = 0
        max_timeout = 300  # 5分钟后断开连接

        try:
            print(f"[SSE] Starting event stream for session: {session_id}")
            while True:
                try:
                    # 阻塞等待事件，超时为1秒
                    event = queue.get(timeout=1)
                    timeout_count = 0
                    print(
                        f"[SSE] Sending event to {session_id}: {event.get('type')}")
                    # 发送SSE格式的数据
                    yield f"data: {json.dumps(event)}\n\n"
                except:
                    # 队列超时，继续等待（心跳）
                    timeout_count += 1
                    if timeout_count > max_timeout:
                        # 连接超时，关闭流
                        print(
                            f"[SSE] Connection timeout for session: {session_id}")
                        break
                    # 可选：发送保活心跳
                    # yield ": keep-alive\n\n"
        except GeneratorExit:
            # 客户端断开连接
            print(f"[SSE] Client disconnected from session: {session_id}")
        finally:
            # 清理
            print(f"[SSE] Cleaning up session: {session_id}")
            event_queue_manager.unsubscribe(session_id)

    return Response(
        event_generator(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@app.route('/api/process', methods=['POST'])
def process_request():
    """处理用户请求"""
    payload = _request_payload()

    session_id = payload.get('session_id')
    user_request = payload.get('request', '') or ''
    enable_search = _bool_from_value(payload.get('enable_search'), True)
    user_id = payload.get('user_id', 'web')

    session_id = _ensure_session(session_id, user_id=user_id)

    # 提前为会话创建事件队列
    event_queue_manager.ensure_queue(session_id)
    print(f"[process_request] Created event queue for session {session_id}")

    input_image_path = None
    file = request.files.get('image')
    if file and file.filename:
        input_image_path = controller.resource_manager.build_unique_upload_path(
            session_id, file.filename, str(_now_ms()))
        file.save(input_image_path)
        session = controller.get_session(session_id)
        if session is not None:
            session['input_image'] = input_image_path
            session.setdefault('uploaded_files', []).append({
                'file_path': input_image_path,
                'filename': os.path.basename(input_image_path),
                'mime_type': file.mimetype,
                'file_size': os.path.getsize(input_image_path),
                'uploaded_at': datetime.now().isoformat(),
            })
            controller.resource_manager.append_agent_call(
                session_id,
                'User',
                'upload_input_image',
                {'filename': file.filename, 'mime_type': file.mimetype},
                {'file_path': input_image_path,
                    'file_size': os.path.getsize(input_image_path)}
            )
            controller.resource_manager.save_session_state(session_id, session)
    else:
        # 多轮对话：没有新图片时复用会话已有的 input_image
        session = controller.get_session(session_id)
        if session and session.get('input_image'):
            input_image_path = session['input_image']

    # 定义事件推送的回调函数
    def on_event(event_type: str, data: Any):
        """回调函数，由controller调用来推送事件到前端"""
        print(f"[app.process_request] on_event called: {event_type}")
        if event_type == 'state':
            data = _enrich_state_event(data)
        elif event_type == 'complete' and isinstance(data, dict):
            session = controller.get_session(session_id) or {}
            execution_result = session.get('execution_result') or {}
            output_path = execution_result.get(
                'output_path') if execution_result.get('success') else None
            data = {
                **data,
                'status': _normalize_session_status(session.get('status')),
                'final_response': _build_final_response(session),
                'output_image_base64': _encode_file_as_data_uri(output_path) if output_path else None,
            }
        event_queue_manager.push_event(session_id, event_type, data)

    if input_image_path:
        on_event('state', {
            'id': 'input_image',
            'agent': 'User',
            'action': 'input_image_uploaded',
            'status': 'completed',
            'timestamp': datetime.now().isoformat(),
            'data': {
                'filename': os.path.basename(input_image_path),
                'input_image_path': input_image_path,
            },
        })

    def run_processing():
        try:
            result = controller.process_user_request(
                session_id=session_id,
                user_request=user_request,
                input_image_path=input_image_path,
                enable_search=enable_search,
                on_event_callback=on_event
            )
            result = _attach_output_images(result)
            session = controller.get_session(session_id) or {}
            final_response = _build_final_response(session)

            # Append final assistant message to session messages
            if final_response and session is not None:
                msgs = session.setdefault('messages', [])
                if not any(m.get('content') == final_response for m in msgs):
                    msg_count = len(msgs)
                    msgs.append({
                        'id': f'{session_id}_assistant_{msg_count + 1}',
                        'role': 'assistant',
                        'content': final_response,
                        'timestamp': datetime.now().isoformat(),
                        'status': 'complete',
                    })
                    controller.resource_manager.save_session_state(
                        session_id, session)

            execution_result = session.get('execution_result') or {}
            output_path = execution_result.get(
                'output_path') if execution_result.get('success') else None
            event_queue_manager.push_event(session_id, 'message', {
                'content': final_response or result.get('iteration_reason') or '处理完成',
            })
            event_queue_manager.push_event(session_id, 'status', {
                'status': _normalize_session_status(session.get('status')),
            })
            event_queue_manager.push_event(session_id, 'complete', {
                'success': result.get('success', False),
                'final_score': result.get('final_score'),
                'iteration_reason': result.get('iteration_reason'),
                'final_response': final_response,
                'output_image_base64': _encode_file_as_data_uri(output_path) if output_path else None,
                'timestamp': datetime.now().isoformat(),
            })
        except Exception as exc:
            session = controller.get_session(session_id)
            if session is not None:
                session['status'] = 'error'
                session['error'] = str(exc)
                msgs = session.setdefault('messages', [])
                msgs.append({
                    'id': f'{session_id}_error_{len(msgs) + 1}',
                    'role': 'assistant',
                    'content': f'处理出错：{str(exc)}',
                    'timestamp': datetime.now().isoformat(),
                    'status': 'error',
                })
                controller.resource_manager.save_session_state(
                    session_id, session)
            event_queue_manager.push_event(session_id, 'error', {
                'error': str(exc),
                'timestamp': datetime.now().isoformat(),
            })
            event_queue_manager.push_event(session_id, 'complete', {
                'success': False,
                'error': str(exc),
                'timestamp': datetime.now().isoformat(),
            })

    threading.Thread(target=run_processing, daemon=True).start()

    response_payload = {
        'success': True,
        'session_id': session_id,
        'text': '',
        'status': 'processing',
        'message': '处理已开始',
    }

    return jsonify(response_payload), 202


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传文件"""
    payload = _request_payload()
    session_id = _ensure_session(payload.get(
        'session_id'), user_id=payload.get('user_id', 'web'))
    file = request.files.get('file')

    if not file or not file.filename:
        return jsonify({'success': False, 'error': '未找到上传文件'}), 400

    file_path = controller.resource_manager.build_upload_path(
        session_id, file.filename)
    file.save(file_path)
    session = controller.get_session(session_id)
    if session is not None:
        uploads = session.setdefault('uploaded_files', [])
        uploads.append({
            'file_path': file_path,
            'filename': os.path.basename(file_path),
            'mime_type': file.mimetype,
            'file_size': os.path.getsize(file_path),
            'uploaded_at': datetime.now().isoformat(),
        })
        controller.resource_manager.append_agent_call(
            session_id,
            'User',
            'upload_file',
            {'filename': file.filename, 'mime_type': file.mimetype},
            {'file_path': file_path, 'file_size': os.path.getsize(file_path)}
        )
        controller.resource_manager.save_session_state(session_id, session)

    return jsonify({
        'success': True,
        'session_id': session_id,
        'file_path': file_path,
        'file_size': os.path.getsize(file_path),
        'mime_type': file.mimetype,
    })


@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """提交用户反馈"""
    data = _request_payload()
    session_id = data.get('session_id')
    feedback_type = data.get('type')  # 'accept' or 'reject'
    suggestions = data.get('suggestions', '')

    if not session_id:
        return jsonify({'success': False, 'error': '缺少 session_id'}), 400

    if not _session_exists(session_id):
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    result = controller.submit_feedback(session_id, feedback_type, suggestions)

    # 如果是 reject 且有建议，自动触发重新生成
    if result.get('action') == 'regenerate':
        # 获取之前的请求信息
        session = controller.get_session(session_id)
        if session:
            # 重新处理请求（会使用新的反馈）
            process_result = controller.process_user_request(
                session_id=session_id,
                user_request=session['user_request'],
                input_image_path=session.get('input_image'),
                enable_search=False  # 重新生成时不需要再次搜索
            )
            result['new_result'] = _attach_output_images(process_result)

    return jsonify(result)


@app.route('/api/state-diagram/<session_id>', methods=['GET'])
def get_state_diagram(session_id):
    """获取状态流程图"""
    if not _session_exists(session_id):
        return jsonify({'success': False, 'error': 'Session not found'}), 404

    diagram = controller.get_state_diagram(session_id)
    return jsonify({
        'success': True,
        'diagram': diagram
    })


@app.route('/api/history', methods=['GET'])
def get_history():
    """获取聊天历史"""
    # 返回所有会话的摘要
    histories = []
    for session_id, session in controller.sessions.items():
        created_at_ms = _to_ms(session.get('created_at')) or _now_ms()
        updated_at_ms = created_at_ms
        if session.get('state_logs'):
            updated_at_ms = _to_ms(
                session['state_logs'][-1].get('timestamp')) or created_at_ms

        histories.append({
            'session_id': session_id,
            'created_at': created_at_ms,
            'updated_at': updated_at_ms,
            'title': session.get('title', ''),
            'user_request': session['user_request'],
            'status': _normalize_session_status(session['status']),
            'iteration_count': session['iteration_count'],
            'final_response': _build_final_response(session),
        })

    # 按创建时间排序
    histories.sort(key=lambda x: x['created_at'], reverse=True)

    return jsonify({
        'success': True,
        'histories': histories
    })


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """获取会话列表，可选按 user_id 过滤"""
    user_id = request.args.get('user_id')
    histories = []

    for session_id, session in controller.sessions.items():
        if user_id and session.get('user_id') != user_id:
            continue

        created_at_ms = _to_ms(session.get('created_at')) or _now_ms()
        histories.append({
            'session_id': session_id,
            'created_at': created_at_ms,
            'updated_at': _to_ms(session.get('state_logs', [{}])[-1].get('timestamp')) if session.get('state_logs') else created_at_ms,
            'title': session.get('title', ''),
            'status': _normalize_session_status(session.get('status')),
            'user_request': session.get('user_request'),
            'iteration_count': session.get('iteration_count', 0),
            'message_count': len(session.get('messages', [])),
        })

    histories.sort(key=lambda item: item['created_at'], reverse=True)
    return jsonify({'success': True, 'sessions': histories})


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """提供上传文件的访问"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/output_images/<filename>')
def output_file(filename):
    """提供输出图片的访问"""
    return send_from_directory('output_images', filename)


@app.route('/api/session/<session_id>/files/<area>/<filename>')
def session_resource_file(session_id, area, filename):
    """提供会话资源文件访问"""
    if area not in {'uploads', 'outputs', 'workspace'}:
        return jsonify({'success': False, 'error': 'Invalid file area'}), 400

    resources = _session_resources(session_id)
    directory = resources.get(area)
    if directory and os.path.exists(os.path.join(directory, filename)):
        return send_from_directory(directory, filename)

    return jsonify({'success': False, 'error': 'File not found'}), 404


@app.route('/api/session/<session_id>/output/<filename>')
def session_output_file(session_id, filename):
    """提供会话输出文件访问"""
    resources = _session_resources(session_id)
    session_output_dir = resources.get('outputs')
    if session_output_dir and os.path.exists(os.path.join(session_output_dir, filename)):
        return send_from_directory(session_output_dir, filename)

    session_upload_dir = resources.get('uploads')
    if session_upload_dir and os.path.exists(os.path.join(session_upload_dir, filename)):
        return send_from_directory(session_upload_dir, filename)

    session_output_dir = os.path.join('output_images')
    if os.path.exists(os.path.join(session_output_dir, filename)):
        return send_from_directory(session_output_dir, filename)

    session_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
    if os.path.exists(os.path.join(session_upload_dir, filename)):
        return send_from_directory(session_upload_dir, filename)

    return jsonify({'success': False, 'error': 'File not found'}), 404


@app.route('/api/knowledge/stats', methods=['GET'])
def knowledge_stats():
    """获取知识库统计信息"""
    try:
        stats = controller.knowledge_base.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/knowledge/recommend', methods=['POST'])
def knowledge_recommend():
    """查询知识库推荐方案"""
    payload = _request_payload()
    user_request = payload.get('request', '')
    task_type = payload.get('task_type', '')
    if not user_request:
        return jsonify({'success': False, 'error': 'Missing request field'}), 400
    try:
        recommendations = controller.knowledge_base.recommend(
            user_request, task_type=task_type)
        return jsonify({'success': True, 'recommendations': recommendations})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/knowledge/cleanup', methods=['POST'])
def knowledge_cleanup():
    """清理知识库中的过期条目"""
    payload = _request_payload()
    max_age_days = int(payload.get('max_age_days', 180))
    try:
        controller.knowledge_base.cleanup_stale(max_age_days=max_age_days)
        stats = controller.knowledge_base.get_stats()
        return jsonify({'success': True, 'message': f'清理完成（超过 {max_age_days} 天未使用的条目）', 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5008)
