/**
 * API 和 SSE 流处理
 */

import type {
  ChatResponse,
  SessionListResponse,
  SessionResponse,
  StateLog,
} from './types';

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5008').replace(/\/$/, '');
const API_BASE = `${API_ORIGIN}/api`;

interface StreamCallbacks {
  onMessage: (data: any) => void;
  onStateLog: (log: StateLog) => void;
  onStatus: (status: string) => void;
  onError: (error: string) => void;
  onComplete: (data?: any) => void;
}

const normalizeStateLog = (data: any): StateLog => {
  const logData = data?.data && typeof data.data === 'object' ? data.data : {};
  return {
    id: data?.id || `log_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    agent: data?.agent || logData.agent || 'Agent',
    action: data?.action || logData.action || 'update',
    status: data?.status || logData.status || 'running',
    timestamp: typeof data?.timestamp === 'number' ? data.timestamp : Date.parse(data?.timestamp || '') || Date.now(),
    data: logData,
    output_path: data?.output_path || logData.output_path,
    output_image_base64: data?.output_image_base64 || logData.output_image_base64,
    input_image_path: data?.input_image_path || logData.input_image_path,
    input_image_base64: data?.input_image_base64 || logData.input_image_base64,
  };
};

function openSessionStream(sessionId: string, callbacks: StreamCallbacks) {
  const sseUrl = `${API_BASE}/stream?session_id=${encodeURIComponent(sessionId)}`;
  console.log('[API] Connecting to SSE endpoint:', sseUrl);

  let completed = false;
  let pollingStarted = false;
  let es: EventSource | null = null;

  const startPollingFallback = () => {
    if (completed || pollingStarted) {
      return;
    }

    pollingStarted = true;
    void pollSessionUpdates(
      sessionId,
      callbacks.onMessage,
      callbacks.onStateLog,
      callbacks.onStatus,
      callbacks.onError,
      callbacks.onComplete,
    );
  };

  try {
    es = new EventSource(sseUrl);

    es.addEventListener('open', () => {
      console.log('[API] SSE connection opened');
    });

    es.addEventListener('message', (ev: MessageEvent) => {
      console.log('[API] SSE message received:', ev.data);
      try {
        const payload = JSON.parse(ev.data);
        const eventType = payload.type || payload.event || 'message';
        const data = payload.data || payload;

        switch (eventType) {
          case 'message':
            if (typeof data === 'string') {
              callbacks.onMessage(data);
            } else {
              callbacks.onMessage(data);
            }
            break;
          case 'state':
            callbacks.onStateLog(normalizeStateLog(data));
            break;
          case 'status':
            callbacks.onStatus(typeof data === 'string' ? data : data.status || data.value || '');
            break;
          case 'tool_call':
            callbacks.onStateLog(normalizeStateLog(data));
            break;
          case 'error':
            callbacks.onError(data?.error || JSON.stringify(data));
            break;
          case 'complete':
            completed = true;
            es?.close();
            if (data?.status) {
              callbacks.onStatus(data.status);
            }
            callbacks.onComplete(data);
            break;
          default:
            if (data && (data.content || data.text || data.delta || data.message)) {
              callbacks.onMessage(data.content || data.text || data.delta || data.message);
            }
            break;
        }
      } catch (err) {
        console.error('Failed to parse SSE message', err);
      }
    });

    es.addEventListener('error', (err) => {
      console.warn('SSE connection error', err);
      if (completed) {
        return;
      }

      try {
        es?.close();
      } catch (closeError) {
        console.warn('Failed to close SSE connection', closeError);
      }

      startPollingFallback();
    });
  } catch (error) {
    console.warn('Failed to create SSE connection, falling back to polling', error);
    startPollingFallback();
  }

  return {
    close: () => {
      completed = true;
      try {
        es?.close();
      } catch (error) {
        console.warn('Failed to close SSE connection', error);
      }
    },
  };
}

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
  onComplete: (data?: any) => void,
  onSessionId?: (sessionId: string) => void,
): Promise<void> {
  let stream: { close: () => void } | null = null;

  try {
    stream = openSessionStream(sessionId, {
      onMessage,
      onStateLog,
      onStatus,
      onError,
      onComplete,
    });

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
      stream.close();
      return;
    }

    if (result.session_id && result.session_id !== sessionId) {
      // 后端分配了新会话ID，关闭旧SSE流并重新连接到正确会话
      stream.close();
      stream = openSessionStream(result.session_id, {
        onMessage,
        onStateLog,
        onStatus,
        onError,
        onComplete,
      });
      onSessionId?.(result.session_id);
    }

    if (result.text) {
      onMessage(result.text);
    }
  } catch (error) {
    stream?.close();
    const message = error instanceof Error ? error.message : '未知错误';
    onError(message);
  }
}

/**
 * 轮询会话状态和日志 (向后兼容现有后端)
 */
async function pollSessionUpdates(
  sessionId: string,
  onMessage: (data: any) => void,
  onStateLog: (log: StateLog) => void,
  onStatus: (status: string) => void,
  onError: (error: string) => void,
  onComplete: (data?: any) => void,
): Promise<void> {
  let lastLogCount = 0;
  let lastMessageCount = 0;
  const maxRetries = 60;
  let retryCount = 0;

  const poll = async () => {
    try {
      const response = await fetch(`${API_BASE}/session/${sessionId}`);
      if (!response.ok) {
        throw new Error(`Session API error: ${response.statusText}`);
      }

      const data: SessionResponse = await response.json();

      // 处理新的 agent_update 消息（从 agent_dialogue 渲染而来）
      if (data.messages && data.messages.length > lastMessageCount) {
        for (let i = lastMessageCount; i < data.messages.length; i++) {
          const msg = data.messages[i];
          if (msg.metadata?.kind === 'agent_update' && msg.content) {
            onMessage(msg);
          }
        }
        lastMessageCount = data.messages.length;
        retryCount = 0;
      }

      // 处理新的状态日志
      if (data.state_logs && data.state_logs.length > lastLogCount) {
        for (let i = lastLogCount; i < data.state_logs.length; i++) {
          onStateLog(data.state_logs[i]);
        }
        lastLogCount = data.state_logs.length;
        retryCount = 0;
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
 * 删除会话
 */
export async function deleteSession(sessionId: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`Delete session error: ${response.statusText}`);
    }
    return true;
  } catch (error) {
    console.error('Failed to delete session:', error);
    return false;
  }
}

/**
 * 重命名会话
 */
export async function renameSession(sessionId: string, title: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/session/${encodeURIComponent(sessionId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title }),
    });
    if (!response.ok) {
      throw new Error(`Rename session error: ${response.statusText}`);
    }
    return true;
  } catch (error) {
    console.error('Failed to rename session:', error);
    return false;
  }
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
 * 获取会话列表
 */
export async function listSessions(): Promise<SessionListResponse> {
  try {
    const response = await fetch(`${API_BASE}/sessions`);
    if (!response.ok) {
      throw new Error(`List sessions error: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Failed to list sessions:', error);
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
  onComplete: (data?: any) => void,
  onSessionId?: (sessionId: string) => void,
): Promise<void> {
  let stream: { close: () => void } | null = null;

  try {
    stream = openSessionStream(sessionId, {
      onMessage,
      onStateLog,
      onStatus,
      onError,
      onComplete,
    });

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
      stream.close();
      return;
    }

    if (result.session_id && result.session_id !== sessionId) {
      // 后端分配了新会话ID，关闭旧SSE流并重新连接到正确会话
      stream.close();
      stream = openSessionStream(result.session_id, {
        onMessage,
        onStateLog,
        onStatus,
        onError,
        onComplete,
      });
      onSessionId?.(result.session_id);
    }

    if (result.text) {
      onMessage(result.text);
    }
  } catch (error) {
    stream?.close();
    const message = error instanceof Error ? error.message : '未知错误';
    onError(message);
  }
}
