"""
Flask Web API 服务
提供 RESTful API 供前端调用
"""

import os
import base64
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from controller.controller import ControllerAgent

app = Flask(__name__, 
            template_folder='../frontend/templates',
            static_folder='../frontend/static')

# 配置上传文件夹
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 最大 16MB

# 初始化控制器
controller = ControllerAgent()

# 存储当前会话 ID (简化实现，实际应该用 session 或数据库)
current_sessions = {}


@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/api/session/create', methods=['POST'])
def create_session():
    """创建新会话"""
    user_id = request.json.get('user_id', 'default')
    session_id = controller.create_session(user_id)
    current_sessions[user_id] = session_id
    return jsonify({
        'success': True,
        'session_id': session_id
    })


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """获取会话状态"""
    summary = controller.get_session_summary(session_id)
    return jsonify(summary)


@app.route('/api/process', methods=['POST'])
def process_request():
    """处理用户请求"""
    data = request.form if request.files else request.json
    
    session_id = data.get('session_id')
    user_request = data.get('request', '')
    enable_search = data.get('enable_search', 'true') in ['true', 'True', '1', True]
    
    if not session_id:
        # 创建新会话
        session_id = controller.create_session()
    
    # 处理上传的图片
    input_image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file.filename != '':
            filename = secure_filename(file.filename)
            input_image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(input_image_path)
    
    # 处理请求
    result = controller.process_user_request(
        session_id=session_id,
        user_request=user_request,
        input_image_path=input_image_path,
        enable_search=enable_search
    )
    
    # 如果有输出图片，进行 base64 编码
    if result.get('success') and result.get('steps'):
        for step in result['steps']:
            if step['agent'] == 'ExecutionAgent' and step['result'].get('output_path'):
                output_path = step['result']['output_path']
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        image_data = base64.b64encode(f.read()).decode('utf-8')
                    step['result']['output_image_base64'] = f"data:image/png;base64,{image_data}"
    
    return jsonify(result)


@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """提交用户反馈"""
    data = request.json
    session_id = data.get('session_id')
    feedback_type = data.get('type')  # 'accept' or 'reject'
    suggestions = data.get('suggestions', '')
    
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
            result['new_result'] = process_result
    
    return jsonify(result)


@app.route('/api/state-diagram/<session_id>', methods=['GET'])
def get_state_diagram(session_id):
    """获取状态流程图"""
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
        histories.append({
            'session_id': session_id,
            'created_at': session['created_at'],
            'user_request': session['user_request'],
            'status': session['status'],
            'iteration_count': session['iteration_count']
        })
    
    # 按创建时间排序
    histories.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({
        'success': True,
        'histories': histories
    })


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """提供上传文件的访问"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/output_images/<filename>')
def output_file(filename):
    """提供输出图片的访问"""
    return send_from_directory('output_images', filename)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5008)
