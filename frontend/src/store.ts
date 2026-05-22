/**
 * Zustand 状态管理 Store
 */

import { create } from 'zustand';
import type {
  Message,
  Session,
  StateLog,
  ViewMode,
  SessionStatus,
  SessionResponse,
  TurnSummary,
} from './types';

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

  // Turn state
  turns: TurnSummary[];
  activeTurnId: number | null;

  // 操作方法
  setCurrentSession: (sessionId: string) => void;
  createSession: (title: string, backendSessionId: string) => void;
  replaceSessions: (sessions: Session[], currentSessionId?: string | null) => void;
  hydrateSessionFromBackend: (session: SessionResponse) => void;
  deleteSession: (sessionId: string) => void;
  renameSession: (sessionId: string, newTitle: string) => void;

  addMessage: (message: Message) => void;
  updateMessage: (messageId: string, updates: Partial<Message>) => void;
  clearMessages: () => void;
  appendMessageFromStream?: (event: any) => void;

  addStateLog: (log: StateLog) => void;
  clearStateLogs: () => void;
  appendStateLogFromStream?: (event: any) => void;

  setSessionStatus: (status: SessionStatus) => void;
  setIsLoading: (loading: boolean) => void;
  setViewMode: (mode: ViewMode) => void;
  setTurns: (turns: TurnSummary[]) => void;
  setActiveTurnId: (turnId: number | null) => void;
}

const generateLogId = () => 'log_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

