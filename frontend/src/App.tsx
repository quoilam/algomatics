import React, { useEffect } from 'react';
import { useChatStore } from './store';
import { sendChatMessageStream, sendChatWithImage, createSession as createBackendSession, getSessionDetails, listSessions } from './api';
import type { Message, StateLog } from './types';

import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import InputArea from './components/InputArea';

import './App.css';

const readFileAsDataUrl = (file: File): Promise<string> => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result || ''));
  reader.onerror = () => reject(reader.error || new Error('读取图片失败'));
  reader.readAsDataURL(file);
});

const generateMessageId = () => 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

const normalizeMessageTimestamp = (timestamp: unknown) => {
  if (typeof timestamp === 'number') {
    return timestamp;
  }

  if (typeof timestamp === 'string') {
    return Date.parse(timestamp) || Date.now();
  }

  return Date.now();
};

const App: React.FC = () => {
  const currentSessionId = useChatStore(state => state.currentSessionId);
  const isLoading = useChatStore(state => state.isLoading);
  
  const setIsLoading = useChatStore(state => state.setIsLoading);
  const addMessage = useChatStore(state => state.addMessage);
  const updateMessage = useChatStore(state => state.updateMessage);
  const addStateLog = useChatStore(state => state.addStateLog);
  const clearStateLogs = useChatStore(state => state.clearStateLogs);
  const setSessionStatus = useChatStore(state => state.setSessionStatus);
  const createSessionLocal = useChatStore(state => state.createSession);
  const replaceSessions = useChatStore(state => state.replaceSessions);
  const hydrateSessionFromBackend = useChatStore(state => state.hydrateSessionFromBackend);

  // 初始化：从后端加载会话列表和当前会话消息
  useEffect(() => {
    let cancelled = false;

    const bootstrapSessions = async () => {
      try {
        const response = await listSessions();
        if (cancelled) {
          return;
        }

        if (response.success && response.sessions.length > 0) {
          const backendSessions = response.sessions.map(session => ({
            id: session.session_id,
            title: session.title || session.user_request?.slice(0, 24) || `对话 ${new Date(session.created_at).toLocaleTimeString()}`,
            createdAt: session.created_at,
            updatedAt: session.updated_at,
            messages: [],
            status: session.status,
            iterationCount: session.iteration_count || 0,
            userRequest: session.user_request || undefined,
            finalResponse: session.final_response || undefined,
            messageCount: session.message_count || 0,
          }));

          const currentSessionId = useChatStore.getState().currentSessionId;
          const resolvedCurrentSessionId = currentSessionId && backendSessions.some(session => session.id === currentSessionId)
            ? currentSessionId
            : backendSessions[0].id;

          replaceSessions(backendSessions, resolvedCurrentSessionId);

          const activeSessionId = resolvedCurrentSessionId || backendSessions[0].id;
          if (activeSessionId) {
            const sessionDetails = await getSessionDetails(activeSessionId);
            if (!cancelled) {
              hydrateSessionFromBackend(sessionDetails);
            }
          }
          return;
        }

        // 没有现成会话，创建一个
        const backendSessionId = await createBackendSession();
        if (cancelled) {
          return;
        }

        createSessionLocal('新对话', backendSessionId);
        const sessionDetails = await getSessionDetails(backendSessionId);
        if (!cancelled) {
          hydrateSessionFromBackend(sessionDetails);
        }
      } catch (error) {
        console.error('Failed to bootstrap backend sessions:', error);
      }
    };

    void bootstrapSessions();

    return () => {
      cancelled = true;
    };
  }, []);

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K 创建新会话
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        void (async () => {
          try {
            const backendSessionId = await createBackendSession();
            createSessionLocal('新对话', backendSessionId);
            const sessionDetails = await getSessionDetails(backendSessionId);
            hydrateSessionFromBackend(sessionDetails);
          } catch (error) {
            console.error('Failed to create session:', error);
          }
        })();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSendMessage = async (message: string, enableSearch: boolean, file?: File) => {
    if (!currentSessionId) {
      alert('请先创建或选择一个对话');
      return;
    }

    const imageUrl = file ? await readFileAsDataUrl(file) : null;

    // 添加用户消息
    const userMessage: Message = {
      id: generateMessageId(),
      role: 'user',
      content: message || (file ? `[上传图片: ${file.name}]` : ''),
      timestamp: Date.now(),
      status: 'sent',
      imageUrl,
      metadata: file ? {
        filename: file.name,
        size: file.size,
        type: file.type,
      } : undefined,
    };
    addMessage(userMessage);

    const assistantMessageId = generateMessageId();

    setIsLoading(true);
    clearStateLogs();
    setSessionStatus('processing');

    try {
      let assistantContent = '';
      let assistantMessageCreated = false;

      const upsertStreamMessage = (streamMessage: Message) => {
        const exists = useChatStore.getState().messages.some(item => item.id === streamMessage.id);
        if (exists) {
          updateMessage(streamMessage.id, streamMessage);
        } else {
          addMessage(streamMessage);
        }
      };

      const handleStreamMessage = (data: any) => {
        if (data && typeof data === 'object') {
          const content = data.content || data.text || data.delta || data.message || '';
          if (!content) {
            return;
          }

          const metadata = data.metadata || {};
          if (metadata.kind === 'agent_update') {
            upsertStreamMessage({
              id: data.id || generateMessageId(),
              role: (data.role || 'assistant') as Message['role'],
              content,
              timestamp: normalizeMessageTimestamp(data.timestamp),
              status: (data.status || 'complete') as Message['status'],
              metadata,
              sessionId: data.sessionId || currentSessionId,
            });
            return;
          }

          assistantContent += content;
        } else {
          assistantContent += String(data || '');
        }

        if (!assistantMessageCreated) {
          assistantMessageCreated = true;
          addMessage({
            id: assistantMessageId,
            role: 'assistant',
            content: assistantContent,
            timestamp: Date.now(),
            status: 'sending',
            streaming: true,
          });
          return;
        }

        updateMessage(assistantMessageId, {
          content: assistantContent,
          status: 'sending',
        });
      };

      const handleStateLog = (log: StateLog) => {
        addStateLog(log);
      };

      const handleStatus = (status: string) => {
        setSessionStatus(status as any);
      };

      const handleSessionId = (sessionId: string) => {
        if (sessionId && sessionId !== currentSessionId) {
          createSessionLocal('新对话', sessionId);
        }
      };

      const handleError = (error: string) => {
        console.error('Error:', error);
        const errorMessage: Partial<Message> = {
          content: assistantContent || `错误: ${error}`,
          status: 'error',
          streaming: false,
        };
        if (assistantMessageCreated) {
          updateMessage(assistantMessageId, errorMessage);
        } else {
          addMessage({
            id: assistantMessageId,
            role: 'assistant',
            content: errorMessage.content || `错误: ${error}`,
            timestamp: Date.now(),
            status: 'error',
            streaming: false,
          });
          assistantMessageCreated = true;
        }
        setSessionStatus('error');
        setIsLoading(false);
      };

      const handleComplete = (data?: any) => {
        if (data?.final_response && !assistantContent.includes(data.final_response)) {
          assistantContent += data.final_response;
        }
        if (!assistantContent && data?.iteration_reason) {
          assistantContent = data.iteration_reason;
        }
        setIsLoading(false);
        const completeMessage: Partial<Message> = {
          content: assistantContent || '处理完成',
          status: 'complete',
          streaming: false,
          outputImageUrl: data?.output_image_base64 || undefined,
        };
        if (assistantMessageCreated) {
          updateMessage(assistantMessageId, completeMessage);
        } else {
          addMessage({
            id: assistantMessageId,
            role: 'assistant',
            content: completeMessage.content || '处理完成',
            timestamp: Date.now(),
            status: 'complete',
            streaming: false,
            outputImageUrl: completeMessage.outputImageUrl,
          });
          assistantMessageCreated = true;
        }
      };

      // 发送消息
      if (file) {
        await sendChatWithImage(
          currentSessionId,
          message,
          file,
          enableSearch,
          handleStreamMessage,
          handleStateLog,
          handleStatus,
          handleError,
          handleComplete,
          handleSessionId,
        );
      } else {
        await sendChatMessageStream(
          currentSessionId,
          message,
          enableSearch,
          handleStreamMessage,
          handleStateLog,
          handleStatus,
          handleError,
          handleComplete,
          handleSessionId,
        );
      }
    } catch (error) {
      console.error('Send message failed:', error);
      setIsLoading(false);
      setSessionStatus('error');
    }
  };

  const handleCopyMessage = (content: string) => {
    navigator.clipboard.writeText(content).then(() => {
      // 可选：显示复制成功的提示
      console.log('Copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy:', err);
    });
  };

  return (
    <div className="app">
      <Sidebar />
      
      <div className="main-content">
        <div className="chat-area">
          <ChatWindow onCopy={handleCopyMessage} />
        </div>
        
        <InputArea
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
};

export default App;
