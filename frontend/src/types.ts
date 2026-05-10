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
  // 可选的扩展字段，来自后端流事件的元数据
  metadata?: { [key: string]: any };
  toolArgs?: any;
  toolResult?: any;
  errorTrace?: string | null;
  sessionId?: string | null;
  imageUrl?: string | null;
  outputImageUrl?: string | null;
}

export type SessionStatus = 'idle' | 'processing' | 'completed' | 'error' | 'accepted' | 'needs_review';

export interface Session {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages?: Message[];
  status: SessionStatus;
  stateLogs?: StateLog[];
  userRequest?: string;
  finalResponse?: string;
  iterationCount?: number;
  messageCount?: number;
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
  input_image_base64?: string;
  input_image_path?: string;
}

export interface StreamMessage {
  type: 'message' | 'state' | 'status' | 'error' | 'complete' | 'tool_call';
  data: any;
}

export interface StreamEvent {
  id?: string;
  type: 'message' | 'state' | 'status' | 'error' | 'complete' | 'tool_call';
  timestamp?: number;
  role?: MessageRole;
  content?: string;
  metadata?: { [key: string]: any };
  toolArgs?: any;
  toolResult?: any;
  errorTrace?: string | null;
  sessionId?: string | null;
}

export interface ChatResponse {
  success: boolean;
  session_id: string;
  text?: string;
  error?: string;
  status?: SessionStatus;
  total_iterations?: number;
  final_score?: number;
  result?: Record<string, any>;
  message?: string;
}

export interface SessionSummaryResponse {
  session_id: string;
  created_at: number;
  updated_at: number;
  title?: string;
  status: SessionStatus;
  user_request?: string | null;
  iteration_count?: number;
  final_response?: string | null;
  message_count?: number;
}

export interface SessionResponse {
  success: boolean;
  session_id: string;
  title?: string;
  status: SessionStatus;
  created_at: number;
  updated_at: number;
  messages: Message[];
  state_logs: StateLog[];
  current_agent?: string | null;
  current_action?: string | null;
  output_image_base64?: string;
  input_image_base64?: string;
  final_response?: string;
  user_request?: string | null;
  iteration_count?: number;
  feedback_history?: Array<Record<string, any>>;
}

export interface SessionListResponse {
  success: boolean;
  sessions: SessionSummaryResponse[];
}

export type ViewMode = 'detailed' | 'simplified';
