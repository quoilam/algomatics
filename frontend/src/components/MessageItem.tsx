/**
 * 单条消息组件
 */

import React from 'react';
import { marked } from 'marked';
import type { Message } from '../types';
import '../styles/MessageItem.css';

interface MessageItemProps {
  message: Message;
  onCopy?: (content: string) => void;
  showDetails?: boolean;
}

const markdownOptions = {
  gfm: true,
  breaks: true,
};

const renderMarkdown = (content: string) => {
  const rendered = marked.parse(content || '', markdownOptions);
  return { __html: typeof rendered === 'string' ? rendered : '' };
};

const stringifyDetailValue = (value: any) => {
  if (value === null || value === undefined) {
    return '';
  }

  if (typeof value === 'string') {
    const trimmed = value.trim();
    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2);
      } catch (error) {
        return value;
      }
    }

    return value;
  }

  return JSON.stringify(value, null, 2);
};

const renderDetailSection = (title: string, value: any, className = '') => {
  if (value === null || value === undefined || value === '') {
    return null;
  }

  const displayValue = stringifyDetailValue(value);
  const isMultiline = displayValue.includes('\n');

  return (
    <div className={`detail-section ${className}`.trim()}>
      <div className="detail-title">{title}</div>
      {isMultiline ? (
        <pre className="detail-pre">{displayValue}</pre>
      ) : (
        <div className="detail-text">{displayValue}</div>
      )}
    </div>
  );
};

const phaseText: Record<string, string> = {
  decision: '决策',
  iteration: '迭代',
  action: '执行',
  result: '结果',
  progress: '进展',
};

const getMessageRoleLabel = (message: Message) => {
  const isUser = message.role === 'user';
  if (isUser) {
    return '你';
  }

  if (message.metadata?.kind !== 'agent_update') {
    return '助手';
  }

  const parts = [
    message.metadata.agent || '实时进展',
    message.metadata.iteration ? `第 ${message.metadata.iteration} 轮` : null,
    message.metadata.phase ? (phaseText[message.metadata.phase] || message.metadata.phase) : null,
  ].filter(Boolean);

  return parts.join(' · ');
};

const MessageItem: React.FC<MessageItemProps> = ({ message, onCopy, showDetails = true }) => {
  const isUser = message.role === 'user';
  const hasDetails = Boolean(message.metadata || message.toolArgs || message.toolResult || message.errorTrace || message.sessionId);

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
          {getMessageRoleLabel(message)}
        </span>
        <span className="message-time">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <div className="message-content">
        {message.imageUrl && (
          <img className="message-image" src={message.imageUrl} alt="用户上传" />
        )}
        <div className="message-markdown" dangerouslySetInnerHTML={renderMarkdown(message.content)} />
        {message.outputImageUrl && (
          <img className="message-image output-image" src={message.outputImageUrl} alt="处理结果" />
        )}
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
        <div className="message-status">正在思考和执行...</div>
      )}
      {message.status === 'error' && (
        <div className="message-status error">发送失败</div>
      )}
      {showDetails && hasDetails && (
        <details className="message-details">
          <summary>工具调用与状态详情</summary>
          <div className="details-body">
            {renderDetailSection('Session', message.sessionId)}
            {renderDetailSection('Metadata', message.metadata)}
            {renderDetailSection('Tool Arguments', message.toolArgs)}
            {renderDetailSection('Tool Result', message.toolResult)}
            {renderDetailSection('Error Trace', message.errorTrace, 'error-trace')}
          </div>
        </details>
      )}
    </div>
  );
};

export default MessageItem;
