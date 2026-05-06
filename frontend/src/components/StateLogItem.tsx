/**
 * 状态日志项组件
 */

import React, { useState } from 'react';
import type { StateLog } from '../types';
import '../styles/StateLogItem.css';

interface StateLogItemProps {
  log: StateLog;
}

const StateLogItem: React.FC<StateLogItemProps> = ({ log }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'running':
      case 'started':
        return 'processing';
      case 'failed':
        return 'error';
      case 'paused':
        return 'warning';
      default:
        return 'default';
    }
  };

  const renderDataField = (key: string, value: any) => {
    // 根据键名决定如何渲染
    if (key.toLowerCase().includes('code') || 
        key.toLowerCase().includes('preview') || 
        key.toLowerCase().includes('improvement') ||
        key.toLowerCase().includes('evaluation')) {
      return (
        <div key={key} className="data-field code-field">
          <strong>{key}:</strong>
          <pre>{String(value)}</pre>
        </div>
      );
    }

    if (key.toLowerCase().includes('output_path') && value) {
      return (
        <div key={key} className="data-field path-field">
          <strong>输出路径:</strong>
          <code>{value}</code>
        </div>
      );
    }

    if (key.toLowerCase().includes('image')) {
      return (
        <div key={key} className="data-field image-field">
          <strong>{key}:</strong>
          <img 
            src={typeof value === 'string' && value.startsWith('data:') ? value : `data:image/png;base64,${value}`} 
            alt="output" 
          />
        </div>
      );
    }

    return (
      <div key={key} className="data-field">
        <strong>{key}:</strong>
        <span>{typeof value === 'string' ? value : JSON.stringify(value)}</span>
      </div>
    );
  };

  return (
    <div className={`state-log-item status-${getStatusColor(log.status)}`}>
      <div 
        className="log-header"
        onClick={() => setIsExpanded(!isExpanded)}
        style={{ cursor: 'pointer' }}
      >
        <div className="log-left">
          <span className="log-status-dot"></span>
          <div className="log-titles">
            <div className="log-agent">{log.agent}</div>
            <div className="log-action">{log.action}</div>
          </div>
        </div>
        <div className="log-right">
          <span className="log-time">
            {new Date(log.timestamp).toLocaleTimeString()}
          </span>
          <span className={`log-status status-${getStatusColor(log.status)}`}>
            {log.status}
          </span>
          <span className="expand-icon">
            {isExpanded ? '▼' : '▶'}
          </span>
        </div>
      </div>

      {isExpanded && (
        <div className="log-body">
          {Object.entries(log.data || {}).map(([key, value]) =>
            renderDataField(key, value)
          )}
          {log.output_path && (
            <div className="data-field path-field">
              <strong>输出路径:</strong>
              <code>{log.output_path}</code>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default StateLogItem;
