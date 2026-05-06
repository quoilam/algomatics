/**
 * 状态指示器组件
 */

import React from 'react';
import type { StateLogStatus, SessionStatus } from '../types';
import '../styles/StatusIndicator.css';

interface StatusIndicatorProps {
  status: SessionStatus;
  agentName?: string;
  actionName?: string;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  agentName,
  actionName,
}) => {
  const getStatusColor = (s: SessionStatus | StateLogStatus) => {
    switch (s) {
      case 'idle':
      case 'completed':
      case 'accepted':
        return 'success';
      case 'processing':
      case 'running':
      case 'started':
        return 'processing';
      case 'error':
      case 'failed':
        return 'error';
      case 'needs_review':
      case 'paused':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusLabel = (s: SessionStatus | StateLogStatus) => {
    const labels: Record<string, string> = {
      idle: '待处理',
      processing: '处理中',
      processing: '进行中',
      completed: '已完成',
      accepted: '已接受',
      error: '错误',
      needs_review: '需要审查',
      failed: '失败',
      started: '已开始',
      running: '运行中',
      paused: '已暂停',
    };
    return labels[s] || s;
  };

  const colorClass = getStatusColor(status);
  const label = getStatusLabel(status);

  return (
    <div className="status-indicator">
      <div className={`status-badge status-${colorClass}`}>
        <span className="status-dot"></span>
        <span className="status-text">{label}</span>
      </div>
      {agentName && (
        <div className="agent-info">
          <span className="agent-name">{agentName}</span>
          {actionName && <span className="action-name">{actionName}</span>}
        </div>
      )}
    </div>
  );
};

export default StatusIndicator;
