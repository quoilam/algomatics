/**
 * 侧边栏组件 - 会话历史列表
 */

import React, { useState } from 'react';
import { useChatStore } from '../store';
import { createSession } from '../api';
import '../styles/Sidebar.css';

const Sidebar: React.FC = () => {
  const sessions = useChatStore(state => state.sessions);
  const currentSessionId = useChatStore(state => state.currentSessionId);
  const setCurrentSession = useChatStore(state => state.setCurrentSession);
  const createSessionLocal = useChatStore(state => state.createSession);
  const deleteSession = useChatStore(state => state.deleteSession);
  const renameSession = useChatStore(state => state.renameSession);

  const [isCreating, setIsCreating] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const handleCreateSession = async () => {
    setIsCreating(true);
    try {
      const sessionId = createSessionLocal('新对话');
      // 可选：尝试创建后端会话
      try {
        await createSession();
      } catch (e) {
        console.warn('Failed to create backend session:', e);
      }
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个会话吗？')) {
      deleteSession(sessionId);
    }
  };

  const handleRenameStart = (sessionId: string, title: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRenamingId(sessionId);
    setRenameValue(title);
  };

  const handleRenameSave = (sessionId: string) => {
    if (renameValue.trim()) {
      renameSession(sessionId, renameValue);
    }
    setRenamingId(null);
    setRenameValue('');
  };

  const handleRenameKeyDown = (sessionId: string, e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleRenameSave(sessionId);
    } else if (e.key === 'Escape') {
      setRenamingId(null);
    }
  };

  // 过滤会话
  const filteredSessions = sessions.filter(session =>
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    
    return date.toLocaleDateString();
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">对话历史</h1>
        <button
          className="btn-new-session"
          onClick={handleCreateSession}
          disabled={isCreating}
          title="创建新对话 (Ctrl+K)"
        >
          {isCreating ? '✓' : '+ 新建'}
        </button>
      </div>

      <div className="sidebar-search">
        <input
          type="text"
          className="search-input"
          placeholder="搜索对话..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="sessions-list">
        {filteredSessions.length === 0 ? (
          <div className="empty-sessions">
            <p>暂无对话记录</p>
            <button
              className="btn-create-first"
              onClick={handleCreateSession}
            >
              创建第一个对话
            </button>
          </div>
        ) : (
          filteredSessions.map(session => (
            <div
              key={session.id}
              className={`session-item ${session.id === currentSessionId ? 'active' : ''}`}
              onClick={() => setCurrentSession(session.id)}
            >
              {renamingId === session.id ? (
                <div className="session-rename" onClick={e => e.stopPropagation()}>
                  <input
                    type="text"
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    onKeyDown={e => handleRenameKeyDown(session.id, e)}
                    onBlur={() => handleRenameSave(session.id)}
                    autoFocus
                  />
                </div>
              ) : (
                <>
                  <div className="session-content">
                    <div className="session-title">{session.title}</div>
                    <div className="session-meta">
                      <span className="session-count">
                        {session.messages.length} 消息
                      </span>
                      <span className="session-time">
                        {formatDate(session.updatedAt)}
                      </span>
                    </div>
                  </div>
                  <div className="session-actions">
                    <button
                      className="action-edit"
                      onClick={e => handleRenameStart(session.id, session.title, e)}
                      title="重命名"
                    >
                      ✏️
                    </button>
                    <button
                      className="action-delete"
                      onClick={e => handleDeleteSession(session.id, e)}
                      title="删除"
                    >
                      🗑️
                    </button>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <small>LocalStorage 保存会话</small>
      </div>
    </div>
  );
};

export default Sidebar;
