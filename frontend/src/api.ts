/**
 * API 和 SSE 流处理
 */

import type { StreamMessage, ChatResponse, SessionResponse, StateLog } from './types';

const API_BASE = '/api';

/**
 * 发送聊天消息并处理 SSE 流式响应
 */
export async function sendChatMessageStream(
  sessionId: string,
  message: string,
  enableSearch: boolean,
  onMessage: (data: any) => void,
  onStateLog: (log: StateLog) => void,
  onStatus: (status: string) => void,
  onError: (error: string) => void,
  onComplete: () => void,
): Promise<void> {
  try {
    // 发送初始请求
    const response = await fetch(`${API_BASE}/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId || '',
        request: message,
        enable_search: enableSearch,
      }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const result: ChatResponse = await response.json();
    if (!result.success) {
      onError(result.error || '处理失败');
      return;
    }

    // 发出初始消息
    if (result.text) {
      onMessage(result.text);
    }

    // 开始轮询会话状态和日志
    const sessionId2 = result.session_id || sessionId;
    await pollSessionUpdates(
      sessionId2,
      onStateLog,
      onStatus,
      onError,
      onComplete,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误';
    onError(message);
  }
}

/**
 * 轮询会话状态和日志 (向后兼容现有后端)
 */
async function pollSessionUpdates(
  sessionId: string,
  onStateLog: (log: StateLog) => void,
  onStatus: (status: string) => void,
  onError: (error: string) => void,
  onComplete: () => void,
): Promise<void> {
  let lastLogCount = 0;
  const maxRetries = 60;
  let retryCount = 0;

  const poll = async () => {
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}`);
      if (!response.ok) {
        throw new Error(`Session API error: ${response.statusText}`);
      }

      const data: SessionResponse = await response.json();

      // 处理新的状态日志
      if (data.state_logs && data.state_logs.length > lastLogCount) {
        for (let i = lastLogCount; i < data.state_logs.length; i++) {
          onStateLog(data.state_logs[i]);
        }
        lastLogCount = data.state_logs.length;
        retryCount = 0; // 重置重试计数
      }

      // 更新状态
      if (data.status) {
        onStatus(data.status);

        // 检查是否完成
        const terminalStates = ['completed', 'accepted', 'needs_review', 'error'];
        if (terminalStates.includes(data.status)) {
          if (data.final_response) {
            onMessage(data.final_response);
          }
          onComplete();
          return;
        }
      }

      // 继续轮询
      if (retryCount < maxRetries) {
        retryCount++;
        setTimeout(poll, 900);
      } else {
        onError('轮询超时');
        onComplete();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '轮询错误';
      onError(message);
      onComplete();
    }
  };

  // 立即开始轮询
  setTimeout(poll, 500);
}

/**
 * 创建新会话
 */
export async function createSession(): Promise<string> {
  try {
    const response = await fetch(`${API_BASE}/session/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'web' }),
    });

    if (!response.ok) {
      throw new Error(`Create session error: ${response.statusText}`);
    }

    const data: ChatResponse = await response.json();
    if (data.success && data.session_id) {
      return data.session_id;
    }

    throw new Error(data.error || '创建会话失败');
  } catch (error) {
    console.error('Failed to create session:', error);
    throw error;
  }
}

/**
 * 获取会话详情
 */
export async function getSessionDetails(sessionId: string): Promise<SessionResponse> {
  try {
    const response = await fetch(`${API_BASE}/session/${sessionId}`);
    if (!response.ok) {
      throw new Error(`Get session error: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to get session details:', error);
    throw error;
  }
}

/**
 * 处理文件上传
 */
export async function sendChatWithImage(
  sessionId: string,
  message: string,
  file: File,
  enableSearch: boolean,
  onMessage: (data: any) => void,
  onStateLog: (log: StateLog) => void,
  onStatus: (status: string) => void,
  onError: (error: string) => void,
  onComplete: () => void,
): Promise<void> {
  try {
    const formData = new FormData();
    formData.append('image', file);
    formData.append('request', message);
    formData.append('session_id', sessionId || '');
    formData.append('enable_search', enableSearch ? 'true' : 'false');

    const response = await fetch(`${API_BASE}/process`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const result: ChatResponse = await response.json();
    if (!result.success) {
      onError(result.error || '处理失败');
      return;
    }

    if (result.text) {
      onMessage(result.text);
    }

    const sessionId2 = result.session_id || sessionId;
    await pollSessionUpdates(
      sessionId2,
      onStateLog,
      onStatus,
      onError,
      onComplete,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : '未知错误';
    onError(message);
  }
}
