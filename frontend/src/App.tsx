import React, { useEffect } from 'react';
import { useChatStore, generateIds } from './store';
import { sendChatMessageStream, sendChatWithImage, createSession as createBackendSession } from './api';
import type { Message, StateLog } from './types';

import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import StatePanel from './components/StatePanel';
import InputArea from './components/InputArea';

import './App.css';

const App: React.FC = () => {
  const currentSessionId = useChatStore(state => state.currentSessionId);
  const messages = useChatStore(state => state.messages);
  const isLoading = useChatStore(state => state.isLoading);
  
  const setIsLoading = useChatStore(state => state.setIsLoading);
  const addMessage = useChatStore(state => state.addMessage);
  const updateMessage = useChatStore(state => state.updateMessage);
  const addStateLog = useChatStore(state => state.addStateLog);
  const clearStateLogs = useChatStore(state => state.clearStateLogs);
  const setSessionStatus = useChatStore(state => state.setSessionStatus);
  const createSessionLocal = useChatStore(state => state.createSession);
  const loadFromLocalStorage = useChatStore(state => state.loadFromLocalStorage);

  // 初始化：加载本地存储的会话
  useEffect(() => {
    loadFromLocalStorage();

    // 如果没有会话，创建一个
    setTimeout(() => {
      const store = useChatStore.getState();
      if (!store.currentSessionId && store.sessions.length === 0) {
        createSessionLocal('新对话');
      }
    }, 100);
  }, []);

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+K 创建新会话
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        createSessionLocal('新对话');
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

    // 添加用户消息
    const userMessage: Message = {
      id: generateIds.message(),
      role: 'user',
      content: message || (file ? `[上传图片: ${file.name}]` : ''),
      timestamp: Date.now(),
      status: 'sent',
    };
    addMessage(userMessage);

    // 添加助手消息占位符
    const assistantMessageId = generateIds.message();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      status: 'sending',
      streaming: true,
    };
    addMessage(assistantMessage);

    setIsLoading(true);
    clearStateLogs();
    setSessionStatus('processing');

    try {
      let assistantContent = '';

      const handleStreamMessage = (data: string) => {
        assistantContent += data;
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

      const handleError = (error: string) => {
        console.error('Error:', error);
        updateMessage(assistantMessageId, {
          content: assistantContent || `错误: ${error}`,
          status: 'error',
        });
        setSessionStatus('error');
      };

      const handleComplete = () => {
        setIsLoading(false);
        updateMessage(assistantMessageId, {
          status: 'complete',
          streaming: false,
        });
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
          <StatePanel />
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
