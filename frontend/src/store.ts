/**
 * Zustand 状态管理 Store
 */

import { create } from 'zustand';
import type { Message, Session, StateLog, ViewMode, SessionStatus } from './types';

interface ChatStore {
  // 会话管理
  sessions: Session[];
  currentSessionId: string | null;
  
  // 当前会话数据
  messages: Message[];
  stateLogs: StateLog[];
  sessionStatus: SessionStatus;
  
  // UI 状态
  viewMode: ViewMode;
  isLoading: boolean;
  
  // 操作方法
  setCurrentSession: (sessionId: string) => void;
  createSession: (title: string) => string;
  deleteSession: (sessionId: string) => void;
  renameSession: (sessionId: string, newTitle: string) => void;
  
  addMessage: (message: Message) => void;
  updateMessage: (messageId: string, updates: Partial<Message>) => void;
  clearMessages: () => void;
  
  addStateLog: (log: StateLog) => void;
  clearStateLogs: () => void;
  
  setSessionStatus: (status: SessionStatus) => void;
  setIsLoading: (loading: boolean) => void;
  setViewMode: (mode: ViewMode) => void;
  
  // 存储相关
  saveToLocalStorage: () => void;
  loadFromLocalStorage: () => void;
}

const STORAGE_KEY = 'agent-chat-sessions';
const MAX_SESSIONS = 20;

// 生成会话ID
const generateSessionId = () => 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

// 生成消息ID
const generateMessageId = () => 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

// 生成日志ID
const generateLogId = () => 'log_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

export const useChatStore = create<ChatStore>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  stateLogs: [],
  sessionStatus: 'idle',
  viewMode: 'detailed',
  isLoading: false,

  setCurrentSession: (sessionId) => {
    const store = get();
    const session = store.sessions.find(s => s.id === sessionId);
    if (session) {
      set({
        currentSessionId: sessionId,
        messages: [...session.messages],
        stateLogs: [],
        sessionStatus: session.status,
      });
    }
  },

  createSession: (title) => {
    const store = get();
    const sessionId = generateSessionId();
    const newSession: Session = {
      id: sessionId,
      title: title || `对话 ${new Date().toLocaleTimeString()}`,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: [],
      status: 'idle',
    };

    const sessions = [newSession, ...store.sessions].slice(0, MAX_SESSIONS);
    set({
      sessions,
      currentSessionId: sessionId,
      messages: [],
      stateLogs: [],
      sessionStatus: 'idle',
    });

    // 自动保存到 LocalStorage
    setTimeout(() => get().saveToLocalStorage(), 100);
    return sessionId;
  },

  deleteSession: (sessionId) => {
    const store = get();
    const sessions = store.sessions.filter(s => s.id !== sessionId);
    const isDeleted = sessionId === store.currentSessionId;
    
    set({
      sessions,
      currentSessionId: isDeleted ? (sessions[0]?.id || null) : store.currentSessionId,
      messages: isDeleted ? [] : store.messages,
      stateLogs: isDeleted ? [] : store.stateLogs,
    });
    
    get().saveToLocalStorage();
  },

  renameSession: (sessionId, newTitle) => {
    const store = get();
    const sessions = store.sessions.map(s => 
      s.id === sessionId ? { ...s, title: newTitle, updatedAt: Date.now() } : s
    );
    set({ sessions });
    get().saveToLocalStorage();
  },

  addMessage: (message) => {
    const store = get();
    const messages = [...store.messages, message];
    
    // 更新当前会话
    const sessions = store.sessions.map(s => 
      s.id === store.currentSessionId
        ? { ...s, messages, updatedAt: Date.now() }
        : s
    );

    set({ messages, sessions });
    get().saveToLocalStorage();
  },

  updateMessage: (messageId, updates) => {
    const store = get();
    const messages = store.messages.map(m =>
      m.id === messageId ? { ...m, ...updates } : m
    );

    const sessions = store.sessions.map(s =>
      s.id === store.currentSessionId
        ? { ...s, messages, updatedAt: Date.now() }
        : s
    );

    set({ messages, sessions });
    get().saveToLocalStorage();
  },

  clearMessages: () => {
    const store = get();
    const sessions = store.sessions.map(s =>
      s.id === store.currentSessionId
        ? { ...s, messages: [], updatedAt: Date.now() }
        : s
    );
    set({ messages: [], sessions });
    get().saveToLocalStorage();
  },

  addStateLog: (log) => {
    const logWithId = { ...log, id: log.id || generateLogId() };
    set(state => ({
      stateLogs: [...state.stateLogs, logWithId]
    }));
  },

  clearStateLogs: () => {
    set({ stateLogs: [] });
  },

  setSessionStatus: (status) => {
    const store = get();
    set({ sessionStatus: status });
    
    // 更新会话状态
    const sessions = store.sessions.map(s =>
      s.id === store.currentSessionId
        ? { ...s, status, updatedAt: Date.now() }
        : s
    );
    set({ sessions });
  },

  setIsLoading: (loading) => {
    set({ isLoading: loading });
  },

  setViewMode: (mode) => {
    set({ viewMode: mode });
  },

  saveToLocalStorage: () => {
    const store = get();
    try {
      const data = {
        sessions: store.sessions,
        currentSessionId: store.currentSessionId,
        timestamp: Date.now(),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      console.error('Failed to save to LocalStorage:', e);
    }
  },

  loadFromLocalStorage: () => {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        const { sessions, currentSessionId } = JSON.parse(data);
        set({
          sessions: sessions || [],
          currentSessionId: currentSessionId || null,
        });
        
        // 如果有当前会话，加载其消息
        if (currentSessionId) {
          const session = sessions.find((s: Session) => s.id === currentSessionId);
          if (session) {
            set({ messages: session.messages });
          }
        }
      }
    } catch (e) {
      console.error('Failed to load from LocalStorage:', e);
    }
  },
}));

// 导出工具函数
export const generateIds = {
  session: generateSessionId,
  message: generateMessageId,
  log: generateLogId,
};
