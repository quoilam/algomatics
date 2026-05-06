/**
 * 核心数据类型定义
 */

export type MessageRole = 'user' | 'assistant' | 'system';
export type MessageStatus = 'sending' | 'sent' | 'error' | 'complete';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  status: MessageStatus;
  streaming?: boolean;
}

export type SessionStatus = 'idle' | 'processing' | 'completed' | 'error' | 'accepted' | 'needs_review';

export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: Message[];
  status: SessionStatus;
}

export type StateLogStatus = 'started' | 'running' | 'completed' | 'failed' | 'paused';

export interface StateLogData {
  [key: string]: any;
}

export interface StateLog {
  id: string;
  agent: string;
  action: string;
  status: StateLogStatus;
  timestamp: number;
  data: StateLogData;
  output_path?: string;
  output_image_base64?: string;
}

export interface StreamMessage {
  type: 'message' | 'state' | 'status' | 'error' | 'complete';
  data: any;
}

export interface ChatResponse {
  success: boolean;
  session_id: string;
  text?: string;
  error?: string;
  status?: SessionStatus;
}

export interface SessionResponse {
  status: SessionStatus;
  state_logs: StateLog[];
  output_image_base64?: string;
  final_response?: string;
}

export type ViewMode = 'detailed' | 'simplified';
