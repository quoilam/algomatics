/**
 * 单条消息组件
 */

import React from 'react';
import type { Message } from '../types';
import '../styles/MessageItem.css';

interface MessageItemProps {
  message: Message;
  onCopy?: (content: string) => void;
}

const MessageItem: React.FC<MessageItemProps> = ({ message, onCopy }) => {
  const isUser = message.role === 'user';

  const handleCopy = () => {
    if (onCopy) {
      onCopy(message.content);
    } else {
      navigator.clipboard.writeText(message.content).catch(err => {
        console.error('Failed to copy:', err);
      });
    }
  };

  return (
    <div className={`message-item message-${message.role}`}>
      <div className="message-header">
        <span className="message-role">
          {isUser ? '你' : '助手'}
        </span>
        <span className="message-time">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <div className="message-content">
        <p>{message.content}</p>
      </div>
      {!isUser && (
        <div className="message-actions">
          <button
            className="action-btn copy-btn"
            onClick={handleCopy}
            title="复制消息"
          >
            📋 复制
          </button>
        </div>
      )}
      {message.status === 'sending' && (
        <div className="message-status">正在发送...</div>
      )}
      {message.status === 'error' && (
        <div className="message-status error">发送失败</div>
      )}
    </div>
  );
};

export default MessageItem;