export const useChatStore = create<ChatStore>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  messages: [],
  stateLogs: [],
  sessionStatus: 'idle',
  viewMode: 'detailed',
  isLoading: false,
  turns: [],
  activeTurnId: null,

  setCurrentSession: (sessionId) => {
    const store = get();
    const session = store.sessions.find(s => s.id === sessionId);
    if (session) {
      set({
        currentSessionId: sessionId,
        messages: [],  // cleared until hydrateSessionFromBackend loads them from API
        stateLogs: [],
        sessionStatus: session.status,
      });
    }
  },

  createSession: (title, backendSessionId) => {
    const newSession: Session = {
      id: backendSessionId,
      title: title || '新对话',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      status: 'idle',
    };

    set(state => ({
      sessions: [newSession, ...state.sessions],
      currentSessionId: backendSessionId,
      messages: [],
      stateLogs: [],
      sessionStatus: 'idle',
    }));
  },

  replaceSessions: (sessions, currentSessionId = null) => {
    set({
      sessions,
      currentSessionId,
    });
  },

  hydrateSessionFromBackend: (session) => {
    const resolvedMessages: Message[] = Array.isArray(session.messages) && session.messages.length > 0
      ? session.messages.map(message => ({
          ...message,
          role: message.role as Message['role'],
          status: (message.status || (message.role === 'user' ? 'sent' : 'complete')) as Message['status'],
          imageUrl: message.role === 'user' ? (message.imageUrl || session.input_image_base64 || null) : message.imageUrl,
        }))
      : [];

    if (resolvedMessages.length === 0 && session.user_request) {
      resolvedMessages.push({
        id: `${session.session_id}_user`,
        role: 'user',
        content: session.user_request,
        timestamp: session.created_at,
        status: 'sent',
        imageUrl: session.input_image_base64 || null,
      });
    }

    if (session.final_response) {
      resolvedMessages.push({
        id: `${session.session_id}_assistant`,
        role: 'assistant',
        content: session.final_response,
        timestamp: session.updated_at,
        status: 'complete',
      });
    }

    // Capture turns from the session response
    const turns = Array.isArray(session.turns) ? session.turns : [];

    const resolvedSession: Session = {
      id: session.session_id,
      title: session.title || session.user_request?.slice(0, 24) || `对话 ${new Date(session.created_at).toLocaleTimeString()}`,
      createdAt: session.created_at,
      updatedAt: session.updated_at,
      status: session.status,
      stateLogs: session.state_logs || [],
      userRequest: session.user_request || undefined,
      finalResponse: session.final_response || undefined,
      iterationCount: session.iteration_count || 0,
    };

    set(state => {
      const existingIndex = state.sessions.findIndex(item => item.id === session.session_id);
      const sessions = [...state.sessions];

      if (existingIndex >= 0) {
        sessions[existingIndex] = resolvedSession;
      } else {
        sessions.unshift(resolvedSession);
      }

      const isCurrent = state.currentSessionId === session.session_id;

      return {
        sessions,
        currentSessionId: isCurrent ? session.session_id : state.currentSessionId,
        messages: isCurrent ? resolvedMessages : state.messages,
        stateLogs: isCurrent ? (session.state_logs || []) : state.stateLogs,
        sessionStatus: isCurrent ? session.status : state.sessionStatus,
        turns: isCurrent ? turns : state.turns,
        activeTurnId: isCurrent ? (turns.length > 0 ? turns[turns.length - 1].turn_id : null) : state.activeTurnId,
      };
    });
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
  },

  renameSession: (sessionId, newTitle) => {
    const store = get();
    const sessions = store.sessions.map(s =>
      s.id === sessionId ? { ...s, title: newTitle, updatedAt: Date.now() } : s
    );
    set({ sessions });
  },

  addMessage: (message) => {
    set(state => {
      const existingIndex = state.messages.findIndex(item => item.id === message.id);
      const messages = existingIndex >= 0
        ? state.messages.map(item => item.id === message.id ? { ...item, ...message } : item)
        : [...state.messages, message];

      return { messages };
    });
  },

  updateMessage: (messageId, updates) => {
    const store = get();
    const messages = store.messages.map(m =>
      m.id === messageId ? { ...m, ...updates } : m
    );
    set({ messages });
  },

  // 将来自流的事件追加为消息（幂等）
  appendMessageFromStream: (event) => {
    const store = get();
    const msgId = event.id || (event.data && event.data.id) || `stream_${Date.now()}_${Math.random().toString(36).slice(2,8)}`;
    const exists = store.messages.some(m => m.id === msgId || (m.timestamp === event.timestamp && m.role === event.role && m.content === event.content));
    const newMessage: Message = {
      id: msgId,
      role: (event.role || (event.data && event.data.role) || 'assistant') as any,
      content: event.content || (event.data && event.data.content) || '',
      timestamp: event.timestamp || (event.data && event.data.timestamp) || Date.now(),
      status: (event.status || 'sent') as any,
      streaming: !!event.streaming,
      metadata: event.metadata || (event.data && event.data.metadata) || undefined,
      toolArgs: event.toolArgs || (event.data && event.data.toolArgs),
      toolResult: event.toolResult || (event.data && event.data.toolResult),
      errorTrace: event.errorTrace || (event.data && event.data.errorTrace) || null,
      sessionId: event.sessionId || (event.data && event.data.sessionId) || store.currentSessionId,
    };

    if (exists) {
      const messages = store.messages.map(m => (m.id === msgId ? { ...m, ...newMessage } : m));
      set({ messages });
    } else {
      const messages = [...store.messages, newMessage];
      set({ messages });
    }
  },

  clearMessages: () => {
    set({ messages: [] });
  },

  // 追加来自流的状态日志（幂等）
  appendStateLogFromStream: (event) => {
    const store = get();
    const id = event.id || (event.data && event.data.id) || generateLogId();
    const exists = store.stateLogs.some(l => l.id === id);
    const log: StateLog = {
      id,
      agent: event.agent || (event.data && event.data.agent) || 'agent',
      action: event.action || (event.data && event.data.action) || 'action',
      status: (event.status || (event.data && event.data.status) || 'running') as any,
      timestamp: event.timestamp || (event.data && event.data.timestamp) || Date.now(),
      data: event.data || (event.payload) || {},
      output_path: event.output_path || (event.data && event.data.output_path),
      output_image_base64: event.output_image_base64 || (event.data && event.data.output_image_base64),
    };

    if (!exists) {
      set(state => ({ stateLogs: [...state.stateLogs, log] }));
    }
  },

  addStateLog: (log) => {
    const logWithId = { ...log, id: log.id || generateLogId() };
    set(state => {
      const existingIndex = state.stateLogs.findIndex(item => item.id === logWithId.id);
      const stateLogs = existingIndex >= 0
        ? state.stateLogs.map(item => item.id === logWithId.id ? { ...item, ...logWithId } : item)
        : [...state.stateLogs, logWithId];

      return { stateLogs };
    });
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

  setTurns: (turns) => set({ turns }),

  setActiveTurnId: (turnId) => set({ activeTurnId: turnId }),

}));
