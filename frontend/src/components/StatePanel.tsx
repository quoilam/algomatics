/**
 * 状态面板组件
 */

import React, { useRef, useEffect } from 'react';
import { useChatStore } from '../store';
import StateLogItem from './StateLogItem';
import StatusIndicator from './StatusIndicator';
import '../styles/StatePanel.css';

interface StatePanelProps {
  onViewModeChange?: (mode: 'detailed' | 'simplified') => void;
}

const StatePanel: React.FC<StatePanelProps> = ({ onViewModeChange }) => {
  const stateLogs = useChatStore(state => state.stateLogs);
  const sessionStatus = useChatStore(state => state.sessionStatus);
  const viewMode = useChatStore(state => state.viewMode);
  const setViewMode = useChatStore(state => state.setViewMode);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [stateLogs]);

  const handleViewModeChange = (mode: 'detailed' | 'simplified') => {
    setViewMode(mode);
    onViewModeChange?.(mode);
  };

  // 获取当前执行的步骤
  const currentStep = stateLogs.length > 0 ? stateLogs[stateLogs.length - 1] : null;
  const completedCount = stateLogs.filter(log => log.status === 'completed').length;
  const progress = stateLogs.length > 0 ? Math.round((completedCount / stateLogs.length) * 100) : 0;

  return (
    <div className="state-panel">
      <div className="panel-header">
        <div className="panel-title">
          <span>步骤日志</span>
          <span className="log-count">{stateLogs.length}</span>
        </div>
        <div className="panel-controls">
          <div className="view-mode-toggle">
            <button
              className={`mode-btn ${viewMode === 'detailed' ? 'active' : ''}`}
              onClick={() => handleViewModeChange('detailed')}
              title="详细视图"
            >
              📋 详细
            </button>
            <button
              className={`mode-btn ${viewMode === 'simplified' ? 'active' : ''}`}
              onClick={() => handleViewModeChange('simplified')}
              title="简化视图"
            >
              ⚙️ 简化
            </button>
          </div>
        </div>
      </div>

      <div className="panel-status">
        <StatusIndicator status={sessionStatus} />
        {currentStep && (
          <div className="current-step">
            <span className="step-label">当前步骤:</span>
            <span className="step-name">{currentStep.agent} - {currentStep.action}</span>
          </div>
        )}
        {stateLogs.length > 0 && (
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }}></div>
            <span className="progress-text">{completedCount}/{stateLogs.length}</span>
          </div>
        )}
      </div>

      <div className="logs-container">
        {stateLogs.length === 0 ? (
          <div className="empty-logs">
            <p>等待执行步骤...</p>
          </div>
        ) : (
          <>
            {viewMode === 'detailed' ? (
              stateLogs.map(log => (
                <StateLogItem key={log.id} log={log} />
              ))
            ) : (
              // 简化视图：只显示关键信息
              <div className="simplified-logs">
                {stateLogs.map((log, idx) => (
                  <div key={log.id} className="simplified-log-item">
                    <div className="simplified-step">
                      <span className={`step-number ${log.status}`}>{idx + 1}</span>
                      <div className="step-info">
                        <strong>{log.agent}</strong>
                        <span className="step-action">{log.action}</span>
                      </div>
                      <span className={`step-status status-${log.status}`}>
                        {log.status === 'completed' ? '✓' : 
                         log.status === 'failed' ? '✗' :
                         log.status === 'running' ? '⟳' : '○'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div ref={logsEndRef} />
          </>
        )}
      </div>
    </div>
  );
};

export default StatePanel;
